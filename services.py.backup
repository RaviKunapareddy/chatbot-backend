"""
Service Connections Management

This module handles connections to external services (Redis, Elasticsearch, Pinecone).

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
from elasticsearch import Elasticsearch
from config import settings
import os
from support_docs.pinecone_client import PineconeSupport

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
    _es_client: Optional[Elasticsearch] = None
    _pinecone_client: Optional[PineconeSupport] = None
    
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
            cls._redis_client = redis.from_url(redis_url, decode_responses=True)
        return cls._redis_client
    
    @classmethod
    def get_elasticsearch(cls) -> Elasticsearch:
        """
        Get Elasticsearch connection.
        
        Note: Current implementation uses single connection.
        Production would:
        - Use connection pool
        - Add automatic reconnection
        - Monitor cluster health
        - Add load balancing
        """
        if not cls._es_client:
            es_host = os.getenv("ELASTICSEARCH_HOST")
            es_port = os.getenv("ELASTICSEARCH_PORT")
            es_api_key = os.getenv("ELASTICSEARCH_API_KEY")
            
            if not es_host:
                raise Exception("ELASTICSEARCH_HOST is required for Elastic Cloud connection")
            if not es_port:
                raise Exception("ELASTICSEARCH_PORT is required for Elastic Cloud connection")
            if not es_api_key:
                raise Exception("ELASTICSEARCH_API_KEY is required for Elastic Cloud connection")
                
            es_url = f"https://{es_host}:{es_port}"
            
            cls._es_client = Elasticsearch(
                es_url,
                api_key=es_api_key,
                verify_certs=True
            )
        return cls._es_client

    @classmethod
    def get_pinecone(cls) -> PineconeSupport:
        """
        Get Pinecone connection for support RAG.
        
        Note: Current implementation uses basic connection.
        Production would:
        - Add connection monitoring
        - Implement retry logic
        - Add error recovery
        """
        if not cls._pinecone_client:
            cls._pinecone_client = PineconeSupport()
            if not cls._pinecone_client.is_available():
                raise Exception("PINECONE_API_KEY is required for Support RAG")
        return cls._pinecone_client
    
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
        
        # Test Elasticsearch connection (required)
        try:
            es = cls.get_elasticsearch()
            es.ping()
            print("✅ Elasticsearch connected successfully")
        except Exception as e:
            raise Exception(f"Elasticsearch connection required but failed: {e}")

        # Test Pinecone connection (required)
        try:
            pinecone = cls.get_pinecone()
            if not pinecone.is_available():
                raise Exception("Pinecone connection failed")
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
        if cls._es_client:
            cls._es_client.close()
        # Pinecone doesn't need explicit cleanup

# Global service connections instance
services = ServiceConnections() 