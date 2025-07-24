"""
Elasticsearch Hybrid Search Client

This module replaces the Pinecone vector search with Elasticsearch's built-in
hybrid search that combines BM25 (keyword) + vector similarity automatically.
"""

import os
import json
from typing import List, Dict, Any, Optional
from elasticsearch import Elasticsearch
import requests
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class ElasticsearchClient:
    """Handles hybrid search using Elasticsearch (BM25 + Vector combined)"""
    
    def __init__(self):
        self.client = None
        self.hf_api_key = os.getenv("HF_API_KEY")
        self.hf_model = os.getenv("HF_PRODUCT_MODEL", "BAAI/bge-small-en-v1.5")
        # Use direct models API for feature extraction
        self.hf_api_url = f"https://api-inference.huggingface.co/models/{self.hf_model}"
        self.index_name = os.getenv("ELASTICSEARCH_INDEX", "products")
        self.available = False
        
        self._init_elasticsearch()
        
    def _init_elasticsearch(self):
        """Initialize Elasticsearch connection (API key, HTTPS) - cloud-only configuration"""
        try:
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
            
            self.client = Elasticsearch(
                es_url,
                api_key=es_api_key,
                verify_certs=True
            )
            
            # Test connection
            if self.client.ping():
                self.available = True
                logger.info("✅ Elasticsearch connected successfully")
            else:
                raise Exception("Elasticsearch ping failed")
                
        except Exception as e:
            logger.error(f"❌ Elasticsearch connection failed: {e}")
            raise Exception(f"Elasticsearch connection required but failed: {e}")

    def _get_embedding(self, text: str) -> List[float]:
        """Get embedding from Hugging Face API"""
        try:
            headers = {"Authorization": f"Bearer {self.hf_api_key}"}
            response = requests.post(
                self.hf_api_url,
                headers=headers,
                json={"inputs": [text]}  # Correct format: array of strings
            )
            
            if response.status_code == 200:
                embeddings = response.json()
                if isinstance(embeddings, list) and len(embeddings) > 0:
                    return embeddings[0]  # First (and only) embedding
                else:
                    logger.error(f"Unexpected embedding format: {embeddings}")
                    return None
            else:
                logger.error(f"Failed to get embedding: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error getting embedding: {e}")
            return None

    def create_index(self):
        """Create the products index with hybrid search mapping"""
        mapping = {
            "mappings": {
                "properties": {
                    "id": {"type": "keyword"},
                    "title": {
                        "type": "text",
                        "analyzer": "standard",
                        "search_analyzer": "standard"
                    },
                    "description": {
                        "type": "text", 
                        "analyzer": "standard"
                    },
                    "category": {
                        "type": "keyword",
                        "fields": {
                            "text": {"type": "text"}
                        }
                    },
                    "brand": {"type": "keyword"},
                    "price": {"type": "float"},
                    "rating": {"type": "float"},
                    "tags": {"type": "keyword"},
                    "embedding": {
                        "type": "dense_vector",
                        "dims": 384,  # all-MiniLM-L6-v2 dimension
                        "index": True,
                        "similarity": "cosine"
                    },
                    "searchable_text": {
                        "type": "text",
                        "analyzer": "standard"
                    }
                }
            },
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "analysis": {
                    "analyzer": {
                        "standard": {
                            "type": "standard"
                        }
                    }
                }
            }
        }
        
        try:
            if self.client.indices.exists(index=self.index_name):
                logger.info(f"Index {self.index_name} already exists")
                return True
                
            self.client.indices.create(index=self.index_name, body=mapping)
            logger.info(f"✅ Created index: {self.index_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create index: {e}")
            return False
    
    def index_products(self, products: List[Dict[str, Any]]):
        """Index products with embeddings for hybrid search"""
        if not self.available:
            logger.warning("Elasticsearch not available")
            return False
            
        try:
            actions = []
            for product in products:
                # Create searchable text combining title, description, category
                searchable_text = f"{product.get('title', '')} {product.get('description', '')} {product.get('category', '')}"
                
                # Generate embedding using Hugging Face API
                embedding = self._get_embedding(searchable_text)
                if not embedding:
                    logger.warning(f"Skipping product {product.get('id')} - failed to generate embedding")
                    continue
                
                # Prepare document
                doc = {
                    "_index": self.index_name,
                    "_id": str(product.get("id")),
                    "_source": {
                        "id": product.get("id"),
                        "title": product.get("title", ""),
                        "description": product.get("description", ""),
                        "category": product.get("category", ""),
                        "brand": product.get("brand", ""),
                        "price": float(product.get("price", 0)),
                        "rating": float(product.get("rating", 0)),
                        "tags": product.get("tags", []),
                        "embedding": embedding,
                        "searchable_text": searchable_text,
                        # Keep all original fields
                        **product
                    }
                }
                actions.append(doc)
            
            # Bulk index
            from elasticsearch.helpers import bulk
            success, failed = bulk(self.client, actions, index=self.index_name)
            
            logger.info(f"✅ Indexed {success} products, {len(failed)} failed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to index products: {e}")
            return False
    
    def hybrid_search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Perform hybrid search combining BM25 (keyword) + vector similarity
        This is the main search method that replaces Pinecone
        """
        if not self.available:
            logger.warning("Elasticsearch not available, returning empty results")
            return []
        
        try:
            # Generate query embedding using Hugging Face API
            query_embedding = self._get_embedding(query)
            if not query_embedding:
                logger.error("Failed to generate query embedding")
                return []
            
            # Hybrid search query combining BM25 + vector
            search_body = {
                "size": limit,
                "query": {
                    "bool": {
                        "should": [
                            # BM25 text matching
                            {
                                "multi_match": {
                                    "query": query,
                                    "fields": ["title^2", "description", "category.text", "searchable_text"],
                                    "type": "best_fields",
                                    "boost": 1.0
                                }
                            },
                            # Vector similarity
                            {
                                "script_score": {
                                    "query": {"match_all": {}},
                                    "script": {
                                        "source": "cosineSimilarity(params.query_vector, 'embedding') + 1.0",
                                        "params": {"query_vector": query_embedding}
                                    },
                                    "boost": 1.0
                                }
                            }
                        ],
                        "minimum_should_match": 1
                    }
                },
                "_source": {
                    "excludes": ["embedding"]  # Don't return embeddings in results
                }
            }
            
            response = self.client.search(index=self.index_name, body=search_body)
            
            # Convert to expected format
            results = []
            for hit in response['hits']['hits']:
                product = hit['_source']
                product['similarity_score'] = hit['_score']
                results.append(product)
            
            logger.info(f"🔍 Found {len(results)} products for query: '{query}'")
            return results
            
        except Exception as e:
            logger.error(f"❌ Search failed for query '{query}': {e}")
            return []
    
    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Main search method - calls hybrid_search"""
        return self.hybrid_search(query, limit)
    
    def get_health(self) -> Dict[str, Any]:
        """Get Elasticsearch health status"""
        try:
            if not self.available:
                return {"status": "unavailable", "message": "Elasticsearch not connected"}
            
            health = self.client.cluster.health()
            count = self.client.count(index=self.index_name)
            
            return {
                "status": "healthy",
                "cluster_status": health.get("status"),
                "indexed_products": count.get("count", 0),
                "available": True
            }
        except Exception as e:
            return {"status": "error", "message": str(e), "available": False}

# Global instance
elasticsearch_client = ElasticsearchClient() 