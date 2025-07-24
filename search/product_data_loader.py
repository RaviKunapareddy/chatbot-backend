"""
Data Loading and Management

This module handles:
- Product data loading from S3
- Category extraction and management
- Semantic search integration with vector store
- Product filtering and recommendations
"""

import json
import os
from typing import List, Dict, Any, Optional
from data.s3_client import s3_client

class ProductDataLoader:
    """Handles product data loading and search operations"""
    
    def __init__(self):
        self.products = []
        self.categories = set()
        self._llm_service = None
    
    @property
    def llm_service(self):
        """Lazy load LLM service to avoid circular imports"""
        if self._llm_service is None:
            from llm.llm_service import llm_service
            self._llm_service = llm_service
        return self._llm_service
    
    def load_products(self) -> List[Dict[str, Any]]:
        """Load products from S3"""
        try:
            # Load products from S3
            self.products = s3_client.load_products()
            
            # Extract categories
            self.categories = {product.get('category', 'Unknown') for product in self.products}
            
            # Optionally store in Elasticsearch for semantic search (if available)
            try:
                from search.elasticsearch_client import elasticsearch_client
                if elasticsearch_client.available:
                    elasticsearch_client.create_index()
                    elasticsearch_client.index_products(self.products)
                    print(f"✅ Products indexed in Elasticsearch for hybrid search")
            except Exception as e:
                print(f"⚠️ Elasticsearch indexing failed (will use keyword search): {e}")
            
            print(f"✅ Loaded {len(self.products)} products")
            return self.products
            
        except Exception as e:
            print(f"❌ Error loading products: {e}")
            return []
    
    def get_products(self) -> List[Dict[str, Any]]:
        """Get all loaded products"""
        if not self.products:
            self.load_products()
        return self.products
    
    def get_categories(self) -> List[str]:
        """Get all available categories"""
        if not self.categories:
            self.load_products()
        return sorted(list(self.categories))
    
    def search_products(self, query: str, category: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Basic keyword search for products"""
        if not self.products:
            self.load_products()
        
        results = []
        query_lower = query.lower()
        
        for product in self.products:
            # Category filter
            if category and product.get('category', '').lower() != category.lower():
                continue
            
            # Search in title and description
            title = product.get('title', '').lower()
            description = product.get('description', '').lower()
            
            if query_lower in title or query_lower in description:
                results.append(product)
            
            if len(results) >= limit:
                break
        
        return results
    
    def semantic_search_products(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Advanced semantic search using Elasticsearch or fallback to keyword search"""
        if not self.products:
            self.load_products()
        
        # Try Elasticsearch hybrid search first (if available)
        try:
            from search.elasticsearch_client import elasticsearch_client
            if elasticsearch_client.available:
                results = elasticsearch_client.hybrid_search(query, limit=limit)
                if results:
                    return results
        except Exception as e:
            print(f"⚠️ Elasticsearch search failed, falling back to keyword search: {e}")
        
        # Fallback to basic keyword search
        print(f"🔄 Using keyword search fallback for: '{query}'")
        results = self.search_products(query, limit=limit)
        
        # Ensure we have similarity scores for ranking consistency
        for i, result in enumerate(results):
            if 'similarity_score' not in result:
                # Assign decreasing scores for fallback results
                result['similarity_score'] = 1.0 - (i * 0.1)

        return results
    
    def get_products_by_category(self, category: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get products from specific category"""
        if not self.products:
            self.load_products()
        
        results = []
        for product in self.products:
            if product.get('category', '').lower() == category.lower():
                results.append(product)
                if len(results) >= limit:
                    break
        
        return results
    
    def get_product_by_id(self, product_id: int) -> Optional[Dict[str, Any]]:
        """Get specific product by ID"""
        if not self.products:
            self.load_products()
        
        for product in self.products:
            if product.get('id') == product_id:
                return product
        return None
    
    def get_featured_products(self, limit: int = 6) -> List[Dict[str, Any]]:
        """Get featured products (high rating, good price)"""
        if not self.products:
            self.load_products()
        
        # Sort by rating and reasonable price
        featured = sorted(
            self.products,
            key=lambda x: (x.get('rating', 0), -x.get('price', float('inf'))),
            reverse=True
        )
        
        return featured[:limit]
    
    def get_recommendations(self, category: str = None, max_price: float = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Get product recommendations based on criteria"""
        if not self.products:
            self.load_products()
        
        filtered_products = self.products.copy()
        
        # Apply filters
        if category:
            filtered_products = [p for p in filtered_products 
                               if p.get('category', '').lower() == category.lower()]
        
        if max_price:
            filtered_products = [p for p in filtered_products 
                               if p.get('price', 0) <= max_price]
        
        # Sort by rating
        recommendations = sorted(
            filtered_products,
            key=lambda x: x.get('rating', 0),
            reverse=True
        )
        
        return recommendations[:limit]

# Global product data loader instance
product_data_loader = ProductDataLoader() 