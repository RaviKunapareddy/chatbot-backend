"""
Service Connections Management

This module handles connections to external services (Redis, Pinecone).

Current Implementation (Demo):
- Static service connections suitable for demo load
- Basic error handling
- Simple connection management

Production Considerations:
- Implement connection pooling
- Add connection health monitoring
- Add automatic reconnection
- Implement circuit breakers
"""

from typing import Optional
import redis
from config import settings
import os
from vector_service.pinecone_client import PineconeClient, pinecone_products_client, pinecone_support_client

class ServiceConnections:
    """
    Manages service connections for the application.
    
    Note: Current implementation uses static connections.
    Production would:
    - Use connection pools
    - Implement retry mechanisms
    - Add connection lifecycle management
    - Monitor connection health
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
            from urllib.parse import quote
            import os
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
                redis_url, 
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
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
        Initialize all service connections.
        
        Note: Current implementation uses simple initialization.
        Production would:
        - Add health check retries
        - Implement graceful degradation
        - Add startup logging
        - Monitor initialization time
        """
        # Test Redis connection
        try:
            redis = cls.get_redis()
            redis.ping()
            print("✅ Redis connected successfully")
        except Exception as e:
            print(f"⚠️ Redis connection failed: {e}")
        
        # Test Pinecone Products connection (required)
        try:
            pinecone_products = cls.get_pinecone_products()
            if not pinecone_products.is_available():
                raise Exception("Pinecone Products connection failed")
            print("✅ Pinecone Products Search connected successfully")
        except Exception as e:
            raise Exception(f"Pinecone Products connection required but failed: {e}")

        # Test Pinecone Support connection (required)
        try:
            pinecone_support = cls.get_pinecone_support()
            if not pinecone_support.is_available():
                raise Exception("Pinecone Support connection failed")
            print("✅ Pinecone Support RAG connected successfully")
        except Exception as e:
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