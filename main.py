"""
FastAPI Backend Application

This module serves as the main entry point for the AI chatbot backend.
It handles product data management, search functionality, and chat interactions.

Current Implementation (Demo):
- Single instance deployment
- In-memory product data suitable for demo scale
- Static service connections
- Basic error handling and logging

Production Considerations:
- Implement connection pooling for high concurrency
- Add Redis caching for product data
- Add proper logging and monitoring
- Implement rate limiting and security measures
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from typing import Dict, Any
from router.chat import router as chat_router
from search.product_data_loader import product_data_loader
from config import settings
from services import services

def transform_product_for_frontend(product: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform backend product to frontend-friendly format.
    
    Note: Current implementation handles basic product attributes.
    Production would add:
    - Image CDN integration
    - Price formatting by locale
    - Inventory status validation
    """
    return {
        "id": str(product.get('id', '')),
        "title": product.get('title', ''),
        "price": float(product.get('price', 0)),
        "originalPrice": float(product.get('originalPrice', 0)) if product.get('originalPrice') else None,
        "image": product.get('thumbnail', '') or (product.get('images', [''])[0] if product.get('images') else ''),
        "rating": float(product.get('rating', 0)) if product.get('rating') else None,
        "reviewCount": int(product.get('reviews', [{'rating': 0}])[0].get('rating', 0)) if product.get('reviews') else None,
        "inStock": int(product.get('stock', 0)) > 0,
        "description": product.get('description', ''),
        "brand": product.get('brand', ''),
        "category": product.get('category', '')
    }

app = FastAPI(
    title=f"{settings.PROJECT_NAME}", 
    version="1.0.0",
    description="Production-grade AI chatbot with Redis, Elasticsearch hybrid search, and multi-LLM support"
)

@app.get("/health")
async def health_check():
    """
    Health check endpoint for container orchestration.
    
    Note: Current implementation checks basic service status.
    Production would add:
    - Deep health checks for all services
    - Memory usage metrics
    - Response time monitoring
    """
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "project_id": settings.PROJECT_ID,
        "environment": settings.ENVIRONMENT
    }

@app.on_event("startup")
async def startup_event():
    """
    Initialize services and load data.
    
    Cloud-only configuration with comprehensive validation.
    """
    print(f"🚀 Initializing {settings.PROJECT_NAME} (ID: {settings.PROJECT_ID})...")
    
    # Validate required cloud credentials
    print("🔍 Validating cloud service credentials...")
    validate_cloud_credentials()
    
    # Initialize service connections
    services.initialize_all()
    
    # Load product data
    print("📦 Loading product data and initializing vector store...")
    product_data_loader.load_products()
    
    print("✅ Backend fully initialized")

def validate_cloud_credentials():
    """Validate that all required cloud service credentials are present"""
    import os
    
    required_credentials = {
        "AWS S3": ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "S3_BUCKET_NAME"],
        "Elasticsearch Cloud": ["ELASTICSEARCH_HOST", "ELASTICSEARCH_PORT", "ELASTICSEARCH_API_KEY"],
        "Redis Cloud": ["REDIS_HOST"],  # REDIS_URL is alternative
        "HuggingFace Cloud": ["HF_API_KEY"],
        "Pinecone Cloud": ["PINECONE_API_KEY"]
    }
    
    missing_credentials = []
    
    for service, credentials in required_credentials.items():
        for credential in credentials:
            if not os.getenv(credential):
                # Special case for Redis - either REDIS_URL or REDIS_HOST is required
                if credential == "REDIS_HOST" and os.getenv("REDIS_URL"):
                    continue
                missing_credentials.append(f"{service}: {credential}")
    
    if missing_credentials:
        print("❌ Missing required cloud credentials:")
        for cred in missing_credentials:
            print(f"   - {cred}")
        raise Exception("Cloud credentials validation failed. Please check your .env file.")
    
    print("✅ All cloud credentials validated")

@app.on_event("shutdown")
async def shutdown_event():
    """
    Cleanup service connections.
    
    Note: Current implementation handles basic cleanup.
    Production would:
    - Ensure graceful shutdown
    - Wait for ongoing requests
    - Cleanup cache entries
    """
    services.close_all()

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include chat router
app.include_router(chat_router, tags=["chat"])

@app.get("/products")
async def get_products(limit: int = 50, offset: int = 0, category: str = None):
    """
    Get products for frontend display.
    
    Note: Current implementation uses in-memory filtering.
    Production would:
    - Add Redis caching
    - Implement database filtering
    - Add field selection
    - Add sorting options
    """
    try:
        all_products = product_data_loader.products
        
        # Filter by category if provided
        if category:
            filtered_products = [p for p in all_products if p.get('category', '').lower() == category.lower()]
        else:
            filtered_products = all_products
        
        # Apply pagination
        start = offset
        end = start + limit
        products_page = filtered_products[start:end]
        
        # Transform to frontend-friendly format
        frontend_products = []
        for product in products_page:
            frontend_product = transform_product_for_frontend(product)
            frontend_products.append(frontend_product)
        
        return {
            "products": frontend_products,
            "total": len(filtered_products),
            "limit": limit,
            "offset": offset,
            "has_more": end < len(filtered_products)
        }
        
    except Exception as e:
        return {"error": f"Failed to fetch products: {str(e)}", "products": []}

@app.get("/products/search")
async def search_products(q: str, limit: int = 10):
    """
    Search products for frontend.
    
    Note: Current implementation uses Elasticsearch for demo.
    Production would add:
    - Query validation and sanitization
    - Search result caching
    - Analytics tracking
    - Relevance tuning
    """
    try:
        # Use the same search function as chat
        results = product_data_loader.semantic_search_products(q, limit=limit)
        
        # Transform to frontend format
        frontend_products = []
        for product in results:
            frontend_product = transform_product_for_frontend(product)
            frontend_products.append(frontend_product)
        
        return {
            "products": frontend_products,
            "query": q,
            "total": len(frontend_products)
        }
        
    except Exception as e:
        return {"error": f"Search failed: {str(e)}", "products": []}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 