"""
Unified S3 Client for All Data Management

This module provides a unified interface for managing both product and support data in S3.
It handles:
- Product data loading and uploading
- Support data generation, loading, and uploading
- Unified validation and backup operations
- Caching and error handling
"""

import boto3
import json
from typing import Dict, List, Any, Optional
import os
from datetime import datetime
from config import settings
from botocore.exceptions import ClientError
from botocore.config import Config
import logging

logger = logging.getLogger(__name__)


class ProductS3Client:
    """Handles product-specific S3 operations"""
    
    def __init__(self, s3_client, bucket_name: str):
        self.s3_client = s3_client
        self.bucket_name = bucket_name
        self.products_key = settings.S3_PRODUCTS_KEY
        self.cached_products = None
    
    def load_products(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Load products from S3 with caching"""
        if not force_refresh and self.cached_products is not None:
            return self.cached_products
            
        try:
            # Try to load from S3
            try:
                response = self.s3_client.get_object(
                    Bucket=self.bucket_name,
                    Key=self.products_key
                )
                products_data = json.loads(response['Body'].read().decode('utf-8'))
                
                # Handle both array and object with products key
                if isinstance(products_data, dict) and 'products' in products_data:
                    self.cached_products = products_data['products']
                elif isinstance(products_data, list):
                    self.cached_products = products_data
                else:
                    self.cached_products = []
                    
                logger.info(f"✅ Loaded {len(self.cached_products)} products from S3")
                
            except ClientError as e:
                logger.warning(f"❌ S3 error: {e}")
                # Fall back to local file if S3 fails
                local_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'products.json')
                
                if os.path.exists(local_path):
                    # Load products from local file if it exists
                    try:
                        with open(local_path, 'r') as f:
                            products_data = json.load(f)
                            
                            # Handle both array and object with products key
                            if isinstance(products_data, dict) and 'products' in products_data:
                                self.cached_products = products_data['products']
                            elif isinstance(products_data, list):
                                self.cached_products = products_data
                            else:
                                self.cached_products = []
                                
                            logger.info(f"✅ Loaded {len(self.cached_products)} products from local file")
                    except Exception as local_error:
                        logger.error(f"❌ Error loading local products file: {local_error}")
                        self.cached_products = []
                else:
                    logger.warning(f"Local products file not found at {local_path}")
                    self.cached_products = []
                
            return self.cached_products
                
        except Exception as e:
            logger.error(f"❌ Error loading products: {e}")
            return []
    
    def upload_products(self, file_path: str, create_backup: bool = True) -> bool:
        """Upload products from local JSON file to S3"""
        try:
            # Load products from file
            with open(file_path, 'r', encoding='utf-8') as f:
                products_data = json.load(f)
            
            # Handle both array and object with products key
            if isinstance(products_data, dict) and 'products' in products_data:
                products = products_data['products']
            elif isinstance(products_data, list):
                products = products_data
            else:
                raise ValueError("Invalid products data format in file")
            
            # Validate products
            if not self.validate_products(products):
                logger.error("❌ Product validation failed")
                return False
            
            # Create backup if requested
            if create_backup:
                self._create_backup()
            
            # Upload to S3
            products_json = json.dumps(products, indent=2)
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=self.products_key,
                Body=products_json,
                ContentType='application/json',
                Metadata={
                    'total_products': str(len(products)),
                    'last_updated': datetime.utcnow().isoformat() + "Z"
                }
            )
            
            # Update cache
            self.cached_products = products
            
            logger.info(f"✅ Successfully uploaded {len(products)} products to S3")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to upload products: {e}")
            return False
    
    def validate_products(self, products: List[Dict[str, Any]]) -> bool:
        """Validate product data structure"""
        try:
            if not isinstance(products, list):
                logger.error("❌ Products must be a list")
                return False
            
            if len(products) == 0:
                logger.error("❌ Products list cannot be empty")
                return False
            
            # Check required fields in sample products
            required_fields = ['id', 'title', 'price']
            for i, product in enumerate(products[:5]):  # Check first 5
                if not isinstance(product, dict):
                    logger.error(f"❌ Product {i} is not a dictionary")
                    return False
                
                for field in required_fields:
                    if field not in product:
                        logger.error(f"❌ Product {i} missing required field: {field}")
                        return False
                
                # Validate data types
                if not isinstance(product['price'], (int, float)):
                    logger.error(f"❌ Product {i} price must be a number")
                    return False
            
            logger.info(f"✅ Validated {len(products)} products")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error validating products: {e}")
            return False
    
    def _create_backup(self):
        """Create backup of existing products"""
        try:
            # Check if products exist
            existing_products = self.load_products()
            if existing_products:
                backup_key = f"product_backups/products_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=backup_key,
                    Body=json.dumps(existing_products, indent=2),
                    ContentType='application/json'
                )
                logger.info(f"📁 Created product backup: {backup_key}")
        except Exception as e:
            logger.warning(f"⚠️ Product backup creation failed: {e}")
    
    def get_product_stats(self) -> Dict[str, Any]:
        """Get statistics about products in S3"""
        stats = {
            "products_available": True,
            "cached": self.cached_products is not None
        }
        
        try:
            # Check if products exist
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=self.products_key
            )
            stats["products_exist"] = True
            stats["last_modified"] = response['LastModified'].isoformat()
            stats["size_bytes"] = response['ContentLength']
            
            # Get metadata
            metadata = response.get('Metadata', {})
            if metadata:
                stats["total_products"] = metadata.get('total_products', 'unknown')
            
            # If cached, add more details
            if self.cached_products:
                stats["total_products"] = len(self.cached_products)
                categories = set(p.get('category', 'Unknown') for p in self.cached_products)
                stats["categories"] = sorted(list(categories))
                
        except ClientError:
            stats["products_exist"] = False
        except Exception as e:
            stats["error"] = str(e)
        
        return stats
    
    def clear_cache(self):
        """Clear cached products"""
        self.cached_products = None
        logger.info("🔄 Cleared products cache")


class SupportS3Client:
    """Handles support-specific S3 operations"""
    
    def __init__(self, s3_client, bucket_name: str):
        self.s3_client = s3_client
        self.bucket_name = bucket_name
        self.support_knowledge_key = os.getenv("S3_SUPPORT_KNOWLEDGE_KEY", "support_knowledge_base.json")
        self.cached_support_data = None
    
    def load_support_data(self, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """Load support data from S3 with caching"""
        if use_cache and self.cached_support_data is not None:
            return self.cached_support_data
            
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=self.support_knowledge_key
            )
            support_data = json.loads(response['Body'].read().decode('utf-8'))
            
            # Validate data structure
            if not self.validate_support_data(support_data):
                logger.error("❌ Invalid support data structure in S3")
                return None
            
            # Update cache
            self.cached_support_data = support_data
            
            logger.info(f"✅ Loaded support data from S3: {support_data['metadata']['total_documents']} documents")
            return support_data
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                logger.warning(f"⚠️ Support data not found in S3: {self.support_knowledge_key}")
            elif error_code == 'NoSuchBucket':
                logger.error(f"❌ S3 bucket not found: {self.bucket_name}")
            else:
                logger.error(f"❌ S3 error loading support data: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Failed to load support data from S3: {e}")
            return None
    
    def upload_support_data(self, support_data: Dict[str, Any] = None, create_backup: bool = True) -> bool:
        """Upload support data to S3 with optional backup"""
        try:
            # Generate data if not provided
            if support_data is None:
                support_data = self.generate_support_data()
            
            # Validate data
            if not self.validate_support_data(support_data):
                logger.error("❌ Support data validation failed")
                return False
            
            # Create backup if requested
            if create_backup:
                self._create_backup()
            
            # Upload to S3
            support_json = json.dumps(support_data, indent=2)
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=self.support_knowledge_key,
                Body=support_json,
                ContentType='application/json',
                Metadata={
                    'total_documents': str(support_data['metadata']['total_documents']),
                    'version': support_data['metadata']['version'],
                    'last_updated': support_data['metadata']['last_updated']
                }
            )
            
            # Update cache
            self.cached_support_data = support_data
            
            logger.info(f"✅ Successfully uploaded support data to S3: {self.support_knowledge_key}")
            logger.info(f"📊 Total documents: {support_data['metadata']['total_documents']}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to upload support data to S3: {e}")
            return False
    
    def generate_support_data(self) -> Dict[str, Any]:
        """Generate complete support data structure from current sources"""
        try:
            # Import here to avoid circular imports
            from support_docs.FAQ_Knowledge_base import ProductPolicyScraper
            from support_docs.FAQ_Knowledge_base import KnowledgeProvider
            
            # Extract support documents from products
            extractor = ProductPolicyScraper()
            product_support_docs = extractor.extract_policies()
            
            # Get FAQ documents (now includes hybrid static + scraped)
            provider = KnowledgeProvider()
            faq_docs = provider.get_all_knowledge()
            
            # Combine all support documents
            all_support_docs = product_support_docs + faq_docs
            
            # Add unique IDs to each document if not present
            for i, doc in enumerate(all_support_docs):
                if 'doc_id' not in doc and 'faq_id' not in doc:
                    doc['doc_id'] = f"support_doc_{i+1}"
            
            # Create complete data structure
            support_data = {
                'metadata': {
                    'total_documents': len(all_support_docs),
                    'product_derived_count': len(product_support_docs),
                    'faq_count': len(faq_docs),
                    'last_updated': datetime.utcnow().isoformat() + "Z",
                    'version': "1.0",
                    'categories': sorted(list(set([doc.get('category', '') for doc in all_support_docs]))),
                    'document_types': sorted(list(set([doc.get('type', '') for doc in all_support_docs]))),
                    'sources': sorted(list(set([doc.get('source', '') for doc in all_support_docs])))
                },
                'support_documents': all_support_docs
            }
            
            logger.info(f"📊 Generated support data: {len(all_support_docs)} documents")
            return support_data
            
        except Exception as e:
            logger.error(f"❌ Error generating support data: {e}")
            raise
    
    def validate_support_data(self, data: Dict[str, Any]) -> bool:
        """Validate support data structure"""
        try:
            # Check required top-level keys
            if not all(key in data for key in ['metadata', 'support_documents']):
                logger.error("❌ Missing required keys in support data")
                return False
            
            # Check metadata structure
            metadata = data['metadata']
            required_metadata = ['total_documents', 'last_updated', 'categories', 'document_types']
            if not all(key in metadata for key in required_metadata):
                logger.error("❌ Missing required metadata fields")
                return False
            
            # Check support documents structure
            docs = data['support_documents']
            if not isinstance(docs, list):
                logger.error("❌ Support documents must be a list")
                return False
            
            # Validate document count matches metadata
            if len(docs) != metadata['total_documents']:
                logger.error("❌ Document count mismatch with metadata")
                return False
            
            # Check document structure (sample first few)
            for i, doc in enumerate(docs[:3]):
                if not all(key in doc for key in ['content', 'type', 'category', 'source']):
                    logger.error(f"❌ Document {i} missing required fields")
                    return False
            
            logger.info(f"✅ Validated support data with {len(docs)} documents")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error validating support data: {e}")
            return False
    
    def _create_backup(self):
        """Create backup of existing support data"""
        try:
            existing_data = self.load_support_data(use_cache=False)
            if existing_data:
                backup_key = f"support_backups/knowledge_base_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=backup_key,
                    Body=json.dumps(existing_data, indent=2),
                    ContentType='application/json'
                )
                logger.info(f"📁 Created support backup: {backup_key}")
        except Exception as e:
            logger.warning(f"⚠️ Support backup creation failed: {e}")
    
    def get_support_documents(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        """Get just the support documents list"""
        support_data = self.load_support_data(use_cache=use_cache)
        if support_data and 'support_documents' in support_data:
            return support_data['support_documents']
        return []
    
    def get_support_stats(self) -> Dict[str, Any]:
        """Get statistics about support data in S3"""
        stats = {
            "support_available": True,
            "cached": self.cached_support_data is not None
        }
        
        try:
            # Check if support data exists
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=self.support_knowledge_key
            )
            stats["support_data_exists"] = True
            stats["last_modified"] = response['LastModified'].isoformat()
            stats["size_bytes"] = response['ContentLength']
            
            # Get metadata
            metadata = response.get('Metadata', {})
            if metadata:
                stats["total_documents"] = metadata.get('total_documents', 'unknown')
                stats["version"] = metadata.get('version', 'unknown')
            
            # If cached, add more details
            if self.cached_support_data:
                cached_metadata = self.cached_support_data.get('metadata', {})
                stats.update({
                    "categories": cached_metadata.get('categories', []),
                    "document_types": cached_metadata.get('document_types', []),
                    "sources": cached_metadata.get('sources', [])
                })
                
        except ClientError:
            stats["support_data_exists"] = False
        except Exception as e:
            stats["error"] = str(e)
        
        return stats
    
    def clear_cache(self):
        """Clear cached support data"""
        self.cached_support_data = None
        logger.info("🔄 Cleared support data cache")


class UnifiedS3Client:
    """Unified interface for all S3 data operations"""
    
    def __init__(self):
        self.bucket_name = settings.S3_BUCKET_NAME
        self._init_s3_client()
        
        # Initialize specialized clients
        self.product_client = ProductS3Client(self.s3_client, self.bucket_name)
        self.support_client = SupportS3Client(self.s3_client, self.bucket_name)
    
    def _init_s3_client(self):
        """Initialize S3 client using existing AWS credentials"""
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_DEFAULT_REGION,
                config=Config(
                    read_timeout=10,
                    connect_timeout=5
                )
            )
            logger.info("✅ Unified S3 client initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize S3 client: {e}")
            raise
    
    # Product operations (backward compatibility)
    def load_products(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Load products from S3 - backward compatible method"""
        return self.product_client.load_products(force_refresh)
    
    def update_products(self, products: List[Dict[str, Any]]) -> bool:
        """Update products in S3 - backward compatible method"""
        try:
            products_json = json.dumps(products, indent=2)
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=self.product_client.products_key,
                Body=products_json,
                ContentType='application/json'
            )
            self.product_client.cached_products = products
            logger.info("✅ Successfully updated products in S3")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to update products in S3: {e}")
            return False
    
    # Unified data operations
    def upload_data(self, data_type: str, file_path: str = None, data: Any = None, create_backup: bool = True) -> bool:
        """Upload data to S3 - unified method"""
        try:
            if data_type == "products":
                if file_path:
                    return self.product_client.upload_products(file_path, create_backup)
                else:
                    logger.error("❌ File path required for product upload")
                    return False
            
            elif data_type == "support":
                return self.support_client.upload_support_data(data, create_backup)
            
            else:
                logger.error(f"❌ Unknown data type: {data_type}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to upload {data_type} data: {e}")
            return False
    
    def load_data(self, data_type: str, **kwargs) -> Any:
        """Load data from S3 - unified method"""
        try:
            if data_type == "products":
                return self.product_client.load_products(kwargs.get('force_refresh', False))
            
            elif data_type == "support":
                return self.support_client.load_support_data(kwargs.get('use_cache', True))
            
            else:
                logger.error(f"❌ Unknown data type: {data_type}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Failed to load {data_type} data: {e}")
            return None
    
    def validate_data(self, data_type: str, data: Any) -> bool:
        """Validate data - unified method"""
        try:
            if data_type == "products":
                return self.product_client.validate_products(data)
            
            elif data_type == "support":
                return self.support_client.validate_support_data(data)
            
            else:
                logger.error(f"❌ Unknown data type: {data_type}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to validate {data_type} data: {e}")
            return False
    
    def get_data_stats(self, data_type: str = None) -> Dict[str, Any]:
        """Get statistics about data in S3 - unified method"""
        try:
            if data_type == "products":
                return self.product_client.get_product_stats()
            
            elif data_type == "support":
                return self.support_client.get_support_stats()
            
            elif data_type is None:
                # Return stats for all data types
                return {
                    "products": self.product_client.get_product_stats(),
                    "support": self.support_client.get_support_stats()
                }
            
            else:
                logger.error(f"❌ Unknown data type: {data_type}")
                return {}
                
        except Exception as e:
            logger.error(f"❌ Failed to get {data_type} stats: {e}")
            return {}
    
    def clear_cache(self, data_type: str = None):
        """Clear cached data - unified method"""
        try:
            if data_type == "products":
                self.product_client.clear_cache()
            
            elif data_type == "support":
                self.support_client.clear_cache()
            
            elif data_type is None:
                # Clear all caches
                self.product_client.clear_cache()
                self.support_client.clear_cache()
                logger.info("🔄 Cleared all caches")
            
            else:
                logger.error(f"❌ Unknown data type: {data_type}")
                
        except Exception as e:
            logger.error(f"❌ Failed to clear {data_type} cache: {e}")
    
    # Support-specific convenience methods
    def get_support_documents(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        """Get support documents - convenience method"""
        return self.support_client.get_support_documents(use_cache)
    
    def generate_support_data(self) -> Dict[str, Any]:
        """Generate support data - convenience method"""
        return self.support_client.generate_support_data()


# Global instance - backward compatible
s3_client = UnifiedS3Client() 