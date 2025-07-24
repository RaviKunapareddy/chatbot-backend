from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
from search.product_data_loader import product_data_loader
from router.intent_classifier import intent_classifier
from memory.conversation_memory import conversation_memory
from support_docs.support_loader import SupportLoader

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
async def process_message(chat_message: ChatMessage):
    """Main chat endpoint - processes user message and returns appropriate response"""
    
    try:
        user_message = chat_message.message
        session_id = chat_message.session_id
    
        
        # Get conversation context
        context = conversation_memory.get_context(session_id)
        
        # Step 1: Enhanced intent classification (does spelling, price extraction, etc.)
        intent_result = await intent_classifier.classify_intent(user_message)
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
        else:
            # Fallback
            response = await handle_search(user_message, intent_result, session_id)
        
        # Store conversation in memory (Redis)
        conversation_memory.add_message(session_id, user_message, response.response, intent)
        
        return response
            
    except Exception as e:
        # Log error instead of printing
        import logging
        logging.error(f"Chat processing error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

async def handle_search(user_message: str, intent_result: Dict[str, Any] = None, session_id: str = "default_session") -> ChatResponse:
    """Handle product search queries using enhanced intent data"""
    
    # Check if this is a follow-up question about previous search results
    user_lower = user_message.lower()
    if any(phrase in user_lower for phrase in ['first option', 'second option', 'third option', 'tell me about', 'more about']):
        last_results = conversation_memory.get_context_value(session_id, "last_search_results")
        if last_results:
            # Extract which option they're asking about
            if 'first' in user_lower:
                product = last_results[0] if len(last_results) > 0 else None
            elif 'second' in user_lower:
                product = last_results[1] if len(last_results) > 1 else None
            elif 'third' in user_lower:
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
                    suggestions=[]
                )
    
    # Use the enhanced intent_result directly (no more redundant LLM calls!)
    corrected_query = intent_result.get("corrected_query", user_message)
    key_terms = intent_result.get("key_terms", [])
    price_mentioned = intent_result.get("price_mentioned")
    
    # Build search terms - prioritize key terms over conversational query
    if key_terms:
        # Use key terms if available (better for product search)
        search_terms = ' '.join(key_terms)
    else:
        # Fallback to corrected query
        search_terms = corrected_query
    
    # Search products using Elasticsearch hybrid search
    all_products = product_data_loader.semantic_search_products(search_terms, limit=20)
    
    # Apply price filters if mentioned
    filtered_products = []
    for product in all_products:
        price = float(product.get('price', 0))
        
        # Apply price filter if user mentioned a price
        if price_mentioned and price > price_mentioned:
            continue
            
        filtered_products.append(product)
    
    # Limit results to 3 for cleaner UI and focused recommendations
    final_products = filtered_products[:3]
    
    # Create analysis data for response generation (simplified)
    search_analysis = {
        "intent_explanation": f"Looking for {search_terms}",
        "is_followup": any(word in user_message.lower() for word in ['more', 'other', 'different', 'cheaper', 'better', 'similar']),
        "key_terms": key_terms
    }
    
    # Store last search results in memory for follow-up questions
    if final_products:
        conversation_memory.update_context(session_id, "last_search_results", final_products)
        conversation_memory.update_context(session_id, "last_search_query", search_terms)
    
    # Generate intelligent response using LLM
    if final_products:
        response = await generate_search_response_with_llm(user_message, final_products, search_analysis)
        suggestions = []  # No suggestions unless no results
    else:
        response = await generate_no_results_response_with_llm(user_message, search_analysis)
        suggestions = ["Browse smartphones", "Show me trending"]
    
    return ChatResponse(
        response=response,
        intent="SEARCH",
        products=final_products,
        suggestions=suggestions
    )



