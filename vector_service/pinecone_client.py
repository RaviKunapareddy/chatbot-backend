"""
Unified Pinecone Client

This module provides a unified Pinecone client that can be used for both
product search and support document RAG. It replaces the separate Pinecone
clients previously used in the codebase.
"""

import hashlib
import json
import logging
import os
import random
import time
import uuid
from typing import Any, Dict, List, Optional

import numpy as np
import requests
from dotenv import load_dotenv

# Optional Pinecone import - using v6.x API
try:
    from pinecone import Pinecone

    PINECONE_AVAILABLE = True
except ImportError:
    PINECONE_AVAILABLE = False
    logging.warning("⚠️ Pinecone not available - vector search will be disabled")

# Load environment variables from .env file
load_dotenv()
logger = logging.getLogger(__name__)


class PineconeClient:
    """Unified Pinecone client for both product search and support document RAG"""

    def __init__(
        self,
        api_key: str = None,
        environment: str = "us-east-1",
        index_name: str = None,
        dimension: int = 384,
        hf_model: str = None,
        index_type: str = "products",
    ):
        """
        Initialize Pinecone client

        Args:
            api_key: Pinecone API key (defaults to PINECONE_API_KEY env var)
            environment: Pinecone environment (defaults to us-east-1)
            index_name: Name of the Pinecone index to use
            dimension: Dimension of embeddings (defaults to 384 for BAAI/bge-small-en-v1.5)
            hf_model: HuggingFace model to use for embeddings
            index_type: Type of index ("products" or "support")
        """
        self.api_key = api_key or os.getenv("PINECONE_API_KEY")
        self.environment = environment
        self.index_type = index_type

        # Set default index name based on type if not provided
        if index_name:
            self.index_name = index_name
        elif index_type == "products":
            self.index_name = os.getenv("PINECONE_PRODUCTS_INDEX", "chatbot-products")
        else:  # support
            self.index_name = os.getenv("PINECONE_SUPPORT_INDEX", "chatbot-support-knowledge")

        self.dimension = dimension

        # Initialize Hugging Face API
        self.hf_api_key = os.getenv("HF_API_KEY")

        # Set default model based on type if not provided
        if hf_model:
            self.hf_model = hf_model
        elif index_type == "products":
            self.hf_model = os.getenv("HF_PRODUCT_MODEL", "BAAI/bge-small-en-v1.5")
        else:  # support
            self.hf_model = os.getenv("HF_SUPPORT_MODEL", "BAAI/bge-small-en-v1.5")

        # Use direct models API for feature extraction
        self.hf_api_url = f"https://api-inference.huggingface.co/models/{self.hf_model}"

        # Initialize Pinecone
        self.pc = None
        self.index = None
        self.available = False
        self._initialize_pinecone()

    def _initialize_pinecone(self):
        """Initialize Pinecone connection with v6.x API"""
        if not PINECONE_AVAILABLE:
            logger.warning("⚠️ Pinecone package not available. Vector search will be disabled.")
            return

        try:
            if not self.api_key:
                logger.warning("⚠️ PINECONE_API_KEY not found. Vector search will be disabled.")
                return

            # Initialize Pinecone with v6.x API
            self.pc = Pinecone(api_key=self.api_key)

            # Connect to existing serverless index
            try:
                # Connect to the index
                self.index = self.pc.Index(self.index_name)
                # Test the connection
                stats = self.index.describe_index_stats()
                logger.info(f"✅ Connected to Pinecone serverless index: {self.index_name}")
                logger.info(f"📊 Index has {stats.total_vector_count} vectors")
                self.available = True
            except Exception as connect_error:
                logger.warning(
                    f"❌ Could not connect to index '{self.index_name}': {connect_error}"
                )
                # Fail fast if index doesn't exist
                logger.error("Please create the Pinecone index manually in the Pinecone console")
                logger.error(f"Index name: {self.index_name}, Dimension: {self.dimension}")
                raise connect_error

        except Exception as e:
            logger.error(f"❌ Pinecone initialization failed for index '{self.index_name}': {e}", exc_info=True)
            self.pc = None
            self.index = None

    def is_available(self) -> bool:
        """Check if Pinecone is available"""
        return self.available and self.index is not None

    def _get_embedding(self, text: str) -> List[float]:
        """Get embedding from Hugging Face API with retries and fallback"""
        # Configuration for retries
        max_retries = 3
        retry_delay = 2  # seconds
        timeout = 15  # seconds
        
        # Try multiple times with increasing timeout
        for attempt in range(1, max_retries + 1):
            try:
                # Log retry attempts if not the first try
                if attempt > 1:
                    logger.info(f"Retry attempt {attempt}/{max_retries} for embedding generation")
                
                # Try to get embedding from Hugging Face API
                headers = {"Authorization": f"Bearer {self.hf_api_key}"}
                current_timeout = timeout * attempt  # Increase timeout with each retry
                
                logger.debug(f"Requesting embedding with timeout={current_timeout}s")
                response = requests.post(
                    self.hf_api_url,
                    headers=headers,
                    json={"inputs": [text]},  # Correct format: array of strings
                    timeout=current_timeout,
                )

                if response.status_code == 200:
                    embeddings = response.json()
                    if isinstance(embeddings, list) and len(embeddings) > 0:
                        # Track embedding usage for free tier monitoring
                        try:
                            import os
                            from datetime import datetime

                            import redis

                            redis_url = os.getenv("REDIS_URL")
                            if redis_url:
                                redis_client = redis.from_url(redis_url, decode_responses=True)
                                this_month = datetime.now().strftime("%Y-%m")
                                redis_client.incr(f"monthly_embeddings:{this_month}")
                                redis_client.expire(
                                    f"monthly_embeddings:{this_month}", 2678400
                                )  # 31 days
                        except Exception:
                            pass  # Don't fail embedding if tracking fails

                        logger.debug("Successfully generated embedding")
                        return embeddings[0]  # First (and only) embedding
                    else:
                        logger.warning(f"Unexpected embedding format: {embeddings}")
                else:
                    logger.warning(f"Failed to get embedding from API: {response.text}")
                    
                    # Don't retry on 4xx errors (client errors)
                    if 400 <= response.status_code < 500:
                        break
            
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout getting embedding (attempt {attempt}/{max_retries})")
            except Exception as e:
                logger.warning(f"Error getting embedding from API for text '{text[:30]}...' (attempt {attempt}/{max_retries}): {e}", exc_info=True)
            
            # Wait before retrying, but not on the last attempt
            if attempt < max_retries:
                time.sleep(retry_delay * attempt)  # Exponential backoff
        
        # If we get here, all retries failed
        # Generate a simple deterministic embedding as fallback
        logger.warning("All embedding API attempts failed, using fallback")
        return self._generate_fallback_embedding(text)

    def _generate_fallback_embedding(self, text: str) -> List[float]:
        """Generate a simple deterministic embedding when HuggingFace API fails"""
        logger.info("Using fallback embedding generation")

        # Create a simple deterministic embedding based on text characteristics
        # This is not semantically meaningful but provides a consistent vector for the same text

        # Create a hash of the text
        text_hash = hashlib.md5(text.encode()).digest()

        # Use the hash to seed a random number generator
        np.random.seed(int.from_bytes(text_hash[:4], byteorder="big"))

        # Generate a random embedding vector of the correct dimension
        embedding = np.random.uniform(-1, 1, self.dimension).tolist()

        # Normalize to unit length for cosine similarity
        norm = sum(x * x for x in embedding) ** 0.5
        if norm > 0:
            embedding = [x / norm for x in embedding]

        return embedding

    def _normalize_tag(self, tag) -> str:
        """Normalize a tag string to a safe metadata key suffix.
        Rules: lowercase, trim, non-alnum -> underscore, collapse repeats, strip edges.
        """
        try:
            s = str(tag).strip().lower()
            s = re.sub(r"[^a-z0-9]+", "_", s)
            s = re.sub(r"_+", "_", s).strip("_")
            return s
        except Exception:
            return ""

    # ===== Product-specific methods =====

    def index_products(self, products: List[Dict[str, Any]]) -> bool:
        """Index products with embeddings for vector search"""
        if not self.is_available():
            logger.warning("Pinecone not available")
            return False

        try:
            vectors_to_upsert = []
            successful = 0

            for product in products:
                # Create searchable text combining title, description, category
                searchable_text = f"{product.get('title', '')} {product.get('description', '')} {product.get('category', '')}"

                # Generate embedding using Hugging Face API
                embedding = self._get_embedding(searchable_text)
                if not embedding:
                    logger.warning(
                        f"Skipping product {product.get('id')} - failed to generate embedding"
                    )
                    continue

                # Derive values needed for metadata
                stock_value = int(product.get("stock", 0))
                availability_status = "in_stock" if stock_value > 0 else "out_of_stock"
                sku_value = (
                    str(product.get("sku"))
                    if product.get("sku") is not None
                    else str(product.get("id", ""))
                )
                # Lowercased variants for case-insensitive filtering
                brand_value = product.get("brand", "")
                category_value = product.get("category", "")
                brand_value_lc = str(brand_value).lower() if brand_value is not None else ""
                category_value_lc = (
                    str(category_value).lower() if category_value is not None else ""
                )
                # Compute discount if not explicitly provided but originalPrice/price exist
                price_val = float(product.get("price", 0))
                original_price_val = float(product.get("originalPrice", 0))
                explicit_discount = product.get("discountPercentage")
                if (
                    (explicit_discount is None or float(explicit_discount) == 0.0)
                    and original_price_val > 0
                    and price_val > 0
                    and price_val < original_price_val
                ):
                    try:
                        computed_discount = round(
                            100.0 * (original_price_val - price_val) / original_price_val, 2
                        )
                    except Exception:
                        computed_discount = 0.0
                else:
                    try:
                        computed_discount = (
                            float(explicit_discount) if explicit_discount is not None else 0.0
                        )
                    except Exception:
                        computed_discount = 0.0

                # Prepare metadata (Pinecone has size limits)
                # We need to ensure all values are strings, numbers, or booleans for Pinecone
                metadata = {
                    "id": str(product.get("id", "")),
                    "title": product.get("title", "")[:1000],  # Limit string size
                    "description": product.get("description", "")[:1000],  # Limit string size
                    "category": category_value,
                    "category_lc": category_value_lc,
                    "brand": brand_value,
                    "brand_lc": brand_value_lc,
                    "price": price_val,
                    "rating": float(product.get("rating", 0)),
                    "searchable_text": searchable_text[:1000],  # Limit string size
                    "type": "product",  # Add type to distinguish from support docs
                    # Add image fields
                    "thumbnail": (
                        str(product.get("thumbnail", ""))[:1000] if product.get("thumbnail") else ""
                    ),
                    # Store first image from images array if present
                    "image": (
                        str(product.get("images", [""])[0])[:1000]
                        if product.get("images") and len(product.get("images", [])) > 0
                        else ""
                    ),
                    # Extended ecommerce attributes for richer filtering
                    "stock": stock_value,
                    "discountPercentage": computed_discount,
                    "originalPrice": original_price_val,
                    # Planned fields per enhancement plan 1.2
                    "availabilityStatus": availability_status,
                    "sku": sku_value,
                }

                # Add tags if available (convert to strings) and boolean flags for server-side filtering
                if "tags" in product and isinstance(product["tags"], list):
                    # Preserve comma-joined tags for backward compatibility
                    metadata["tags"] = ",".join(
                        str(tag) for tag in product["tags"][:20]
                    )  # Limit number of tags
                    # Boolean flags to enable server-side AND filtering on tags
                    for tag in product["tags"][:20]:
                        norm = self._normalize_tag(tag)
                        if norm:
                            metadata[f"tag_{norm}"] = True

                # Create vector record
                vectors_to_upsert.append(
                    {
                        "id": str(product.get("id", str(uuid.uuid4()))),
                        "values": embedding,
                        "metadata": metadata,
                    }
                )

                # Batch upsert in chunks of 100 to avoid request size limits
                if len(vectors_to_upsert) >= 100:
                    self.index.upsert(vectors=vectors_to_upsert)
                    successful += len(vectors_to_upsert)
                    vectors_to_upsert = []

            # Upsert any remaining vectors
            if vectors_to_upsert:
                self.index.upsert(vectors=vectors_to_upsert)
                successful += len(vectors_to_upsert)

            logger.info(f"✅ Indexed {successful} products to Pinecone")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to index products: {e}")
            return False

    def search_products(
        self,
        query: str,
        limit: int = 5,
        price_min: float = None,
        price_max: float = None,
        brand: Optional[str] = None,
        category: Optional[str] = None,
        rating_min: Optional[float] = None,
        in_stock: Optional[bool] = None,
        discount_min: Optional[float] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for products using vector search with optional metadata filtering

        Backward compatible: existing callers can continue to pass only (query, limit, price_min, price_max)
        """
        if not self.is_available():
            logger.warning("Pinecone not available, returning empty results")
            return []

        try:
            # Generate query embedding using Hugging Face API
            query_embedding = self._get_embedding(query)
            if not query_embedding:
                logger.error("Failed to generate query embedding")
                return []

            # Prepare filter dict for metadata filtering
            filter_dict = {"type": "product"}  # Only search for products

            # Add price range filter if provided
            if price_min is not None or price_max is not None:
                price_filter = {}
                if price_min is not None:
                    price_filter["$gte"] = float(price_min)
                if price_max is not None:
                    price_filter["$lte"] = float(price_max)
                filter_dict["price"] = price_filter

            # Case-insensitive brand/category filtering controlled by env flag
            ci_flag = str(os.getenv("SEARCH_CASE_INSENSITIVE", "false")).lower() in (
                "1",
                "true",
                "yes",
            )
            # Add brand filter
            if brand:
                if ci_flag:
                    filter_dict["brand_lc"] = str(brand).lower()
                else:
                    filter_dict["brand"] = str(brand)

            # Add category filter
            if category:
                if ci_flag:
                    filter_dict["category_lc"] = str(category).lower()
                else:
                    filter_dict["category"] = str(category)

            # Rating lower bound
            if rating_min is not None:
                filter_dict["rating"] = {"$gte": float(rating_min)}

            # In-stock filter
            if in_stock is True:
                filter_dict["stock"] = {"$gt": 0}

            # Minimum discount percentage
            if discount_min is not None:
                filter_dict["discountPercentage"] = {"$gte": float(discount_min)}

            # Server-side tags filter (AND semantics) gated by env flag until reindex is complete
            # Enable with: SEARCH_TAGS_SERVER_FILTER_ENABLED=true
            server_side_tags_flag = str(
                os.getenv("SEARCH_TAGS_SERVER_FILTER_ENABLED", "false")
            ).lower() in ("1", "true", "yes")
            requested_tag_norms = []
            if tags:
                for raw_tag in tags:
                    norm = self._normalize_tag(raw_tag)
                    if norm:
                        requested_tag_norms.append(norm)
                        if server_side_tags_flag:
                            filter_dict[f"tag_{norm}"] = True

            # Search Pinecone with vector and optional filters
            results = self.index.query(
                vector=query_embedding, top_k=limit, include_metadata=True, filter=filter_dict
            )

            # Format results (with optional post-filtering for tags)
            products = []
            # Decide if we still need Python post-filtering:
            # If the server-side flag is ON and every match has all requested tag flags, we can skip post-filter.
            # Otherwise (e.g., FakeIndex in tests), we keep the Python post-filter for correctness.
            need_python_post_filter = False
            if tags and requested_tag_norms:
                if server_side_tags_flag:
                    # Peek at matches to see if Pinecone actually enforced flags
                    # If any match is missing any requested flag, keep Python post-filter.
                    for m in results.matches:
                        if not all(bool(m.metadata.get(f"tag_{n}")) for n in requested_tag_norms):
                            need_python_post_filter = True
                            break
                    # If there are no matches, skip post-filter (nothing to filter)
                else:
                    need_python_post_filter = True

            # Use normalized tag comparison for Python post-filtering to match server-side semantics
            for match in results.matches:
                # Extract all metadata fields
                product = {k: v for k, v in match.metadata.items()}

                # Add score from vector similarity
                product["similarity_score"] = float(match.score)

                # Convert tags back to list if present
                if "tags" in product and isinstance(product["tags"], str):
                    product["tags"] = product["tags"].split(",")

                # Apply tags filter (contains all requested tags)
                if need_python_post_filter and requested_tag_norms:
                    product_tags = product.get("tags", [])
                    if isinstance(product_tags, str):
                        product_tags = product_tags.split(",")
                    product_tag_norms = [self._normalize_tag(t) for t in product_tags]
                    if not all(n in product_tag_norms for n in requested_tag_norms):
                        continue

                # Add the document ID
                product["id"] = match.id

                products.append(product)

            logger.info(f"🔍 Found {len(products)} products for query: '{query}'")
            return products

        except Exception as e:
            logger.error(f"❌ Search failed for query '{query}': {e}")
            return []

    # ===== Support document-specific methods =====

    def index_support_docs(self, docs: List[Dict[str, Any]]) -> int:
        """Upsert multiple support documents"""
        if not self.is_available():
            return 0

        successful_upserts = 0
        vectors_to_upsert = []

        for doc in docs:
            try:
                # Create embedding
                embedding = self._get_embedding(doc["content"])
                if not embedding:
                    continue

                # Create unique ID
                doc_id = doc.get("faq_id", str(uuid.uuid4()))

                # Prepare metadata
                metadata = {
                    "type": "support",  # Add type to distinguish from products
                    "doc_type": doc.get("type", ""),
                    "category": doc.get("category", ""),
                    "source": doc.get("source", ""),
                    "content": doc["content"][:1000],  # Limit content size in metadata
                }

                if "product_count" in doc:
                    metadata["product_count"] = doc["product_count"]

                vectors_to_upsert.append({"id": doc_id, "values": embedding, "metadata": metadata})

            except Exception as e:
                logger.error(f"Error preparing document for upsert: {e}")
                continue

        # Batch upsert with v6.x API
        try:
            if vectors_to_upsert:
                self.index.upsert(vectors=vectors_to_upsert)
                successful_upserts = len(vectors_to_upsert)
                logger.info(f"✅ Upserted {successful_upserts} support documents to Pinecone")
        except Exception as e:
            logger.error(f"Error during batch upsert: {e}")

        return successful_upserts

    def search_support(
        self, query: str, top_k: int = 3, filter_dict: Dict = None
    ) -> List[Dict[str, Any]]:
        """Search for relevant support documents"""
        if not self.is_available():
            return []

        try:
            # Create query embedding
            query_embedding = self._get_embedding(query)
            if not query_embedding:
                return []

            # Add type filter to ensure we only get support documents
            if filter_dict is None:
                filter_dict = {"type": "support"}
            else:
                filter_dict["type"] = "support"

            # Search Pinecone with v6.x API
            results = self.index.query(
                vector=query_embedding, top_k=top_k, include_metadata=True, filter=filter_dict
            )

            # Format results
            support_docs = []
            for match in results.matches:
                doc = {
                    "content": match.metadata.get("content", ""),
                    "type": match.metadata.get("doc_type", ""),
                    "category": match.metadata.get("category", ""),
                    "source": match.metadata.get("source", ""),
                    "score": float(match.score),
                    "id": match.id,
                }

                if "product_count" in match.metadata:
                    doc["product_count"] = match.metadata["product_count"]

                support_docs.append(doc)

            return support_docs

        except Exception as e:
            logger.error(f"Error searching support documents: {e}")
            return []

    # ===== Common methods =====

    def get_health(self) -> Dict[str, Any]:
        """Get Pinecone health status"""
        try:
            if not self.is_available():
                return {"status": "unavailable", "message": "Pinecone not connected"}

            stats = self.index.describe_index_stats()

            return {
                "status": "healthy",
                "index_name": self.index_name,
                "index_type": self.index_type,
                "total_vectors": stats.total_vector_count,
                "dimension": stats.dimension,
                "available": True,
            }
        except Exception as e:
            return {"status": "error", "message": str(e), "available": False}

    def clear_index(self, filter_dict: Dict = None) -> bool:
        """
        Clear vectors from the index (use with caution)

        Args:
            filter_dict: Optional filter to only delete specific vectors
                         e.g. {"type": "product"} to only delete products
        """
        if not self.is_available():
            return False

        try:
            if filter_dict:
                # Delete only vectors matching the filter
                self.index.delete(filter=filter_dict)
                logger.info(f"✅ Cleared vectors matching filter {filter_dict} from Pinecone index")
            else:
                # Delete all vectors
                self.index.delete(delete_all=True)
                logger.info(f"✅ Cleared all vectors from Pinecone index {self.index_name}")
            return True
        except Exception as e:
            logger.error(f"Error clearing index: {e}")
            return False


# Factory function to create appropriate client instances
def create_pinecone_client(index_type: str = "products") -> PineconeClient:
    """
    Create a Pinecone client for the specified index type

    Args:
        index_type: Type of index ("products" or "support")

    Returns:
        PineconeClient instance configured for the specified index type
    """
    return PineconeClient(index_type=index_type)


# Global instances for backward compatibility
pinecone_products_client = create_pinecone_client("products")
pinecone_support_client = create_pinecone_client("support")
