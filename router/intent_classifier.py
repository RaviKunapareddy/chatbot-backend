import json
import logging
import os
from typing import Any, Dict

import difflib
import boto3
import google.generativeai as genai
from dotenv import load_dotenv
from search.product_data_loader import product_data_loader
from common.heuristics import build_category_synonyms_for_allowed, get_heuristics

load_dotenv()
logger = logging.getLogger(__name__)


class IntentClassifier:
    def __init__(self):
        self.aws_available = False
        self.gemini_available = False

        # Initialize AWS Bedrock (Primary)
        self._init_aws_bedrock()

        # Initialize Google Gemini (Fallback)
        self._init_gemini()

        # Status summary - use logging instead of print
        if self.aws_available:
            logger.info("AWS Bedrock ready (Primary)")
        elif self.gemini_available:
            logger.info("Google Gemini ready (Fallback)")
        else:
            logger.warning("Using keyword-based classification (Final fallback)")

    def _tokenize_for_fuzzy(self, text: str, min_len: int) -> list[str]:
        try:
            import re
            toks = re.findall(r"[a-z0-9&\-]+", (text or "").lower())
            return [t for t in toks if len(t) >= max(1, int(min_len or 1))]
        except Exception:
            return []

    def _best_fuzzy_candidate(self, candidates: list[str], tokens: list[str], full_text: str) -> tuple[dict | None, int, int]:
        """Return (best_candidate_info, best_score, second_best_score).
        best_candidate_info is {"value": original_candidate, "value_lower": lower} or None.
        Scores are integer percentages 0..100, computed via difflib ratio.
        Candidate score is max over tokens and full_text.
        """
        try:
            def ratio(a: str, b: str) -> int:
                try:
                    return int(round(difflib.SequenceMatcher(None, a, b).ratio() * 100))
                except Exception:
                    return 0

            best = None
            best_score = -1
            second = -1
            ft = (full_text or "").lower()
            for c in candidates or []:
                try:
                    cl = str(c).strip().lower()
                    if not cl:
                        continue
                    # score against full text and tokens
                    s = ratio(cl, ft) if ft else 0
                    for t in tokens or []:
                        s = max(s, ratio(cl, t))
                    if s > best_score:
                        second = best_score
                        best_score = s
                        best = {"value": c, "value_lower": cl}
                    elif s > second:
                        second = s
                except Exception:
                    continue
            return best, (best_score if best_score >= 0 else 0), (second if second >= 0 else 0)
        except Exception:
            return None, 0, 0

    def _init_aws_bedrock(self):
        """Initialize AWS Bedrock client"""
        aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

        if (
            aws_access_key
            and aws_secret_key
            and aws_access_key != "your_aws_access_key_here"
            and aws_secret_key != "your_aws_secret_access_key_here"
        ):

            try:
                self.bedrock_client = boto3.client(
                    "bedrock-runtime",
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key,
                    region_name=aws_region,
                )
                self.aws_model_id = os.getenv(
                    "AWS_BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0"
                )
                self.aws_available = True

            except Exception as e:
                logger.error(f"AWS Bedrock initialization failed for intent classification: {e}", exc_info=True)
                self.aws_available = False

    def _init_gemini(self):
        """Initialize Google Gemini client"""
        google_api_key = os.getenv("GOOGLE_API_KEY")

        if google_api_key and google_api_key != "your_google_api_key_here":
            try:
                genai.configure(api_key=google_api_key)
                self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
                self.gemini_client = genai.GenerativeModel(self.gemini_model)
                self.gemini_available = True

            except Exception as e:
                logger.error(f"Google Gemini initialization failed for intent classification: {e}", exc_info=True)
                self.gemini_available = False

    async def classify_intent(self, user_message: str, session_id: str = "default_session") -> Dict[str, Any]:
        """Classify user intent: AWS Bedrock → Gemini → Keyword fallback"""
        # Test/runtime override: allow forcing keyword-based fallback regardless of LLM availability
        try:
            if str(os.getenv("FORCE_KEYWORD_FALLBACK", "")).strip() == "1":
                logger.info("FORCE_KEYWORD_FALLBACK=1: Using keyword-based classification (forced)")
                result = self._fallback_classification(user_message)
                # Add price extraction
                result = self._enhance_with_price_extraction(user_message, result)
                # Add additional filter extraction (brand, rating_min, in_stock, discount_min, tags)
                result = self._enhance_with_additional_filters(user_message, result)
                # Detect refine intent markers
                result = self._enhance_with_refine_detection(user_message, result)
                return result
        except Exception:
            # If any error in checking the override, proceed with normal flow
            pass

        # Try AWS Bedrock first (Primary)
        if self.aws_available:
            result = await self._classify_with_bedrock(user_message, session_id)
            if result:
                # Add price extraction
                result = self._enhance_with_price_extraction(user_message, result)
                # Add additional filter extraction (brand, rating_min, in_stock, discount_min, tags)
                result = self._enhance_with_additional_filters(user_message, result)
                # Detect refine intent markers (session-aware application happens in chat handler)
                result = self._enhance_with_refine_detection(user_message, result)
                return result

        # Try Google Gemini (Fallback)
        if self.gemini_available:
            result = await self._classify_with_gemini(user_message, session_id)
            if result:
                # Add price extraction
                result = self._enhance_with_price_extraction(user_message, result)
                # Add additional filter extraction (brand, rating_min, in_stock, discount_min, tags)
                result = self._enhance_with_additional_filters(user_message, result)
                # Detect refine intent markers
                result = self._enhance_with_refine_detection(user_message, result)
                return result

        # Final fallback to keyword-based
        logger.info("Using keyword-based classification (final fallback)")
        result = self._fallback_classification(user_message)
        # Add price extraction
        result = self._enhance_with_price_extraction(user_message, result)
        # Add additional filter extraction (brand, rating_min, in_stock, discount_min, tags)
        result = self._enhance_with_additional_filters(user_message, result)
        # Detect refine intent markers
        result = self._enhance_with_refine_detection(user_message, result)
        return result

    async def _classify_with_bedrock(self, user_message: str, session_id: str = "default_session") -> Dict[str, Any]:
        """Classify using AWS Bedrock with enhanced follow-up detection"""
        try:
            # Get conversation context for follow-up detection
            from memory.conversation_memory import conversation_memory
            context = conversation_memory.get_context(session_id)
            
            # Derive allowed sets from catalog
            allowed_categories_list = product_data_loader.get_categories()
            allowed_brands_list = product_data_loader.get_brands()
            allowed_categories = json.dumps(allowed_categories_list)
            allowed_brands = json.dumps(allowed_brands_list)

            # Include conversation context if available
            context_section = ""
            if context and context.strip():
                context_section = f"Previous conversation:\n{context}\n\n"
                
            prompt_content = f"""You are an intent classifier for an e-commerce chatbot. 
Classify this message into one of these intents:

1. SEARCH - Find/browse products OR ask about specific products (e.g., "show me laptops", "tell me about the first option", "can you tell me about that product")
2. CART - Cart operations (e.g., "add to cart", "remove item", "view cart")  
3. RECOMMENDATION - Product suggestions (e.g., "recommend me a phone", "what's trending")
4. SUPPORT - Help with policies ONLY (e.g., "return policy", "shipping info", "warranty", "contact support")
5. COMPARE - Compare two results from the last shown list or by name (e.g., "compare the first and second", "iphone vs pixel")
6. GREETING - General greetings or social conversation (e.g., "hi", "hello", "how are you", "good morning", "what's up")

IMPORTANT: Questions about specific products (like "tell me about the first option" or "can you tell me about that product") are SEARCH, not SUPPORT.

{context_section}Allowed product categories (closed set): {allowed_categories}
Allowed brands (closed set): {allowed_brands}

User message: "{user_message}"

Respond with ONLY valid JSON:
{{
    "intent": "SEARCH|CART|RECOMMENDATION|SUPPORT|COMPARE|GREETING",
    "confidence": 0.0-1.0,
    "is_followup": true/false,
    "referenced_item": "first"/"second"/"third"/null,
    "entities": {{
        "product_type": "one of the allowed product categories or null if unknown",
        "brand": "one of the allowed brands or null if unknown",
        "action": "specific action if any",
        "keywords": ["relevant", "keywords"]
    }}
}}"""

            # Different body format based on model type
            if "claude" in self.aws_model_id:
                # Claude Messages API format (new)
                body = json.dumps(
                    {
                        "messages": [
                            {"role": "user", "content": [{"type": "text", "text": prompt_content}]}
                        ],
                        "max_tokens": 200,
                        "temperature": 0.1,
                        "anthropic_version": "bedrock-2023-05-31",
                    }
                )
            elif "llama" in self.aws_model_id:
                # Llama format
                body = json.dumps(
                    {"prompt": prompt_content, "max_gen_len": 200, "temperature": 0.1}
                )
            elif "titan" in self.aws_model_id:
                # Titan format
                body = json.dumps(
                    {
                        "inputText": prompt_content,
                        "textGenerationConfig": {"maxTokenCount": 200, "temperature": 0.1},
                    }
                )
            elif "nova" in self.aws_model_id:
                # Nova format
                body = json.dumps(
                    {
                        "messages": [{"role": "user", "content": [{"text": prompt_content}]}],
                        "inferenceConfig": {"maxTokens": 200, "temperature": 0.1},
                    }
                )
            else:
                # Default to Claude Messages API
                body = json.dumps(
                    {
                        "messages": [
                            {"role": "user", "content": [{"type": "text", "text": prompt_content}]}
                        ],
                        "max_tokens": 200,
                        "temperature": 0.1,
                        "anthropic_version": "bedrock-2023-05-31",
                    }
                )

            response = self.bedrock_client.invoke_model(modelId=self.aws_model_id, body=body)

            # Parse response body
            response_body = json.loads(response["body"].read())

            # Extract text based on model type
            if "claude" in self.aws_model_id:
                # Claude Messages API response format
                content = response_body.get("content", [])
                result_text = content[0].get("text", "") if content else ""
            elif "llama" in self.aws_model_id:
                result_text = response_body.get("generation", "")
            elif "titan" in self.aws_model_id:
                results = response_body.get("results", [])
                result_text = results[0].get("outputText", "") if results else ""
            elif "nova" in self.aws_model_id:
                # Nova response format
                output = response_body.get("output", {})
                message = output.get("message", {})
                content = message.get("content", [])
                result_text = content[0].get("text", "") if content else ""
            else:
                # Default to Claude Messages API
                content = response_body.get("content", [])
                result_text = content[0].get("text", "") if content else ""

            # Clean up the response and parse JSON
            result_text = result_text.strip()
            if result_text.startswith("```json"):
                result_text = result_text.replace("```json", "").replace("```", "").strip()

            intent_data = json.loads(result_text)

            # Extract follow-up detection fields
            is_followup = intent_data.get("is_followup", False)
            referenced_item = intent_data.get("referenced_item")
            
            # Canonicalize closed-set fields and expose brand at top-level
            entities = intent_data.get("entities") or {}
            def _canon(val: Any, allowed: list) -> Any:
                try:
                    if val is None:
                        return None
                    v = str(val).strip().lower()
                    for a in allowed:
                        if v == str(a).strip().lower():
                            return a
                    return None
                except Exception:
                    return None

            product_type = _canon(entities.get("product_type"), allowed_categories_list)
            brand_val = entities.get("brand") or intent_data.get("brand")
            brand_canon = _canon(brand_val, allowed_brands_list)

            entities["product_type"] = product_type
            entities["brand"] = brand_canon
            intent_data["entities"] = entities
            if brand_canon:
                intent_data["brand"] = brand_canon
            else:
                intent_data.pop("brand", None)
                
            # Add follow-up detection fields to the result
            intent_data["is_followup"] = is_followup
            intent_data["referenced_item"] = referenced_item

            logger.info(
                f"Bedrock classified: {intent_data['intent']} (confidence: {intent_data['confidence']}) is_followup: {is_followup}"
            )
            return intent_data

        except Exception as e:
            logger.error(f"Bedrock intent classification error for query '{prompt[:50]}...': {e}", exc_info=True)
            return None

    async def _classify_with_gemini(self, user_message: str, session_id: str = "default_session") -> Dict[str, Any]:
        """Classify using Google Gemini with enhanced follow-up detection"""
        try:
            # Get conversation context for follow-up detection
            from memory.conversation_memory import conversation_memory
            context = conversation_memory.get_context(session_id)
            
            # Derive allowed sets from catalog
            allowed_categories_list = product_data_loader.get_categories()
            allowed_brands_list = product_data_loader.get_brands()
            allowed_categories = json.dumps(allowed_categories_list)
            allowed_brands = json.dumps(allowed_brands_list)

            # Include conversation context if available
            context_section = ""
            if context and context.strip():
                context_section = f"Previous conversation:\n{context}\n\n"
                
            prompt = f"""You are an intent classifier for an e-commerce chatbot. 
Classify this message into one of these intents:

1. SEARCH - Find/browse products OR ask about specific products (e.g., "show me laptops", "tell me about the first option", "can you tell me about that product")
2. CART - Cart operations (e.g., "add to cart", "remove item", "view cart")  
3. RECOMMENDATION - Product suggestions (e.g., "recommend me a phone", "what's trending")
4. SUPPORT - Help with policies ONLY (e.g., "return policy", "shipping info", "warranty", "contact support")
5. COMPARE - Compare two results from the last shown list or by name (e.g., "compare the first and second", "iphone vs pixel")
6. GREETING - General greetings or social conversation (e.g., "hi", "hello", "how are you", "good morning", "what's up")

IMPORTANT: Questions about specific products (like "tell me about the first option" or "can you tell me about that product") are SEARCH, not SUPPORT.

{context_section}Allowed product categories (closed set): {allowed_categories}
Allowed brands (closed set): {allowed_brands}

User message: "{user_message}"

Respond with ONLY valid JSON:
{{
    "intent": "SEARCH|CART|RECOMMENDATION|SUPPORT|COMPARE|GREETING",
    "confidence": 0.0-1.0,
    "is_followup": true/false,
    "referenced_item": "first"/"second"/"third"/null,
    "entities": {{
        "product_type": "one of the allowed product categories or null if unknown",
        "brand": "one of the allowed brands or null if unknown",
        "action": "specific action if any",
        "keywords": ["relevant", "keywords"]
    }}
}}"""

            response = self.gemini_client.generate_content(prompt)
            result_text = response.text.strip()

            # Clean up the response and parse JSON
            if result_text.startswith("```json"):
                result_text = result_text.replace("```json", "").replace("```", "").strip()

            intent_data = json.loads(result_text)

            # Extract follow-up detection fields
            is_followup = intent_data.get("is_followup", False)
            referenced_item = intent_data.get("referenced_item")
            
            # Canonicalize closed-set fields and expose brand at top-level (mirror Bedrock)
            entities = intent_data.get("entities") or {}

            def _canon(val: Any, allowed: list) -> Any:
                try:
                    if val is None:
                        return None
                    v = str(val).strip().lower()
                    for a in allowed:
                        if v == str(a).strip().lower():
                            return a
                    return None
                except Exception:
                    return None

            product_type = _canon(entities.get("product_type"), allowed_categories_list)
            brand_val = entities.get("brand") or intent_data.get("brand")
            brand_canon = _canon(brand_val, allowed_brands_list)

            entities["product_type"] = product_type
            entities["brand"] = brand_canon
            intent_data["entities"] = entities
            if brand_canon:
                intent_data["brand"] = brand_canon
            else:
                intent_data.pop("brand", None)
                
            # Add follow-up detection fields to the result
            intent_data["is_followup"] = is_followup
            intent_data["referenced_item"] = referenced_item

            logger.info(
                f"Gemini classified: {intent_data['intent']} (confidence: {intent_data['confidence']}) is_followup: {is_followup}"
            )
            return intent_data

        except Exception as e:
            logger.error(f"Gemini intent classification error for query '{prompt[:50]}...': {e}", exc_info=True)
            return None

    def _fallback_classification(self, user_message: str) -> Dict[str, Any]:
        """Keyword-based classification (final fallback)"""
        message_lower = user_message.lower()

        # Enhanced keyword matching with priority order
        heur = get_heuristics()
        intent_kws = heur.get("intent_keywords", {}) or {}
        cart_keywords = intent_kws.get("cart", [])
        support_keywords = intent_kws.get("support", [])
        recommendation_keywords = intent_kws.get("recommendation", [])
        search_keywords = intent_kws.get("search", [])
        compare_keywords = intent_kws.get("compare", [])
        
        # Define greeting keywords
        greeting_keywords = ["hi", "hello", "hey", "greetings", "good morning", "good afternoon", "good evening", "howdy", "how are you", "what's up"]

        # Check for greetings first
        if len(message_lower.split()) <= 5 and any(word in message_lower for word in greeting_keywords):
            intent = "GREETING"
        # Check for follow-up questions about products (most specific for context)
        elif any(
            phrase in message_lower
            for phrase in [
                "tell me about",
                "about the",
                "first option",
                "second option",
                "third option",
                "more details",
                "more info",
            ]
        ):
            intent = "SEARCH"
        # Check compare intent
        elif any(word in message_lower for word in compare_keywords):
            intent = "COMPARE"
        # Check cart
        elif any(word in message_lower for word in cart_keywords):
            intent = "CART"
        # Check support (only for actual policy questions)
        elif any(word in message_lower for word in support_keywords) and not any(
            phrase in message_lower for phrase in ["about the", "tell me about"]
        ):
            intent = "SUPPORT"
        # Check for explicit recommendation requests
        elif any(word in message_lower for word in recommendation_keywords):
            intent = "RECOMMENDATION"
        # Check for explicit search terms
        elif any(word in message_lower for word in search_keywords):
            intent = "SEARCH"
        # If just product names or general queries, default to search
        else:
            intent = "SEARCH"

        # Extract potential product type using dynamic catalog categories
        product_type = None
        try:
            allowed_categories_list = product_data_loader.get_categories()
        except Exception:
            allowed_categories_list = []

        # First: direct substring match against canonical categories from catalog
        for c in allowed_categories_list:
            try:
                cl = str(c).strip().lower()
                if cl and cl in message_lower:
                    product_type = c
                    break
            except Exception:
                pass

        # Second: configured synonym mapping (fallback_config/heuristics.json) -> canonical category
        if product_type is None:
            try:
                syn_map = build_category_synonyms_for_allowed(allowed_categories_list)
                for syn_key, canonical in syn_map.items():
                    try:
                        if syn_key and syn_key in message_lower:
                            product_type = canonical
                            break
                    except Exception:
                        pass
            except Exception:
                pass

        # Third: conservative fuzzy category match (fallback only) guarded by flags/thresholds
        if product_type is None:
            try:
                thresholds = heur.get("thresholds", {}) or {}
                flags = heur.get("feature_flags", {}) or {}
                if flags.get("fallback_fuzzy_category", False) and allowed_categories_list:
                    min_tok = int(thresholds.get("min_token_length", 3) or 3)
                    tokens = self._tokenize_for_fuzzy(user_message, min_tok)
                    best, best_score, second_score = self._best_fuzzy_candidate(
                        allowed_categories_list, tokens, user_message
                    )
                    cutoff = int(thresholds.get("fuzzy_similarity_category", 90) or 90)
                    margin = int(thresholds.get("fuzzy_unambiguous_margin", 3) or 3)  # separation to avoid ties
                    if best and best_score >= cutoff and (best_score - second_score) >= margin:
                        product_type = best["value"]
                        logger.info(
                            f"Fuzzy category match applied: '{best['value']}' ({best_score}%)"
                        )
            except Exception:
                pass

        # Note: no additional built-in synonyms here; rely on direct catalog matches and
        # config-driven synonyms from fallback_config/heuristics.json via build_category_synonyms_for_allowed().

        return {
            "intent": intent,
            "confidence": 0.8,
            "entities": {
                "product_type": product_type,
                "action": None,
                "keywords": [word for word in message_lower.split()[:5] if len(word) > 2],
            },
            "_source": "fallback",
        }

    def _enhance_with_price_extraction(
        self, user_message: str, intent_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract price information from user message"""
        import re

        text = user_message.lower()
        price_min = None
        price_max = None
        price_mentioned = None

        # 1) Explicit ranges like "$300-$500"
        m = re.search(r"\$?\s*(\d{2,6})\s*[-–]\s*\$?\s*(\d{2,6})", text)
        if m:
            a, b = float(m.group(1)), float(m.group(2))
            price_min, price_max = (min(a, b), max(a, b))
            price_mentioned = price_max

        # 2) Between X and Y / From X to Y
        if price_min is None and price_max is None:
            m = re.search(r"(?:between|from)\s+\$?(\d{2,6})\s+(?:and|to)\s+\$?(\d{2,6})", text)
            if m:
                a, b = float(m.group(1)), float(m.group(2))
                price_min, price_max = (min(a, b), max(a, b))
                price_mentioned = price_max

        # 3) Upper bounds: under/less than/below/up to/max/at most
        if price_max is None:
            m = re.search(r"(?:under|less\s+than|below|up\s+to|max|at\s+most)\s+\$?(\d{2,6})", text)
            if m:
                price_max = float(m.group(1))
                price_mentioned = price_max

        # 4) Lower bounds: over/more than/above/at least/minimum
        if price_min is None:
            m = re.search(r"(?:over|more\s+than|above|at\s+least|minimum)\s+\$?(\d{2,6})", text)
            if m:
                price_min = float(m.group(1))
                price_mentioned = price_min

        # 5) Around/about/approximately ~X => +/- 20%
        if price_min is None and price_max is None:
            m = re.search(r"(?:around|about|approximately|~)\s*\$?(\d{2,6})", text)
            if m:
                center = float(m.group(1))
                delta = center * 0.2
                price_min, price_max = center - delta, center + delta
                price_mentioned = center

        # Backward-compatible fields and enhanced keys
        intent_result["price_mentioned"] = price_mentioned
        intent_result["price_min"] = price_min
        intent_result["price_max"] = price_max
        intent_result["corrected_query"] = user_message
        intent_result["key_terms"] = intent_result.get("entities", {}).get("keywords", [])

        return intent_result

    def _enhance_with_additional_filters(
        self, user_message: str, intent_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract additional product filters from the user message.
        Adds: brand, rating_min, in_stock, discount_min, tags (list)
        """
        import re

        text = user_message.strip()
        lower = text.lower()

        heur = get_heuristics()
        phrases = heur.get("phrases", {}) or {}
        rating_patterns = heur.get("rating_patterns", []) or []
        discount_patterns = heur.get("discount_patterns", []) or []
        generic_nouns_list = heur.get("generic_nouns", []) or []
        generic_nouns = {str(n).strip().lower() for n in generic_nouns_list}

        # Initialize
        brand = None
        rating_min = None
        in_stock = None
        discount_min = None
        tags = []

        # If LLM already provided a brand, prefer it and do not override via heuristics
        try:
            brand_from_llm = (
                (intent_result.get("entities") or {}).get("brand") or intent_result.get("brand")
            )
            if brand_from_llm:
                brand = str(brand_from_llm).strip()
        except Exception:
            pass

        # Brand extraction heuristics
        # Patterns: "brand: Apple", "by Apple", "from Apple"
        # Keep brand as the next word(s) up to punctuation
        if brand is None:
            m = re.search(
                r"\bbrand\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9 &\-]{0,40})", text, flags=re.IGNORECASE
            )
            if m:
                brand = m.group(1).strip().rstrip(".,!")
                # Minimal cleanup: stop at common connectors to avoid trailing phrases
                import re as _re

                brand = _re.split(r"\s+(?:with)\b|[,\.!]", brand, maxsplit=1)[0].strip()
                # Trim generic product nouns (e.g., "Samsung phones" -> "Samsung")
                _parts = brand.split()
                if len(_parts) > 1 and _parts[1].lower() in generic_nouns:
                    brand = _parts[0]
        if brand is None:
            m = re.search(
                r"\b(?:by|from)\s+([A-Za-z][A-Za-z0-9 &\-]{1,40})", text, flags=re.IGNORECASE
            )
            if m:
                brand = m.group(1).strip().rstrip(".,!")
                # Minimal cleanup: stop at common connectors to avoid trailing phrases
                import re as _re

                brand = _re.split(r"\s+(?:with)\b|[,\.!]", brand, maxsplit=1)[0].strip()
                # Trim generic product nouns
                _parts = brand.split()
                if len(_parts) > 1 and _parts[1].lower() in generic_nouns:
                    brand = _parts[0]

        # Additional heuristic: "only <brand>" (common refine phrasing)
        if brand is None:
            m = re.search(r"\bonly\s+([A-Za-z][A-Za-z0-9 &\-]{1,40})", text, flags=re.IGNORECASE)
            if m:
                cand = m.group(1).strip().rstrip(".,!")
                # Stop at connectors
                import re as _re

                cand = _re.split(r"\s+(?:with|and|or)\b|[,\.!]", cand, maxsplit=1)[0].strip()
                # Trim generic product nouns (e.g., "Apple phones" -> "Apple")
                _parts = cand.split()
                if len(_parts) > 1 and _parts[1].lower() in generic_nouns:
                    cand = _parts[0]
                brand = cand if cand else None

        # Heuristic: infer brand from patterns like "Apple smartphones", "Samsung phones", etc.
        if brand is None:
            try:
                m = re.search(
                    r"\b([A-Z][A-Za-z0-9&\-]{1,40})\s+(?:phones?|smartphones?|laptops?|watches?)\b",
                    text,
                )
                if m:
                    brand = m.group(1).strip()
            except Exception:
                pass

        # Rating min extraction: patterns loaded from config
        for p in rating_patterns:
            m = re.search(p, lower)
            if m:
                try:
                    rating_min = float(m.group(1))
                    break
                except:
                    pass

        # In-stock extraction using configured phrases
        in_stock_phrases = phrases.get("in_stock", [])
        out_of_stock_phrases = phrases.get("out_of_stock", [])
        if any(kw in lower for kw in in_stock_phrases):
            in_stock = True
        if any(kw in lower for kw in out_of_stock_phrases):
            in_stock = False

        # Discount extraction using configured patterns
        for p in discount_patterns:
            m = re.search(p, lower)
            if m:
                try:
                    discount_min = float(m.group(1))
                    break
                except:
                    pass

        # Tags extraction: hashtags like #gaming, #lightweight or phrases after "with" listing features
        tags = re.findall(r"#([a-z0-9\-]+)", lower)
        # Very light heuristic for features after "with" e.g., "with leather strap, waterproof"
        # We'll split by commas and take 1-3 concise tokens as tags if reasonable
        if not tags:
            m = re.search(r"\bwith\s+([^\.;\n]+)", lower)
            if m:
                feature_str = m.group(1)
                for chunk in re.split(r"[,/]|\band\b", feature_str):
                    t = chunk.strip()
                    # Keep short, single or hyphenated words without spaces
                    if 2 <= len(t) <= 20 and " " not in t:
                        tags.append(t)
        # Deduplicate while preserving order
        seen = set()
        tags = [t for t in tags if not (t in seen or seen.add(t))]

        # Canonicalize brand against catalog-derived closed set
        try:
            if brand:
                allowed_brands_list = product_data_loader.get_brands()
                brand_lower = str(brand).strip().lower()
                for b in allowed_brands_list:
                    try:
                        if brand_lower == str(b).strip().lower():
                            brand = b
                            break
                    except Exception:
                        pass
        except Exception:
            pass

        # Conservative fuzzy brand match (fallback-only) guarded by flags/thresholds
        try:
            heur = heur  # reuse
            flags = heur.get("feature_flags", {}) or {}
            thresholds = heur.get("thresholds", {}) or {}
            if (
                flags.get("fallback_fuzzy_brand", False)
                and intent_result.get("_source") == "fallback"
            ):
                # Ensure we have the candidate set
                try:
                    allowed_brands_list
                except NameError:
                    allowed_brands_list = product_data_loader.get_brands()
                if allowed_brands_list:
                    min_tok = int(thresholds.get("min_token_length", 3) or 3)
                    tokens = self._tokenize_for_fuzzy(user_message, min_tok)
                    # Prefer explicit brand substring if present; else use tokens
                    # Compute best against existing explicit 'brand' (if any) as well
                    token_pool = tokens.copy()
                    if brand and str(brand).strip():
                        token_pool.append(str(brand).strip().lower())
                    best, best_score, second_score = self._best_fuzzy_candidate(
                        allowed_brands_list, token_pool, user_message
                    )
                    cutoff = int(thresholds.get("fuzzy_similarity_brand", 90) or 90)
                    margin = int(thresholds.get("fuzzy_unambiguous_margin", 3) or 3)
                    # Only set brand if not already canonicalized to an allowed brand
                    already_canonical = False
                    try:
                        if brand:
                            bl = str(brand).strip().lower()
                            for b in allowed_brands_list:
                                if bl == str(b).strip().lower():
                                    already_canonical = True
                                    break
                    except Exception:
                        pass
                    if not already_canonical and best and best_score >= cutoff and (best_score - second_score) >= margin:
                        brand = best["value"]
                        logger.info(
                            f"Fuzzy brand match applied: '{best['value']}' ({best_score}%)"
                        )
        except Exception:
            pass

        # Populate into intent_result
        intent_result["brand"] = brand
        intent_result["rating_min"] = rating_min
        intent_result["in_stock"] = in_stock
        intent_result["discount_min"] = discount_min
        if tags:
            intent_result["tags"] = tags
        else:
            intent_result.setdefault("tags", [])

        return intent_result

    def _enhance_with_refine_detection(
        self, user_message: str, intent_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Annotate with refine markers. Actual refine application is session-aware and done in chat handler.
        Triggers:
        - Price refines: cheaper, under/less than/below/up to, over/more than/at least.
        - Constraint refines: only <brand/category>, in stock.
        - Quality refines: higher rating, better rated.
        """
        import re

        text = user_message.lower()
        hints = []

        if any(w in text for w in ["cheaper", "less expensive", "lower price", "more affordable"]):
            hints.append("price_cheaper")
        if re.search(r"(?:under|less\s+than|below|up\s+to|max|at\s+most)\s+\$?\d", text):
            hints.append("price_upper_bound")
        if re.search(r"(?:over|more\s+than|above|at\s+least|minimum)\s+\$?\d", text):
            hints.append("price_lower_bound")
        if re.search(r"\bonly\b", text):
            hints.append("constraint_only")
        if any(w in text for w in ["higher rating", "better rated", "more stars"]):
            hints.append("rating_higher")
        if any(w in text for w in ["in stock", "available now", "instock"]):
            hints.append("in_stock")

        intent_result["is_refine"] = len(hints) > 0
        if hints:
            intent_result["refine_hints"] = hints
        else:
            intent_result.setdefault("refine_hints", [])

        return intent_result


# Global instance
intent_classifier = IntentClassifier()
