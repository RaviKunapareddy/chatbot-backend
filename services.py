"""
Service Connections Management

This module handles connections to external services (Redis, Pinecone).

Current Implementation (Production-Ready):
- Singleton pattern for efficient connection management
- Flexible Redis configuration (URL or component-based)
- Lazy initialization with connection validation
- Graceful error handling and cleanup

Architecture:
- Redis: Optional service (graceful degradation if unavailable)
- Pinecone Products: Required service (fail-fast if unavailable)
- Pinecone Support: Required service (fail-fast if unavailable)
"""

import logging
from typing import Optional

import redis

# Initialize logger for this module
logger = logging.getLogger(__name__)

from vector_service.pinecone_client import (
    PineconeClient,
    pinecone_products_client,
    pinecone_support_client,
)


class ServiceConnections:
    """
    Manages service connections for the application using singleton pattern.

    Production-Ready Features:
    - Singleton pattern prevents connection proliferation
    - Lazy initialization creates connections only when needed
    - Flexible Redis configuration (REDIS_URL or component-based)
    - Connection validation with health checks
    - Graceful error handling per service criticality
    - Proper resource cleanup during shutdown

    Service Architecture:
    - Redis: Optional (graceful degradation if unavailable)
    - Pinecone Products: Required (fail-fast if unavailable)  
    - Pinecone Support: Required (fail-fast if unavailable)
    """

    _redis_client: Optional[redis.Redis] = None
    _pinecone_support_client: Optional[PineconeClient] = None
    _pinecone_products_client: Optional[PineconeClient] = None

    @classmethod
    def get_redis(cls) -> redis.Redis:
        """
        Get Redis connection with project-specific database.

        Note: Current implementation uses single connection.
        Production would:
        - Use connection pool
        - Add retry logic
        - Monitor connection health
        - Implement circuit breaker
        """
        if not cls._redis_client:
            import os
            from urllib.parse import quote

            redis_url = os.getenv("REDIS_URL")
            if not redis_url:
                host = os.getenv("REDIS_HOST")
                port = os.getenv("REDIS_PORT", "6379")
                db = os.getenv("REDIS_DB", "0")
                username = os.getenv("REDIS_USERNAME", "default")
                password = os.getenv("REDIS_PASSWORD", "")
                encoded_pw = quote(password)
                redis_url = f"redis://{username}:{encoded_pw}@{host}:{port}/{db}"
            cls._redis_client = redis.from_url(
                redis_url, decode_responses=True, socket_timeout=5, socket_connect_timeout=5
            )
        return cls._redis_client

    @classmethod
    def get_pinecone_products(cls) -> PineconeClient:
        """
        Get Pinecone connection for product search.

        Note: Current implementation uses basic connection.
        Production would:
        - Add connection monitoring
        - Implement retry logic
        - Add error recovery
        """
        if not cls._pinecone_products_client:
            cls._pinecone_products_client = pinecone_products_client
            if not cls._pinecone_products_client.is_available():
                raise Exception("PINECONE_API_KEY is required for Product Search")
        return cls._pinecone_products_client

    @classmethod
    def get_pinecone_support(cls) -> PineconeClient:
        """
        Get Pinecone connection for support RAG.

        Note: Current implementation uses basic connection.
        Production would:
        - Add connection monitoring
        - Implement retry logic
        - Add error recovery
        """
        if not cls._pinecone_support_client:
            cls._pinecone_support_client = pinecone_support_client
            if not cls._pinecone_support_client.is_available():
                raise Exception("PINECONE_API_KEY is required for Support RAG")
        return cls._pinecone_support_client

    @classmethod
    def initialize_all(cls):
        """
        Initialize all service connections with different criticality levels.

        Service Architecture & Error Handling:
        - Redis (Optional): Conversation memory - warns if down, continues with degraded UX
        - Pinecone (Required): Product search - fails fast if down, prevents broken experience

        This approach ensures users get working core functionality even with partial outages.
        When Redis is down: Users lose chat history but can still search products
        When Pinecone is down: App won't start (better than serving broken search)
        """
        # Test Redis connection (Optional Service - Graceful Degradation)
        try:
            redis = cls.get_redis()
            redis.ping()
            logger.info("✅ Redis connected successfully")
        except Exception as e:
            logger.warning(f"⚠️ Redis connection failed: {e}")
            logger.info("📋 Continuing with degraded functionality (no conversation memory)")

        # Test Pinecone Products connection (Required Service - Fail Fast)
        try:
            pinecone_products = cls.get_pinecone_products()
            if not pinecone_products.is_available():
                raise Exception("Pinecone Products connection failed")
            logger.info("✅ Pinecone Products Search connected successfully")
        except Exception as e:
            logger.error("🚨 Critical service failure - chatbot cannot function without product search")
            raise Exception(f"Pinecone Products connection required but failed: {e}")

        # Test Pinecone Support connection (Required Service - Fail Fast)
        try:
            pinecone_support = cls.get_pinecone_support()
            if not pinecone_support.is_available():
                raise Exception("Pinecone Support connection failed")
            logger.info("✅ Pinecone Support RAG connected successfully")
        except Exception as e:
            logger.error("🚨 Critical service failure - chatbot cannot function without support RAG")
            raise Exception(f"Pinecone Support RAG connection required but failed: {e}")

    @classmethod
    def close_all(cls):
        """
        Close all service connections.

        Note: Current implementation handles basic cleanup.
        Production would:
        - Ensure graceful shutdown
        - Wait for in-flight requests
        - Log connection closure
        - Monitor shutdown time
        """
        if cls._redis_client:
            cls._redis_client.close()
        # Pinecone doesn't need explicit cleanup


# Global service connections instance
services = ServiceConnections()
