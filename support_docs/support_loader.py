import asyncio
import logging
from typing import Any, Dict, List

from vector_service.pinecone_client import pinecone_support_client

from .FAQ_Knowledge_base import KnowledgeProvider, ProductPolicyScraper

logger = logging.getLogger(__name__)


class SupportLoader:
    def __init__(self, llm_service=None):
        self.pinecone_support = pinecone_support_client
        self.policy_extractor = ProductPolicyScraper()
        self.knowledge_provider = KnowledgeProvider()
        self.llm_service = llm_service
        self._is_initialized = False
        # For lightweight analytics
        self._last_citations: List[str] = []
        self._last_mode: str = "init"  # one of: init, rag, fallback

    def initialize_knowledge_base(self, use_s3: bool = True) -> bool:
        """Initialize the support knowledge base with data from S3 or fallback to generation"""
        if not self.pinecone_support.is_available():
            logger.warning("⚠️ Pinecone not available. Using fallback support responses.")
            return False

        try:
            all_support_docs = []

            # Try to load from S3 first if enabled
            if use_s3:
                try:
                    from data.s3_client import s3_client

                    support_docs = s3_client.get_support_documents()
                    if support_docs:
                        all_support_docs = support_docs
                        logger.info(f"✅ Loaded {len(support_docs)} support documents from S3")
                    else:
                        logger.warning("⚠️ No support data found in S3, falling back to generation")
                        use_s3 = False
                except Exception as s3_error:
                    logger.warning(f"⚠️ S3 loading failed: {s3_error}, falling back to generation")
                    use_s3 = False

            # Fallback to generating support data if S3 not available or failed
            if not use_s3 or not all_support_docs:
                logger.info("🔄 Generating support data from products and FAQs...")

                # Extract real support data from products
                product_support_docs = self.policy_extractor.extract_policies()

                # Get additional FAQ data (now includes hybrid static + scraped)
                faq_docs = self.knowledge_provider.get_all_knowledge()

                # Combine all support documents
                all_support_docs = product_support_docs + faq_docs
                logger.info(f"📊 Generated {len(all_support_docs)} support documents")

            # Clear existing index and upload new data
            logger.info("🔄 Updating Pinecone support knowledge base...")
            self.pinecone_support.clear_index()

            # Upsert documents
            successful_upserts = self.pinecone_support.index_support_docs(all_support_docs)

            if successful_upserts > 0:
                logger.info(f"✅ Support knowledge base initialized with {successful_upserts} documents")
                self._is_initialized = True
                return True
            else:
                logger.error("❌ Failed to initialize support knowledge base")
                return False

        except Exception as e:
            logger.error(f"❌ Error initializing support knowledge base: {e}")
            return False

    def is_available(self) -> bool:
        """Check if support RAG is available"""
        return self.pinecone_support.is_available() and self._is_initialized

    async def handle_support_query(self, user_message: str, context: Dict[str, Any] = None) -> str:
        """Handle support queries with real RAG"""
        if not self.is_available():
            # Mark fallback mode
            self._last_mode = "fallback"
            self._last_citations = []
            return self._fallback_support_response(user_message)

        try:
            # Search for relevant support documents
            relevant_docs = self.pinecone_support.search_support(user_message, top_k=3)

            if not relevant_docs:
                return self._fallback_support_response(user_message)

            # Build context from retrieved documents
            context_parts = []
            for doc in relevant_docs:
                context_parts.append(f"- {doc['content']}")

            # Build concise citations from source/category
            citations: List[str] = []
            for doc in relevant_docs:
                src = (doc.get("source") or doc.get("category") or "").strip()
                if src:
                    citations.append(src)
            # Deduplicate while preserving order
            seen = set()
            unique_citations: List[str] = []
            for c in citations:
                key = c.lower()
                if key not in seen:
                    seen.add(key)
                    unique_citations.append(c)
            # Keep it short
            citation_text = ""
            if unique_citations:
                if len(unique_citations) == 1:
                    citation_text = f"Source: {unique_citations[0]}"
                else:
                    citation_text = "Sources: " + ", ".join(unique_citations[:3])
            # Save for analytics
            self._last_citations = unique_citations[:3]

            context_text = "\n".join(context_parts)

            # Generate response with LLM
            response = await self._generate_response_with_context(user_message, context_text)
            # Append citations (if any)
            if citation_text:
                response = f"{response}\n\n{citation_text}"
            # Mark mode as RAG
            self._last_mode = "rag"
            return response

        except Exception as e:
            logger.error(f"Error in support RAG for query '{user_message[:50]}...': {e}", exc_info=True)
            self._last_mode = "fallback"
            self._last_citations = []
            return self._fallback_support_response(user_message)

    async def _generate_response_with_context(self, user_message: str, context: str) -> str:
        """Generate response using LLM with retrieved context"""
        if not self.llm_service:
            # Simple context-based response without LLM
            return f"Based on our policies: {context.split('-')[1].strip() if '-' in context else context}"

        prompt = f"""You are a helpful customer service assistant. Answer the customer's question based on the support information provided.

Support Information:
{context}

Customer Question: {user_message}

Instructions:
- Provide a helpful, specific answer based on the support information above
- Be natural and conversational
- If the information doesn't fully answer the question, say what you can help with
- Keep your response concise but complete

Answer:"""

        try:
            # Use existing LLM service
            response = await asyncio.to_thread(self.llm_service._generate_with_llm, prompt)
            return (
                response.strip()
                if response
                else "I'm here to help based on our policies. Could you provide a bit more detail?"
            )
        except Exception as e:
            logger.error(f"Error generating LLM response for query '{user_message[:50]}...': {e}", exc_info=True)
            # Extract first relevant piece of information as fallback
            if context:
                first_info = context.split("\n")[0].replace("- ", "")
                return f"Based on our policies: {first_info}"
            return "I'm sorry, I couldn't process your request at this time."

    def _fallback_support_response(self, user_message: str) -> str:
        """Fallback support responses when RAG is not available"""
        message_lower = user_message.lower()

        # Simple keyword-based fallback (better than the old hardcoded version)
        if any(word in message_lower for word in ["return", "refund", "send back"]):
            return "Our return policies vary by product. Most items can be returned within 15-90 days in original condition. Please check the specific return policy for your item or contact customer service for assistance."

        elif any(word in message_lower for word in ["shipping", "delivery", "ship"]):
            return "Shipping times vary by product and location. Most items ship within 1-3 business days with standard delivery in 3-7 days. Express and overnight options are available for many products."

        elif any(word in message_lower for word in ["warranty", "guarantee"]):
            return "Products come with manufacturer warranties that vary by brand and product type. Extended warranties may be available for electronics and other items."

        elif any(word in message_lower for word in ["defective", "broken", "damaged", "problem"]):
            return "If you received a defective item, please contact our customer service team immediately. We'll arrange for a replacement or refund at no cost to you."

        else:
            return "I'm here to help with your questions. Please contact our customer service team for specific assistance with orders, returns, shipping, or product issues."

    def get_support_stats(self) -> Dict[str, Any]:
        """Get statistics about the support knowledge base"""
        stats = {
            "pinecone_available": self.pinecone_support.is_available(),
            "knowledge_base_initialized": self._is_initialized,
            "fallback_mode": not self.is_available(),
        }

        # Add Pinecone stats
        if self.pinecone_support.is_available():
            pinecone_health = self.pinecone_support.get_health()
            stats["pinecone_health"] = pinecone_health

        # Add S3 support data stats
        try:
            from data.s3_client import s3_client

            s3_stats = s3_client.get_data_stats("support")
            stats["s3_support_data"] = s3_stats
        except Exception as e:
            stats["s3_support_data_error"] = str(e)

        # Add product data summary
        try:
            product_summary = self.policy_extractor.get_support_summary()
            stats["product_data_summary"] = product_summary
        except Exception as e:
            stats["product_data_error"] = str(e)

        return stats
