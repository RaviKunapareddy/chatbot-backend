"""
FastAPI Backend Application

This module serves as the main entry point for the AI chatbot backend.
It handles product data management, search functionality, and chat interactions.

Current Implementation (Production-Ready):
- FastAPI with modern lifespan management
- Redis-powered conversation memory and caching
- Pinecone vector search with semantic search
- Multi-LLM support (AWS Bedrock, Google Gemini)
- Rate limiting and CORS middleware
- Comprehensive logging with daily rotation
- Health checks with service connectivity testing

Architecture:
- Product data loaded from S3 with Pinecone indexing
- Chat routing with intent classification
- Support RAG with knowledge base integration
- Usage monitoring for free tier awareness
"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from common.limiter import is_disabled, limiter
from config import settings
from router.chat import router as chat_router
from search.product_data_loader import product_data_loader
from services import services

# Initialize logger for this module
logger = logging.getLogger(__name__)

# Rate limiting setup (shared limiter instance from common.limiter)


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
        "id": str(product.get("id", "")),
        "title": product.get("title", ""),
        "price": float(product.get("price", 0)),
        "originalPrice": (
            float(product.get("originalPrice", 0)) if product.get("originalPrice") else None
        ),
        "image": product.get("thumbnail", "")
        or (product.get("images", [""])[0] if product.get("images") else ""),
        "rating": float(product.get("rating", 0)) if product.get("rating") else None,
        "reviewCount": len(product.get("reviews", [])) if product.get("reviews") else None,
        "inStock": int(product.get("stock", 0)) > 0,
        "description": product.get("description", ""),
        "brand": product.get("brand", ""),
        "category": product.get("category", ""),
    }


def setup_logging():
    """Setup daily log files with automatic cleanup"""
    # Create logs directory with error handling
    try:
        os.makedirs("logs", exist_ok=True)
        log_dir = "logs"
    except PermissionError:
        # Fallback to current directory if logs directory cannot be created
        print("Warning: Cannot create logs directory, using current directory for logs")
        log_dir = "."
    except Exception as e:
        # Handle any other filesystem errors
        print(f"Warning: Error creating logs directory: {e}, using current directory for logs")
        log_dir = "."

    # Clean up old log files (older than 7 days)
    try:
        cutoff_date = datetime.now() - timedelta(days=7)
        for filename in os.listdir(log_dir):
            if filename.startswith("app_") and filename.endswith(".log"):
                file_path = os.path.join(log_dir, filename)
                file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                if file_time < cutoff_date:
                    os.remove(file_path)
    except Exception as e:
        print(f"Warning: Could not clean up old log files: {e}")

    # Setup daily log file
    today = datetime.now().strftime("%Y-%m-%d")
    log_filename = os.path.join(log_dir, f"app_{today}.log")

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler(),  # Keep console output too
        ],
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI app startup and shutdown.

    Replaces deprecated @app.on_event handlers with modern lifespan pattern.
    """
    # Startup
    # Setup logging first
    setup_logging()

    logger.info(f"🚀 Initializing {settings.PROJECT_NAME} (ID: {settings.PROJECT_ID})...")

    # Validate required cloud credentials
    logger.info("🔍 Validating cloud service credentials...")
    validate_cloud_credentials()

    # Initialize service connections
    services.initialize_all()

    # Load product data
    logger.info("📦 Loading product data and initializing Pinecone vector database...")
    product_data_loader.load_products()

    logger.info("✅ Backend fully initialized")

    yield

    # Shutdown
    services.close_all()


app = FastAPI(
    title=f"{settings.PROJECT_NAME}",
    version="1.0.0",
    description="Production-grade AI chatbot with Redis, Pinecone vector search, and multi-LLM support",
    lifespan=lifespan,
)

# Configure rate limiter (skip in test mode)
if not is_disabled():
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/health", 
         summary="System Health Check",
         description="Comprehensive health monitoring endpoint that validates all cloud service connections",
         response_description="Health status with detailed service connectivity information")