async def generate_search_response_with_llm(user_message: str, products: List[Dict], search_analysis: Dict) -> str:
    """Generate natural, contextual response like a helpful human assistant"""
    
    from llm.llm_service import llm_service
    from memory.conversation_memory import conversation_memory
    
    # Get conversation context for more natural responses
    context = conversation_memory.get_context("default_session")
    
    # Analyze the products briefly
    product_names = [p.get('title', 'Unknown') for p in products[:3]]
    price_range = f"${min(p.get('price', 0) for p in products[:3])}-${max(p.get('price', 0) for p in products[:3])}"
    
    # Build contextual prompt
    context_info = ""
    if context and len(context.strip()) > 0:
        context_info = f"Previous context: {context}\n"
    
    is_followup = search_analysis.get('is_followup', False)
    followup_note = "This seems like a follow-up to our conversation." if is_followup else ""
    
    prompt = f"""You're a helpful shopping assistant. Respond naturally and conversationally.

{context_info}User asked: "{user_message}"
{followup_note}

I found these products: {', '.join(product_names)}
Price range: {price_range}

Respond like a knowledgeable human assistant would - contextual, helpful, not overly excited. 
Keep it 1-2 sentences. Be natural and conversational, referencing what they asked for specifically.
Avoid generic enthusiasm. Sound professional but approachable."""

    try:
        llm_response = await llm_service._generate_with_llm(prompt)
        if llm_response:
            return llm_response.strip()
    except:
        pass
    
    # Natural fallback responses using key terms instead of full query
    key_terms = search_analysis.get('key_terms', [])
    search_subject = ' '.join(key_terms) if key_terms else "product"
    if is_followup:
        return f"Here are some more {search_subject} options. These should work well for what you're looking for."
    else:
        return f"I found some good {search_subject} options for you. Take a look at these."

async def generate_no_results_response_with_llm(user_message: str, search_analysis: Dict) -> str:
    """Generate helpful no-results response"""
    
    from llm.llm_service import llm_service
    
    prompt = f"""You're a helpful shopping assistant. The user searched for "{user_message}" but I found no matching products.

Respond naturally like a human assistant would when they can't find something. Keep it brief (1 sentence), acknowledge what they searched for, and suggest an alternative approach. Be helpful but not overly apologetic."""

    try:
        llm_response = await llm_service._generate_with_llm(prompt)
        if llm_response:
            return llm_response.strip()
    except:
        pass
    
    # Simple, natural fallback
    return f"I couldn't find any '{user_message}' right now. Try a different search term or let me know what specifically you're looking for."

async def handle_recommendation(user_message: str, intent_result: Dict[str, Any] = None, session_id: str = "default_session") -> ChatResponse:
    """Handle product recommendation requests naturally"""
    
    from llm.llm_service import llm_service
    from memory.conversation_memory import conversation_memory
    
    # Get intelligent recommendations (high-rated products)
    products = product_data_loader.get_featured_products(limit=3)
    
    # Get conversation context for better recommendations
    context = conversation_memory.get_context("default_session")
    
    # Generate contextual response
    prompt = f"""You're a helpful shopping assistant. The user asked: "{user_message}"

{f"Previous conversation context: {context}" if context and context.strip() else ""}

I have some good product recommendations to show them. Respond naturally in 1-2 sentences like a human assistant would when giving recommendations. Be helpful and conversational, not overly enthusiastic."""
    
    try:
        llm_response = await llm_service._generate_with_llm(prompt)
        if llm_response:
            response = llm_response.strip()
        else:
            response = "Here are some popular products I'd recommend. These are well-rated and good value."
    except:
        response = "Here are some popular products I'd recommend. These are well-rated and good value."
    
    if products:
        suggestions = ["Show me more like these", "What's trending?"]
    else:
        suggestions = []
    
    return ChatResponse(
        response=response,
        intent="RECOMMENDATION", 
        products=products,
        suggestions=suggestions
    )

async def handle_cart(user_message: str, intent_result: Dict[str, Any] = None, session_id: str = "default_session") -> ChatResponse:
    """Handle cart-related queries naturally"""
    
    from llm.llm_service import llm_service
    
    # Generate contextual response about cart limitations
    prompt = f"""You're a helpful shopping assistant. The user asked about cart functionality: "{user_message}"

I don't currently have full cart management features available. Respond naturally in 1-2 sentences explaining this limitation while offering to help them find products instead. Be helpful and straightforward, not overly apologetic."""
    
    try:
        llm_response = await llm_service._generate_with_llm(prompt)
        if llm_response:
            response = llm_response.strip()
        else:
            response = "I don't have full cart features yet, but I can help you find products. What are you looking for?"
    except:
        response = "I don't have full cart features yet, but I can help you find products. What are you looking for?"
    
    suggestions = []
    
    return ChatResponse(
        response=response,
        intent="CART",
        products=[],
        suggestions=suggestions
    )

async def handle_support(user_message: str, intent_result: Dict[str, Any] = None, session_id: str = "default_session") -> ChatResponse:
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
        print(f"Error in support RAG: {e}")
        response = "I'm here to help with support questions. What specifically would you like to know about?"
    
    suggestions = []
    
    return ChatResponse(
        response=response,
        intent="SUPPORT",
        products=[],
        suggestions=suggestions
    ) 