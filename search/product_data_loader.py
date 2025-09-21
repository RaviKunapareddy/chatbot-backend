"""
Data Loading and Management

This module handles:
- Product data loading from S3
- Category extraction and management
- Semantic search integration with Pinecone vector database
- Product filtering and recommendations
"""

import logging
import os
import re
from typing import Any, Dict, List, Optional

import vector_service.pinecone_client as pc
from data.s3_client import s3_client
from memory.conversation_memory import conversation_memory
from common.indexing_coordinator import indexing_coordinator

logger = logging.getLogger(__name__)


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
        """Load products from S3 with smart indexing"""
        try:
            # Check if we need to refresh data first (Issue #2 fix)
            current_s3_timestamp = s3_client.get_products_last_modified()
            should_use_fresh_data = self._should_refresh_data(current_s3_timestamp)
            
            # Load products from S3 (with fresh data if needed)
            self.products = s3_client.load_products(force_refresh=should_use_fresh_data)

            # Extract categories
            self.categories = {product.get("category", "Unknown") for product in self.products}

            # Smart indexing: only index if data actually changed (Issue #1 fix)
            should_reindex = self._should_reindex_products(current_s3_timestamp)
            
            if should_reindex:
                try:
                    if pc.pinecone_products_client.is_available():
                        logger.info("🔄 Data changed - reindexing products in Pinecone...")
                        pc.pinecone_products_client.index_products(self.products)
                        
                        # Save timestamp of successful indexing
                        self._save_last_indexed_timestamp(current_s3_timestamp)
                        logger.info("✅ Products indexed in Pinecone for vector search")
                    else:
                        logger.warning("⚠️ Pinecone not available - will use keyword search")
                except Exception as e:
                    logger.warning(f"Pinecone indexing failed (will use keyword search): {e}")
            else:
                logger.info("✅ Products already indexed - skipping reindexing")

            logger.info(f"Loaded {len(self.products)} products")
            return self.products

        except Exception as e:
            logger.error(f"Error loading products: {e}")
            return []

    def _should_refresh_data(self, current_s3_timestamp: Optional[str]) -> bool:
        """Check if we should refresh cached data from S3"""
        if not current_s3_timestamp:
            return True  # Can't check timestamp, refresh to be safe
            
        try:
            # Get last cached data timestamp
            cached_timestamp = self._get_last_cached_timestamp()
            if not cached_timestamp:
                return True  # No cached timestamp, refresh
                
            # Compare timestamps - refresh if S3 data is newer
            if current_s3_timestamp > cached_timestamp:
                logger.info(f"🔄 S3 data updated ({current_s3_timestamp}) - refreshing cache")
                return True
                
            return False  # Cache is up to date
            
        except Exception as e:
            logger.warning(f"Error checking data freshness: {e}")
            return True  # Error checking, refresh to be safe

    def _should_reindex_products(self, current_s3_timestamp: Optional[str]) -> bool:
        """Check if we should reindex products in Pinecone with coordination"""
        if not current_s3_timestamp:
            logger.info("🔄 No S3 timestamp available - will reindex to be safe")
            return True
            
        try:
            # NEW: Check coordination - skip if manual script already handled this data
            if indexing_coordinator.should_skip_automatic_indexing(current_s3_timestamp):
                return False
            
            # Check for recent indexing that might conflict
            recent_indexing = indexing_coordinator.check_recent_indexing(minutes=5)
            if recent_indexing:
                indexed_by = recent_indexing.get("indexed_by")
                minutes_ago = recent_indexing.get("minutes_ago", 0)
                if indexed_by == "manual_script":
                    logger.info(f"⚠️ Manual indexing detected {minutes_ago} minutes ago - proceeding carefully")
                    # Continue with normal checks but be aware of potential conflict
            
            # Original timestamp comparison logic (with Redis backup)
            last_indexed = self._get_last_indexed_timestamp()
            if not last_indexed:
                logger.info("🔄 No previous indexing timestamp - will index")
                return True
                
            # Compare timestamps - reindex if S3 data is newer than last index
            if current_s3_timestamp > last_indexed:
                logger.info(f"🔄 Data updated since last index ({last_indexed}) - will reindex")
                return True
                
            logger.info(f"✅ Data unchanged since last index ({last_indexed}) - skipping")
            return False
            
        except Exception as e:
            logger.warning(f"Error checking indexing status: {e}")
            return True  # Error checking, reindex to be safe

    def _get_last_cached_timestamp(self) -> Optional[str]:
        """Get timestamp of last cached data"""
        try:
            if conversation_memory.is_available():
                return conversation_memory.get("product_cache_timestamp")
            return None
        except Exception:
            return None

    def _get_last_indexed_timestamp(self) -> Optional[str]:
        """Get timestamp of last successful indexing"""
        try:
            if conversation_memory.is_available():
                return conversation_memory.get("product_last_indexed")
            return None
        except Exception:
            return None

    def _save_last_indexed_timestamp(self, timestamp: str) -> None:
        """Save timestamp of successful indexing"""
        try:
            if conversation_memory.is_available():
                conversation_memory.set("product_last_indexed", timestamp, expire_seconds=30*24*3600)  # 30 days
                conversation_memory.set("product_cache_timestamp", timestamp, expire_seconds=30*24*3600)  # 30 days
            
            # NEW: Save coordination info
            indexing_coordinator.save_coordination_info(
                timestamp=timestamp,
                source="automatic",
                operation="index",
                product_count=len(self.products),
                s3_timestamp=timestamp
            )
        except Exception as e:
            logger.warning(f"Could not save indexing timestamp: {e}")

    def _normalize_tag(self, tag) -> str:
        """Normalize a tag string similar to Pinecone metadata flags.
        Rules: lowercase, trim, non-alnum -> underscore, collapse repeats, strip edges.
        """
        try:
            s = str(tag).strip().lower()
            s = re.sub(r"[^a-z0-9]+", "_", s)
            s = re.sub(r"_+", "_", s).strip("_")
            return s
        except Exception:
            return ""

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

    def get_brands(self) -> List[str]:
        """Get all available canonical brands from loaded products"""
        if not self.products:
            self.load_products()
        try:
            brands = {
                (p.get("brand") or "").strip()
                for p in self.products
                if p.get("brand") and str(p.get("brand")).strip()
            }
            return sorted(list(brands))
        except Exception:
            return []

    def search_products(
        self,
        query: str,
        category: str = None,
        limit: int = 10,
        price_min: float = None,
        price_max: float = None,
        brand: str = None,
        rating_min: float = None,
        in_stock: Optional[bool] = None,
        discount_min: float = None,
        tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Basic keyword search for products with optional filters.

        Supports: category, brand, price range, minimum rating, in_stock, minimum discount%, and tags (all must match).
        """
        if not self.products:
            self.load_products()

        results = []
        query_lower = (query or "").lower()
        # If any server-side filter is provided, allow returning results even if the plain
        # query text does not appear in title/description. This mirrors vector search semantics.
        # Only certain filters imply that keyword presence shouldn't be required.
        # Keep substring requirement when only numeric filters (rating/stock/discount) are provided
        # to match existing unit test expectations.
        has_filters = bool(category) or bool(brand) or bool(tags)

        for product in self.products:
            # Category filter
            if category and product.get("category", "").lower() != category.lower():
                continue

            # Brand filter
            if brand and product.get("brand", "").lower() != brand.lower():
                continue

            # Rating filter
            if rating_min is not None and float(product.get("rating", 0) or 0) < float(rating_min):
                continue

            # In-stock filter
            if in_stock is True:
                stock_val = int(product.get("stock", 0) or 0)
                if stock_val <= 0:
                    continue

            # Discount filter (percentage)
            if discount_min is not None:
                # Prefer explicit discountPercentage field for parity with Pinecone metadata filtering
                if product.get("discountPercentage") is not None:
                    discount_pct = float(product.get("discountPercentage") or 0)
                else:
                    price_val_num = float(product.get("price", 0) or 0)
                    orig_val = float(product.get("originalPrice", 0) or 0)
                    discount_pct = (
                        ((orig_val - price_val_num) / orig_val * 100.0)
                        if orig_val and orig_val > 0
                        else 0.0
                    )
                if discount_pct < float(discount_min):
                    continue

            # Price filters
            price_val = product.get("price", 0)
            if price_min is not None and price_val < price_min:
                continue
            if price_max is not None and price_val > price_max:
                continue

            # Tags filter (all requested tags must be present)
            if tags:
                prod_tags = product.get("tags") or []
                # Normalize both sides to match vector-side normalization semantics
                prod_norms = set(self._normalize_tag(t) for t in prod_tags if t is not None)
                desired_norms = [self._normalize_tag(t) for t in tags if t is not None]
                if not all(n and (n in prod_norms) for n in desired_norms):
                    continue

            # Search in title and description unless filters are provided
            if has_filters or not query_lower:
                results.append(product)
            else:
                title = product.get("title", "").lower()
                description = product.get("description", "").lower()
                if query_lower in title or query_lower in description:
                    results.append(product)

            if len(results) >= limit:
                break

        return results

    def semantic_search_products(
        self,
        query: str,
        limit: int = 5,
        price_min: float = None,
        price_max: float = None,
        brand: str = None,
        category: str = None,
        rating_min: float = None,
        in_stock: Optional[bool] = None,
        discount_min: float = None,
        tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Advanced semantic search using Pinecone or fallback to keyword search.

        Passes all supported filters through to Pinecone when available; otherwise applies them via keyword filtering.
        """
        if not self.products:
            self.load_products()

        # Try Pinecone vector search first (if available)
        try:
            if pc.pinecone_products_client.is_available():
                results = pc.pinecone_products_client.search_products(
                    query,
                    limit=limit,
                    brand=brand,
                    category=category,
                    rating_min=rating_min,
                    in_stock=in_stock,
                    discount_min=discount_min,
                    price_min=price_min,
                    price_max=price_max,
                    tags=tags,
                )
                if results:
                    # Apply reranking if enabled
                    results = self._apply_reranking(
                        results, price_min=price_min, price_max=price_max
                    )
                    return results
        except Exception as e:
            logger.warning(f"Pinecone search failed, falling back to keyword search: {e}")

        # Fallback to basic keyword search
        logger.info(f"Using keyword search fallback for: '{query}'")
        results = self.search_products(
            query,
            category=category,
            limit=limit,
            price_min=price_min,
            price_max=price_max,
            brand=brand,
            rating_min=rating_min,
            in_stock=in_stock,
            discount_min=discount_min,
            tags=tags,
        )

        # Ensure we have similarity scores for ranking consistency
        for i, result in enumerate(results):
            if "similarity_score" not in result:
                # Assign decreasing scores for fallback results
                result["similarity_score"] = 1.0 - (i * 0.1)

        # Apply reranking if enabled
        results = self._apply_reranking(results, price_min=price_min, price_max=price_max)
        return results

    def get_products_by_category(self, category: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get products from specific category"""
        if not self.products:
            self.load_products()

        results = []
        for product in self.products:
            if product.get("category", "").lower() == category.lower():
                results.append(product)
                if len(results) >= limit:
                    break

        return results

    def get_product_by_id(self, product_id: int) -> Optional[Dict[str, Any]]:
        """Get specific product by ID"""
        if not self.products:
            self.load_products()

        for product in self.products:
            if product.get("id") == product_id:
                return product
        return None

    def get_featured_products(self, limit: int = 6) -> List[Dict[str, Any]]:
        """Get featured products (high rating, good price)"""
        if not self.products:
            self.load_products()

        # Sort by rating and reasonable price
        featured = sorted(
            self.products,
            key=lambda x: (x.get("rating", 0), -x.get("price", float("inf"))),
            reverse=True,
        )

        return featured[:limit]

    def get_recommendations(
        self, category: str = None, max_price: float = None, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get product recommendations based on criteria"""
        if not self.products:
            self.load_products()

        filtered_products = self.products.copy()

        # Apply filters
        if category:
            filtered_products = [
                p for p in filtered_products if p.get("category", "").lower() == category.lower()
            ]

        if max_price:
            filtered_products = [p for p in filtered_products if p.get("price", 0) <= max_price]

        # Sort by rating
        recommendations = sorted(filtered_products, key=lambda x: x.get("rating", 0), reverse=True)

        return recommendations[:limit]

    def _apply_reranking(
        self, results: List[Dict[str, Any]], price_min: Optional[float], price_max: Optional[float]
    ) -> List[Dict[str, Any]]:
        """Attach rerank_score and optionally reorder results by it.

        score = 0.6 * similarity + 0.2 * (rating/5) + 0.1 * (min(discountPercentage,50)/50) + 0.1 * price_affinity

        price_affinity is 1.0 if price is within provided price bounds; otherwise 0.0.
        Controlled by env SEARCH_RERANK_ENABLED (defaults to false).
        """

        def clamp01(x: float) -> float:
            try:
                if x is None:
                    return 0.0
                xf = float(x)
                # NaN check without importing math
                if xf != xf:
                    return 0.0
                return max(0.0, min(1.0, xf))
            except Exception:
                return 0.0

        def price_affinity(price: Optional[float]) -> float:
            try:
                if price is None:
                    return 0.0
                if price_min is not None and price_max is not None:
                    return 1.0 if (price_min <= price <= price_max) else 0.0
                if price_max is not None:
                    return 1.0 if price <= price_max else 0.0
                if price_min is not None:
                    return 1.0 if price >= price_min else 0.0
                return 0.0
            except Exception:
                return 0.0

        for r in results:
            sim = clamp01(r.get("similarity_score", 0.0))
            rating = clamp01((r.get("rating") or 0.0) / 5.0)
            try:
                discount = float(r.get("discountPercentage", 0.0) or 0.0)
            except Exception:
                discount = 0.0
            discount_norm = clamp01(min(discount, 50.0) / 50.0)
            try:
                price_val = float(r.get("price")) if r.get("price") is not None else None
            except Exception:
                price_val = None
            price_term = clamp01(price_affinity(price_val))

            rerank_score = 0.6 * sim + 0.2 * rating + 0.1 * discount_norm + 0.1 * price_term
            r["rerank_score"] = float(rerank_score)

        # Only reorder when explicitly enabled
        enabled = str(os.getenv("SEARCH_RERANK_ENABLED", "false")).lower() in ("1", "true", "yes")
        if enabled:
            results = sorted(results, key=lambda x: x.get("rerank_score", 0.0), reverse=True)

        return results


# Global product data loader instance
product_data_loader = ProductDataLoader()