async def health_check():
    """
    **Production Health Monitoring Endpoint**
    
    This endpoint provides comprehensive system health information including:
    - Redis cache connectivity status
    - Pinecone vector database availability  
    - Usage monitoring and free tier tracking
    - Service dependency validation
    
    Perfect for monitoring tools, load balancers, and system administrators.
    """
    service_status = {}
    overall_healthy = True

    # Test Redis connectivity
    try:
        redis_client = services.get_redis()
        redis_client.ping()
        service_status["redis"] = "connected"
    except Exception:
        service_status["redis"] = "failed"
        overall_healthy = False

    # Test Pinecone connectivity (products and support)
    try:
        from vector_service.pinecone_client import pinecone_products_client, pinecone_support_client

        prod_ok = pinecone_products_client.is_available()
        sup_ok = pinecone_support_client.is_available()
        service_status["pinecone_products"] = "connected" if prod_ok else "unavailable"
        service_status["pinecone_support"] = "connected" if sup_ok else "unavailable"
        # Backward compatibility aggregate
        if prod_ok and sup_ok:
            service_status["pinecone"] = "connected"
        else:
            service_status["pinecone"] = "degraded"
            overall_healthy = False
    except Exception:
        service_status["pinecone_products"] = "failed"
        service_status["pinecone_support"] = "failed"
        service_status["pinecone"] = "failed"
        overall_healthy = False

    # Add basic usage monitoring for free tier awareness
    usage_info = {}
    try:
        redis_client = services.get_redis()

        # Get daily request count (for rate limiting awareness)
        today = datetime.now().strftime("%Y-%m-%d")
        daily_requests = redis_client.get(f"daily_requests:{today}") or "0"

        # Get monthly embedding count (for HuggingFace API awareness)
        this_month = datetime.now().strftime("%Y-%m")
        monthly_embeddings = redis_client.get(f"monthly_embeddings:{this_month}") or "0"

        usage_info = {
            "daily_requests": int(daily_requests),
            "monthly_embeddings": int(monthly_embeddings),
            "free_tier_limits": {
                "daily_requests_limit": 14400,  # 10/min * 60 * 24
                "monthly_embeddings_limit": 1000,  # HuggingFace free tier
                "note": "Monitor these to stay within free tier limits",
            },
        }
    except Exception as e:
        logger.error(f"Failed to retrieve usage stats in health check: {e}", exc_info=True)
        usage_info = {"error": "Could not retrieve usage stats", "details": str(e)}

    return {
        "status": "healthy" if overall_healthy else "degraded",
        "project": settings.PROJECT_NAME,
        "project_id": settings.PROJECT_ID,
        "environment": settings.ENVIRONMENT,
        "services": service_status,
        "usage_monitoring": usage_info,
    }


def validate_cloud_credentials():
    """Validate that all required cloud service credentials are present"""
    import os

    required_credentials = {
        "AWS S3": ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "S3_BUCKET_NAME"],
        "Redis Cloud": ["REDIS_HOST"],  # REDIS_URL is alternative
        "HuggingFace Cloud": ["HF_API_KEY"],
        "Pinecone Cloud": ["PINECONE_API_KEY"],
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
        logger.error("❌ Missing required cloud credentials:")
        for cred in missing_credentials:
            logger.error(f"   - {cred}")
        raise Exception("Cloud credentials validation failed. Please check your .env file.")

    logger.info("✅ All cloud credentials validated")


# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS_LIST,  # Driven by ALLOWED_ORIGINS in .env
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
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
            filtered_products = [
                p for p in all_products if p.get("category", "").lower() == category.lower()
            ]
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
            "has_more": end < len(filtered_products),
        }

    except Exception as e:
        logger.error(f"Failed to fetch products with category={category}, limit={limit}, offset={offset}: {e}", exc_info=True)
        return {"error": f"Failed to fetch products: {str(e)}", "products": []}


@app.get("/products/search",
         summary="AI-Powered Product Search",
         description="Semantic search using Pinecone vector database with advanced filtering capabilities",
         response_description="Matching products ranked by semantic similarity and filtered by criteria")
async def search_products(
    q: str,
    limit: int = 10,
    brand: Optional[str] = None,
    category: Optional[str] = None,
    rating_min: Optional[float] = None,
    in_stock: Optional[bool] = None,
    discount_min: Optional[float] = None,
    tags: Optional[str] = None,  # comma-separated list e.g., "gaming,lightweight"
):
    """
    Search products for frontend.

    Note: Current implementation uses Pinecone vector search for product data.
    Production would add:
    - Query validation and sanitization
    - Search result caching
    - Analytics tracking
    - Relevance tuning
    """
    try:
        # Parse tags from comma-separated string
        tags_list: Optional[List[str]] = None
        if tags:
            tags_list = [t.strip() for t in tags.split(",") if t.strip()]

        # Use the same search function as chat with extended filters
        results = product_data_loader.semantic_search_products(
            q,
            limit=limit,
            brand=brand,
            category=category,
            rating_min=rating_min,
            in_stock=in_stock,
            discount_min=discount_min,
            tags=tags_list,
        )

        # Transform to frontend format
        frontend_products = []
        for product in results:
            frontend_product = transform_product_for_frontend(product)
            frontend_products.append(frontend_product)

        return {"products": frontend_products, "query": q, "total": len(frontend_products)}

    except Exception as e:
        logger.error(f"Product search failed for query '{q}' with filters (brand={brand}, category={category}): {e}", exc_info=True)
        return {"error": f"Search failed: {str(e)}", "products": []}


if __name__ == "__main__":
    # Make port configurable from environment (default 8000)
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
