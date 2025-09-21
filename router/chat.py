import asyncio
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from common.limiter import maybe_limit
from common.heuristics import get_heuristics
from memory.conversation_memory import conversation_memory
from router.intent_classifier import intent_classifier
from search.product_data_loader import product_data_loader
from services import services
from support_docs.support_loader import SupportLoader

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize support RAG handler (will be properly initialized on startup)
support_loader = None


class ChatMessage(BaseModel):
    message: str
    session_id: str = "default_session"


class ChatResponse(BaseModel):
    response: str
    intent: str
    products: List[Dict[str, Any]] = []
    suggestions: List[str] = []


@router.post("/chat", response_model=ChatResponse)
@maybe_limit("10/minute")
async def process_message(request: Request, chat_message: ChatMessage):
    """Main chat endpoint - processes user message and returns appropriate response"""

    try:
        user_message = chat_message.message
        session_id = chat_message.session_id

        # Track usage for free tier monitoring
        try:
            from datetime import datetime

            redis_client = services.get_redis()
            today = datetime.now().strftime("%Y-%m-%d")
            redis_client.incr(f"daily_requests:{today}")
            redis_client.expire(f"daily_requests:{today}", 86400)  # Expire after 24 hours
        except Exception:
            pass  # Don't fail the request if usage tracking fails

        # Get conversation context
        context = conversation_memory.get_context(session_id)

        # Step 1: Enhanced intent classification (does spelling, price extraction, etc.)
        intent_result = await intent_classifier.classify_intent(user_message, session_id)
        intent = intent_result.get("intent", "SEARCH")

        # Step 2: Route based on intent (pass enhanced intent data)
        if intent == "SEARCH":
            response = await handle_search(user_message, intent_result, session_id)
        elif intent == "RECOMMENDATION":
            response = await handle_recommendation(user_message, intent_result, session_id)
        elif intent == "CART":
            response = await handle_cart(user_message, intent_result, session_id)
        elif intent == "SUPPORT":
            response = await handle_support(user_message, intent_result, session_id)
        elif intent == "COMPARE":
            response = await handle_compare(user_message, intent_result, session_id)
        elif intent == "GREETING":
            response = await handle_greeting(user_message, intent_result, session_id)
        else:
            # Fallback
            response = await handle_search(user_message, intent_result, session_id)

        # Store conversation in memory (Redis)
        conversation_memory.add_message(session_id, user_message, response.response, intent)

        return response

    except Exception as e:
        # Log error with context and stack trace
        logger.error(f"Chat processing error for session {session_id}, message '{message.message[:50]}...': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


async def handle_search(
    user_message: str, intent_result: Dict[str, Any] = None, session_id: str = "default_session"
) -> ChatResponse:
    """Handle product search queries using enhanced intent data"""

    # Load heuristics config (phrases and refine terms)
    heur = get_heuristics()
    phrases_cfg = (heur.get("phrases") or {})
    follow_up_phrases = [str(p).lower() for p in (phrases_cfg.get("follow_up") or [])]

    # Check if this is a follow-up question about previous search results
    user_lower = user_message.lower()
    is_followup = intent_result.get("is_followup", False) or any(phrase in user_lower for phrase in follow_up_phrases)
    
    if is_followup:
        last_results = conversation_memory.get_context_value(session_id, "last_search_results")
        if last_results:
            # Extract which option they're asking about
            referenced_item = intent_result.get("referenced_item")
            
            if referenced_item == "first" or (referenced_item is None and "first" in user_lower):
                product = last_results[0] if len(last_results) > 0 else None
            elif referenced_item == "second" or "second" in user_lower:
                product = last_results[1] if len(last_results) > 1 else None
            elif referenced_item == "third" or "third" in user_lower:
                product = last_results[2] if len(last_results) > 2 else None
            else:
                product = last_results[0] if len(last_results) > 0 else None  # Default to first

            if product:
                # Return detailed info about the specific product
                response = f"The {product['title']} is priced at ${product['price']} with a {product['rating']}/5 rating. {product.get('description', 'No description available.')}"
                return ChatResponse(
                    response=response,
                    intent="SEARCH",
                    products=[product],  # Show just this product
                    suggestions=[],
                )

    # Use the enhanced intent_result directly (no more redundant LLM calls!)
    corrected_query = intent_result.get("corrected_query", user_message)
    key_terms = intent_result.get("key_terms", [])
    price_mentioned = intent_result.get("price_mentioned")
    price_min = intent_result.get("price_min")
    price_max = intent_result.get("price_max")
    # Additional filters extracted by intent classifier
    brand = intent_result.get("brand")
    rating_min = intent_result.get("rating_min")
    in_stock = intent_result.get("in_stock")
    discount_min = intent_result.get("discount_min")
    tags = intent_result.get("tags") or []
    # Map product_type to category if available
    category = None
    try:
        category = (intent_result.get("entities") or {}).get("product_type")
    except Exception:
        category = None
    # Backward-compat: if only price_mentioned was extracted, treat it as a max cap
    if price_min is None and price_max is None and price_mentioned is not None:
        price_max = price_mentioned

    # DEBUG: Initial extracted filters
    logger.debug(
        "search:init_filters session=%s query='%s' key_terms=%s category=%s brand=%s price_min=%s price_max=%s rating_min=%s in_stock=%s discount_min=%s tags=%s",
        session_id,
        corrected_query,
        key_terms,
        category,
        brand,
        price_min,
        price_max,
        rating_min,
        in_stock,
        discount_min,
        tags,
    )

    # Refinement: if user is refining, reuse last query and apply light heuristics
    is_refine = bool(intent_result.get("is_refine"))
    refine_hints = intent_result.get("refine_hints") or []
    last_query = conversation_memory.get_context_value(session_id, "last_search_query")
    last_results = conversation_memory.get_context_value(session_id, "last_search_results") or []
    last_results_baseline = (
        conversation_memory.get_context_value(session_id, "last_search_results_baseline") or []
    )
    if is_refine and last_query:
        # Don't let generic refine words (e.g., "cheaper") become the new search query
        try:
            generic_refine_terms = set(
                str(t).lower() for t in (heur.get("refine_generic_terms") or [])
            )
            ktokens = [str(t).lower() for t in (key_terms or [])]
            if ktokens and all(t in generic_refine_terms for t in ktokens):
                key_terms = []
        except Exception:
            pass
        # If no new key terms, stick with last query as the base
        if not key_terms:
            corrected_query = last_query
        logger.debug(
            "search:refine_start session=%s refine_hints=%s last_query='%s' key_terms=%s",
            session_id,
            refine_hints,
            last_query,
            key_terms,
        )
        # Heuristic: cheaper → cap at min price from prior results when no explicit numeric bound provided
        if ("price_cheaper" in refine_hints) and price_max is None and last_results:
            try:
                prior_prices = [
                    float(p.get("price")) for p in last_results if p.get("price") is not None
                ]
                if prior_prices:
                    min_price = min(prior_prices)
                    if min_price > 0:
                        price_max = min_price
                        logger.debug(
                            "search:refine_cheaper session=%s inferred_price_max=%s",
                            session_id,
                            price_max,
                        )
            except Exception:
                pass
        # Heuristic: higher rating → raise floor slightly above max prior rating when not provided
        if ("rating_higher" in refine_hints) and rating_min is None and last_results:
            try:
                prior_ratings = [
                    float(p.get("rating")) for p in last_results if p.get("rating") is not None
                ]
                if prior_ratings:
                    max_rating = max(prior_ratings)
                    rating_min = min(5.0, round(max_rating + 0.1, 1))
                    logger.debug(
                        "search:refine_rating_higher session=%s prior_max=%s new_rating_min=%s",
                        session_id,
                        max_rating,
                        rating_min,
                    )
            except Exception:
                pass
        # If user asked for higher rating and did not specify a new explicit price bound this turn,
        # clear prior price filters to allow discovering higher-rated options beyond previous price cap.
        if (
            ("rating_higher" in refine_hints)
            and intent_result.get("price_min") is None
            and intent_result.get("price_max") is None
        ):
            price_min = None
            price_max = None
            logger.debug(
                "search:refine_clear_price_bounds session=%s due_to=rating_higher", session_id
            )
        # Heuristic: in stock request
        if ("in_stock" in refine_hints) and in_stock is None:
            in_stock = True
            logger.debug("search:refine_in_stock session=%s enforced_in_stock=True", session_id)
        # Persist brand constraint from last results when refining without an explicit new brand
        # Only infer brand from prior results if there were at least 2 items and they shared a brand.
        # Avoid locking brand based on a single-item prior result.
        if brand is None and last_results and len(last_results) >= 2:
            try:
                last_brands = [str(p.get("brand")).strip() for p in last_results if p.get("brand")]
                lower_set = {b.lower() for b in last_brands if b}
                if len(lower_set) == 1:
                    # Use the canonical capitalization from last_results
                    brand = last_brands[0]
                    logger.debug(
                        "search:refine_persist_brand session=%s brand=%s", session_id, brand
                    )
            except Exception:
                pass

    # Build search terms - prioritize key terms over conversational/last query
    if key_terms:
        # Use key terms if available (better for product search)
        search_terms = " ".join(key_terms)
    else:
        # Fallback to corrected query
        search_terms = corrected_query

    # Search products using Pinecone vector search with price filtering
    # Pass price filters directly to the semantic search function
    logger.debug(
        "search:semantic_query session=%s terms='%s' category=%s brand=%s price_min=%s price_max=%s rating_min=%s in_stock=%s discount_min=%s tags=%s",
        session_id,
        " ".join(key_terms) if key_terms else corrected_query,
        category,
        brand,
        price_min,
        price_max,
        rating_min,
        in_stock,
        discount_min,
        tags,
    )
    filtered_products = product_data_loader.semantic_search_products(
        search_terms,
        limit=20,
        price_min=price_min,
        price_max=price_max,
        brand=brand,
        category=category,
        rating_min=rating_min,
        in_stock=in_stock,
        discount_min=discount_min,
        tags=tags if tags else None,
    )

    # Refine fallback: if refining and re-query yielded nothing, filter previous results in-memory
    if is_refine and not filtered_products and last_results:
        try:
            # Prefer a broader baseline set if available (helps when previous refine narrowed to 1 item)
            base_results = (
                conversation_memory.get_context_value(session_id, "last_search_results_baseline")
                or last_results
            )
            logger.debug(
                "search:fallback_baseline_filter session=%s baseline_size=%s",
                session_id,
                len(base_results) if isinstance(base_results, list) else "n/a",
            )

            def _matches(p: Dict[str, Any]) -> bool:
                # Brand
                if brand and str(p.get("brand", "")).lower() != str(brand).lower():
                    return False
                # Category
                if category and str(p.get("category", "")).lower() != str(category).lower():
                    return False
                # Rating
                try:
                    if rating_min is not None and float(p.get("rating") or 0) < float(rating_min):
                        return False
                except Exception:
                    return False
                # In stock
                if in_stock is True:
                    try:
                        if int(p.get("stock") or 0) <= 0:
                            return False
                    except Exception:
                        return False
                # Discount
                try:
                    if discount_min is not None:
                        if p.get("discountPercentage") is not None:
                            dp = float(p.get("discountPercentage") or 0)
                        else:
                            price_val_num = float(p.get("price", 0) or 0)
                            orig_val = float(p.get("originalPrice", 0) or 0)
                            dp = (
                                ((orig_val - price_val_num) / orig_val * 100.0)
                                if orig_val and orig_val > 0
                                else 0.0
                            )
                        if dp < float(discount_min):
                            return False
                except Exception:
                    return False
                # Price
                try:
                    price_val = float(p.get("price")) if p.get("price") is not None else None
                    if price_min is not None and (price_val is None or price_val < price_min):
                        return False
                    if price_max is not None and (price_val is None or price_val > price_max):
                        return False
                except Exception:
                    return False
                # Tags (require all)
                if tags:
                    prod_tags = p.get("tags") or []
                    prod_norms = set(
                        product_data_loader._normalize_tag(t) for t in prod_tags if t is not None
                    )
                    desired_norms = [
                        product_data_loader._normalize_tag(t) for t in tags if t is not None
                    ]
                    if not all(n and (n in prod_norms) for n in desired_norms):
                        return False
                return True

            filtered_products = [p for p in base_results if _matches(p)]
            logger.debug(
                "search:fallback_baseline_result session=%s matched=%s",
                session_id,
                len(filtered_products),
            )
        except Exception:
            # Keep empty if any error
            filtered_products = []

    # Secondary refine fallback: if still empty, attempt a catalog search constrained by the dominant
    # category from the baseline, using an empty query so numeric filters can apply.
    if is_refine and not filtered_products and last_results:
        try:
            base_results = (
                conversation_memory.get_context_value(session_id, "last_search_results_baseline")
                or last_results
            )
            cats = [
                str(p.get("category") or "").strip().lower()
                for p in base_results
                if p.get("category")
            ]
            uniq = {c for c in cats if c}
            inferred_cat = list(uniq)[0] if len(uniq) == 1 else None
            logger.debug(
                "search:fallback_secondary session=%s inferred_category=%s",
                session_id,
                inferred_cat,
            )
            filtered_products = product_data_loader.search_products(
                query="",
                category=inferred_cat,
                limit=20,
                price_min=price_min,
                price_max=price_max,
                brand=brand,
                rating_min=rating_min,
                in_stock=in_stock,
                discount_min=discount_min,
                tags=tags if tags else None,
            )
            logger.debug(
                "search:fallback_secondary_result session=%s matched=%s",
                session_id,
                len(filtered_products),
            )
        except Exception:
            pass

    # Limit results to 3 for cleaner UI and focused recommendations
    final_products = filtered_products[:3]
    logger.debug("search:final_count session=%s count=%s", session_id, len(final_products))

    # Create analysis data for response generation (simplified)
    search_analysis = {
        "intent_explanation": f"Looking for {search_terms}",
        "is_followup": any(
            word in user_message.lower()
            for word in (phrases_cfg.get("followup_indicators") or [])
        ),
        "key_terms": key_terms,
    }

    # Store last search results in memory for follow-up questions
    if final_products:
        conversation_memory.update_context(session_id, "last_search_results", final_products)
        conversation_memory.update_context(session_id, "last_search_query", search_terms)
        # Maintain a baseline of the broadest results this session to support future refines
        try:
            baseline = conversation_memory.get_context_value(
                session_id, "last_search_results_baseline"
            )
            if not baseline or (len(final_products) > len(baseline)):
                conversation_memory.update_context(
                    session_id, "last_search_results_baseline", final_products
                )
                logger.debug(
                    "search:baseline_updated session=%s new_size=%s old_size=%s",
                    session_id,
                    len(final_products),
                    (len(baseline) if baseline else 0),
                )
        except Exception:
            pass

    # Generate intelligent response using LLM
    if final_products:
        response = await generate_search_response_with_llm(
            user_message, final_products, search_analysis, session_id
        )
        suggestions = []  # No suggestions unless no results
    else:
        response = await generate_no_results_response_with_llm(user_message, search_analysis)
        # Dynamic suggestions to help user recover
        suggestions = []
        if price_min is not None or price_max is not None:
            suggestions.append("Try removing the price filter")
        if price_max is not None:
            suggestions.append(f"Show options under ${int(price_max) + 100}")
        if price_min is not None and price_min > 0:
            suggestions.append(f"Show options above ${int(max(price_min - 100, 0))}")
        # Generic fallbacks
        suggestions.extend(["Browse popular products", "Show me trending"])

    return ChatResponse(
        response=response, intent="SEARCH", products=final_products, suggestions=suggestions
    )


async def handle_greeting(user_message: str, intent_result: Dict, session_id: str = "default_session") -> ChatResponse:
    """Handle greeting and social conversation naturally"""
    
    from memory.conversation_memory import conversation_memory
    from llm.llm_service import llm_service
    import random
    
    # Check if this is mid-conversation or initial greeting
    context = conversation_memory.get_context(session_id)
    last_intent = conversation_memory.get_recent_intent(session_id)
    
    # Initial greeting templates
    initial_greetings = [
        "Hello! I'm Alex, your shopping assistant. I can help you find products, compare options, or answer questions about our items. What are you looking for today?",
        "Hi there! Welcome to our shop. I'm here to help you find the perfect products. Would you like to browse our categories or search for something specific?",
        "Greetings! I'm your shopping buddy. I can help you discover products, compare options, or answer any questions. What can I assist you with today?"
    ]
    
    # Mid-conversation templates
    mid_conversation = [
        "I'm doing great, thanks for asking! Always ready to help you find the perfect products. Were you looking for something specific today?",
        "Thanks for the chat! I'm here to help with your shopping needs. Would you like to continue browsing or search for something new?",
        "It's nice to chat with you! I'm here to assist with your shopping. Is there a particular product category you're interested in?"
    ]
    
    # Choose appropriate response based on context
    if context and last_intent:
        # We're mid-conversation, use a friendly redirect
        response = random.choice(mid_conversation)
        
        # If we have previous product context, reference it
        last_results = conversation_memory.get_context_value(session_id, "last_search_results")
        if last_results:
            product_types = set()
            for product in last_results[:3]:  # Look at first 3 products
                if "category" in product:
                    product_types.add(product["category"])
                elif "category_lc" in product:
                    product_types.add(product["category_lc"])
            
            if product_types:
                product_type = next(iter(product_types))  # Get first product type
                response += f" I see we were looking at {product_type}. Would you like to continue with that?"
    else:
        # Initial greeting
        response = random.choice(initial_greetings)
    
    return ChatResponse(
        response=response,
        intent="GREETING",
        products=[],
        suggestions=["Show me popular products", "What's on sale?", "Help me find a gift"],
    )

async def handle_compare(user_message: str, intent_result: Dict, session_id: str = "default_session") -> ChatResponse:
    """Compare two products from the last search results by ordinal or by approximate name.
    Falls back gracefully if context is missing or ambiguous.
    """
    text = user_message.lower()
    last_results = conversation_memory.get_context_value(session_id, "last_search_results") or []

    if not last_results or len(last_results) < 2:
        return ChatResponse(
            response="I need at least two recent results to compare. Try searching first, then say something like 'compare the first and second'.",
            intent="COMPARE",
            products=[],
            suggestions=["Show me laptops", "Compare the first and second"],
        )

    # 1) Try ordinal extraction (first/second/third or 1st/2nd/3rd)
    import re

    ord_map = {
        "first": 0,
        "1st": 0,
        "one": 0,
        "second": 1,
        "2nd": 1,
        "two": 1,
        "third": 2,
        "3rd": 2,
        "three": 2,
    }
    ordinals = []
    for word, idx in ord_map.items():
        if re.search(rf"\b{re.escape(word)}\b", text):
            ordinals.append(idx)
    ordinals = sorted(set(ordinals))

    idx_a = idx_b = None
    if len(ordinals) >= 2:
        idx_a, idx_b = ordinals[0], ordinals[1]
    elif len(ordinals) == 1:
        idx_a = ordinals[0]

    # 2) Try name-based mentions using simple heuristics (vs/versus or 'compare X and Y')
    name_a = name_b = None
    if idx_a is None or idx_b is None:
        # a) X vs Y pattern
        m = re.search(r"(.+?)\s+(?:vs\.?|versus)\s+(.+)", text)
        if m:
            name_a = m.group(1).strip()
            name_b = m.group(2).strip()
        else:
            # b) compare X and Y
            m2 = re.search(r"compare\s+(.+?)\s+and\s+(.+)", text)
            if m2:
                name_a = m2.group(1).strip()
                name_b = m2.group(2).strip()

    def resolve_by_name(name: str) -> int:
        if not name:
            return None
        name = name.strip()
        best_idx, best_score = None, 0
        for i, p in enumerate(last_results):
            title = (p.get("title") or "").lower()
            # simple token overlap score
            tokens = [t for t in re.split(r"[^a-z0-9]+", name.lower()) if t]
            if not tokens:
                continue
            overlap = sum(1 for t in tokens if t in title)
            # boost if contiguous substring appears
            if name.lower() in title:
                overlap += 2
            if overlap > best_score:
                best_score, best_idx = overlap, i
        return best_idx

    if idx_a is None and name_a:
        idx_a = resolve_by_name(name_a)
    if idx_b is None and name_b:
        idx_b = resolve_by_name(name_b)

    # If still missing a target, default to first two when user clearly asked to compare
    if idx_a is None and idx_b is None and ("compare" in text or "vs" in text or "versus" in text):
        idx_a, idx_b = 0, 1
    elif idx_a is None and idx_b is not None:
        idx_a = 0 if idx_b != 0 else 1
    elif idx_b is None and idx_a is not None:
        idx_b = 1 if idx_a != 1 else 0

    # Validate indices
    if idx_a is None or idx_b is None or idx_a == idx_b:
        return ChatResponse(
            response="Which two should I compare? For example: 'compare the first and second' or 'iPhone vs Pixel'.",
            intent="COMPARE",
            products=[],
            suggestions=["Compare the first and second", "Compare iPhone and Pixel"],
        )

    if idx_a >= len(last_results) or idx_b >= len(last_results):
        return ChatResponse(
            response="I only have a few recent results. Try 'compare the first and second'.",
            intent="COMPARE",
            products=[],
            suggestions=["Compare the first and second"],
        )

    a, b = last_results[idx_a], last_results[idx_b]

    def fmt(p: Dict[str, Any]) -> str:
        brand = p.get("brand") or "—"
        price = p.get("price")
        rating = p.get("rating")
        disc = p.get("discountPercentage")
        stock = int(p.get("stock") or 0)
        stock_str = "in stock" if stock > 0 else "out of stock"
        parts = []
        if price is not None:
            parts.append(f"${price}")
        if rating is not None:
            parts.append(f"{rating}/5")
        if brand and brand != "—":
            parts.append(brand)
        if disc is not None:
            parts.append(f"{int(disc)}% off")
        parts.append(stock_str)
        return ", ".join(parts)

    title_a = a.get("title", "Item A")
    title_b = b.get("title", "Item B")
    summary_a = fmt(a)
    summary_b = fmt(b)

    response = f"Here's a quick comparison: {title_a} vs {title_b}. {title_a}: {summary_a}. {title_b}: {summary_b}."

    return ChatResponse(
        response=response,
        intent="COMPARE",
        products=[a, b],
        suggestions=["Show differences", "Which is better for battery life?"],
    )


async def generate_search_response_with_llm(
    user_message: str, products: List[Dict], search_analysis: Dict, session_id: str
) -> str:
    """Generate natural, contextual response like a helpful human assistant"""

    from llm.llm_service import llm_service
    from memory.conversation_memory import conversation_memory

    # Get conversation context for more natural responses
    context = conversation_memory.get_context(session_id)
    # Sanitize context when we have current results: avoid echoing prior bot apologies/no-results
    sanitized_context = ""
    if context and context.strip():
        try:
            if products:
                # Keep only recent user lines to preserve intent without stale bot messages
                lines = [ln for ln in context.splitlines() if ln.strip().lower().startswith("user:")]
                if lines:
                    sanitized_context = "\n".join(lines)
            else:
                sanitized_context = context
        except Exception:
            sanitized_context = context

    # Analyze the products briefly
    product_names = [p.get("title", "Unknown") for p in products[:3]]
    price_range = f"${min(p.get('price', 0) for p in products[:3])}-${max(p.get('price', 0) for p in products[:3])}"

    # Build contextual prompt
    context_info = ""
    if sanitized_context and len(sanitized_context.strip()) > 0:
        context_info = f"Previous context: {sanitized_context}\n"

    is_followup = search_analysis.get("is_followup", False)
    followup_note = "This seems like a follow-up to our conversation." if is_followup else ""

    prompt = f"""You're a helpful shopping assistant. Respond naturally and conversationally.

{context_info}User asked: "{user_message}"
{followup_note}

I found these products: {', '.join(product_names)}
Price range: {price_range}

Respond like a knowledgeable human assistant would - contextual, helpful, not overly excited. 
Keep it 1-2 sentences. Be natural and conversational, referencing what they asked for specifically.
Avoid generic enthusiasm. Sound professional but approachable.
Do not repeat earlier no-results or apology statements if they appeared before; focus on the current results."""

    try:
        llm_response = await asyncio.to_thread(llm_service._generate_with_llm, prompt)
        if llm_response:
            text = llm_response.strip()
            # Guard: if we have products now, avoid echoing fallback/no-results phrasing
            if products:
                lower = text.lower()
                disallowed = [
                    "couldn't find",
                    "could not find",
                    "can't find",
                    "cannot find",
                    "no results",
                    "no result",
                    "no matches",
                    "no match",
                ]
                if any(p in lower for p in disallowed):
                    return f"Here are some options that match your request: {', '.join(product_names)}. Price range: {price_range}."
            return text
    except:
        pass

    # Natural fallback responses using key terms instead of full query
    key_terms = search_analysis.get("key_terms", [])
    search_subject = " ".join(key_terms) if key_terms else "product"
    if is_followup:
        text = f"Here are some more {search_subject} options. These should work well for what you're looking for."
    else:
        text = f"I found some good {search_subject} options for you. Take a look at these."

    # Apply the same guard for safety
    if products:
        lower = text.lower()
        disallowed = [
            "couldn't find",
            "could not find",
            "can't find",
            "cannot find",
            "no results",
            "no result",
            "no matches",
            "no match",
        ]
        if any(p in lower for p in disallowed):
            return f"Here are some options that match your request: {', '.join(product_names)}. Price range: {price_range}."
    return text


async def generate_no_results_response_with_llm(user_message: str, search_analysis: Dict) -> str:
    """Generate helpful no-results response"""

    from llm.llm_service import llm_service

    prompt = f"""You're a helpful shopping assistant. The user searched for "{user_message}" but I found no matching products.

Respond naturally like a human assistant would when they can't find something. Keep it brief (1 sentence), acknowledge what they searched for, and suggest an alternative approach. Be helpful but not overly apologetic."""

    try:
        llm_response = await asyncio.to_thread(llm_service._generate_with_llm, prompt)
        if llm_response:
            return llm_response.strip()
    except:
        pass

    # Simple, natural fallback
    return f"I couldn't find any '{user_message}' right now. Try a different search term or let me know what specifically you're looking for."


async def handle_recommendation(
    user_message: str, intent_result: Dict[str, Any] = None, session_id: str = "default_session"
) -> ChatResponse:
    """Handle product recommendation requests naturally"""

    from llm.llm_service import llm_service
    from memory.conversation_memory import conversation_memory

    # Get intelligent recommendations (high-rated products)
    products = product_data_loader.get_featured_products(limit=3)

    # Get conversation context for better recommendations
    context = conversation_memory.get_context(session_id)

    # Generate contextual response
    prompt = f"""You're a helpful shopping assistant. The user asked: "{user_message}"

{f"Previous conversation context: {context}" if context and context.strip() else ""}

I have some good product recommendations to show them. Respond naturally in 1-2 sentences like a human assistant would when giving recommendations. Be helpful and conversational, not overly enthusiastic."""

    try:
        llm_response = await asyncio.to_thread(llm_service._generate_with_llm, prompt)
        if llm_response:
            response = llm_response.strip()
        else:
            response = (
                "Here are some popular products I'd recommend. These are well-rated and good value."
            )
    except:
        response = (
            "Here are some popular products I'd recommend. These are well-rated and good value."
        )

    if products:
        suggestions = ["Show me more like these", "What's trending?"]
    else:
        suggestions = []

    return ChatResponse(
        response=response, intent="RECOMMENDATION", products=products, suggestions=suggestions
    )


async def handle_cart(
    user_message: str, intent_result: Dict[str, Any] = None, session_id: str = "default_session"
) -> ChatResponse:
    """Handle cart-related queries naturally"""

    from llm.llm_service import llm_service

    # Generate contextual response about cart limitations
    prompt = f"""You're a helpful shopping assistant. The user asked about cart functionality: "{user_message}"

I don't currently have full cart management features available. Respond naturally in 1-2 sentences explaining this limitation while offering to help them find products instead. Be helpful and straightforward, not overly apologetic."""

    try:
        llm_response = await asyncio.to_thread(llm_service._generate_with_llm, prompt)
        if llm_response:
            response = llm_response.strip()
        else:
            response = "I don't have full cart features yet, but I can help you find products. What are you looking for?"
    except:
        response = "I don't have full cart features yet, but I can help you find products. What are you looking for?"

    suggestions = []

    return ChatResponse(response=response, intent="CART", products=[], suggestions=suggestions)


async def handle_support(
    user_message: str, intent_result: Dict[str, Any] = None, session_id: str = "default_session"
) -> ChatResponse:
    """Handle support and policy queries using real RAG"""

    global support_loader

    # Initialize support loader if not done yet
    if support_loader is None:
        from llm.llm_service import llm_service

        support_loader = SupportLoader(llm_service=llm_service)
        # Try to initialize knowledge base if Pinecone is available
        support_loader.initialize_knowledge_base(use_s3=True)

    # Get response from real RAG system
    try:
        response = await support_loader.handle_support_query(user_message)
    except Exception as e:
        logger.error(f"Error in support RAG for query '{user_message[:50]}...': {e}", exc_info=True)
        response = "I'm here to help with support questions. What specifically would you like to know about?"

    # Lightweight analytics (best-effort, non-fatal)
    try:
        from datetime import datetime

        redis_client = services.get_redis()
        today = datetime.now().strftime("%Y-%m-%d")
        # Totals
        redis_client.incr(f"support:daily:{today}:total")
        # Mode tracking
        mode = getattr(support_loader, "_last_mode", None)
        if mode:
            redis_client.incr(f"support:daily:{today}:mode:{mode}")
        # Citation sources
        citations = getattr(support_loader, "_last_citations", []) or []
        if citations:
            for c in citations:
                if c:
                    redis_client.hincrby(f"support:daily:{today}:source_counts", c, 1)
    except Exception:
        pass

    suggestions = []

    return ChatResponse(response=response, intent="SUPPORT", products=[], suggestions=suggestions)
