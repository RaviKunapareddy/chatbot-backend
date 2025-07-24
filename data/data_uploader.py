"""
Unified Data Uploader for S3

This tool provides a unified interface for uploading both product and support data to S3.
It supports:
- Product data upload from JSON files
- Support data generation and upload
- Automatic backup creation
- Data validation
- Upload verification
"""

import os
import sys
import argparse
from pathlib import Path
import logging
from datetime import datetime
from dotenv import load_dotenv

# Add backend to path so we can import our modules
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BACKEND_DIR))

# Load environment variables
load_dotenv(BACKEND_DIR / '.env')

# Import after env vars are loaded
from s3_client import s3_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def upload_products(file_path: str, create_backup: bool = True) -> bool:
    """Upload product data from JSON file"""
    logger.info(f"🚀 Starting product data upload from {file_path}...")
    
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            logger.error(f"❌ File not found: {file_path}")
            return False
        
        # Check if products already exist
        stats = s3_client.get_data_stats("products")
        if stats.get("products_exist", False):
            logger.info("📁 Existing product data found in S3")
            logger.info(f"   Current products: {stats.get('total_products', 'unknown')}")
            logger.info(f"   Last modified: {stats.get('last_modified', 'unknown')}")
            
            # Confirm overwrite
            response = input("🤔 Overwrite existing product data? (y/N): ").strip().lower()
            if response not in ['y', 'yes']:
                logger.info("❌ Upload cancelled by user")
                return False
        
        # Upload products
        logger.info("📦 Uploading product data...")
        success = s3_client.upload_data("products", file_path=file_path, create_backup=create_backup)
        
        if success:
            logger.info("✅ Successfully uploaded product data to S3!")
            
            # Verify upload
            verify_products()
            return True
        else:
            logger.error("❌ Failed to upload product data")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error uploading product data: {e}")
        return False


def upload_support(create_backup: bool = True) -> bool:
    """Upload support data (generated from products and FAQs)"""
    logger.info("🚀 Starting support data upload...")
    
    try:
        # Check if support data already exists
        stats = s3_client.get_data_stats("support")
        if stats.get("support_data_exists", False):
            logger.info("📁 Existing support data found in S3")
            logger.info(f"   Current documents: {stats.get('total_documents', 'unknown')}")
            logger.info(f"   Last modified: {stats.get('last_modified', 'unknown')}")
            
            # Confirm overwrite
            response = input("🤔 Overwrite existing support data? (y/N): ").strip().lower()
            if response not in ['y', 'yes']:
                logger.info("❌ Upload cancelled by user")
                return False
        
        # Generate and upload support data
        logger.info("🔄 Generating support knowledge base...")
        success = s3_client.upload_data("support", create_backup=create_backup)
        
        if success:
            logger.info("✅ Successfully uploaded support data to S3!")
            
            # Verify upload
            verify_support()
            return True
        else:
            logger.error("❌ Failed to upload support data")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error uploading support data: {e}")
        return False


def verify_products():
    """Verify uploaded product data"""
    logger.info("\n🔍 Verifying uploaded product data...")
    
    try:
        # Clear cache and reload from S3
        s3_client.clear_cache("products")
        products = s3_client.load_data("products", force_refresh=True)
        
        if not products:
            logger.error("❌ Failed to load product data from S3")
            return False
        
        # Display stats
        logger.info(f"✅ Verification successful!")
        logger.info(f"   Total products: {len(products)}")
        
        # Show categories
        categories = set(p.get('category', 'Unknown') for p in products)
        logger.info(f"   Categories: {len(categories)} - {', '.join(sorted(categories))}")
        
        # Show sample products
        logger.info(f"\n📄 Sample products:")
        for i, product in enumerate(products[:3]):
            logger.info(f"   {i+1}. {product.get('title', 'Unknown')} - ${product.get('price', 0)}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error verifying product data: {e}")
        return False


def verify_support():
    """Verify uploaded support data"""
    logger.info("\n🔍 Verifying uploaded support data...")
    
    try:
        # Clear cache and reload from S3
        s3_client.clear_cache("support")
        support_data = s3_client.load_data("support", use_cache=False)
        
        if not support_data:
            logger.error("❌ Failed to load support data from S3")
            return False
        
        # Display metadata
        metadata = support_data.get('metadata', {})
        logger.info(f"✅ Verification successful!")
        logger.info(f"   Total documents: {metadata.get('total_documents', 0)}")
        logger.info(f"   Product-derived: {metadata.get('product_derived_count', 0)}")
        logger.info(f"   FAQ documents: {metadata.get('faq_count', 0)}")
        logger.info(f"   Categories: {len(metadata.get('categories', []))}")
        logger.info(f"   Version: {metadata.get('version', 'unknown')}")
        
        # Show sample documents
        documents = support_data.get('support_documents', [])
        if documents:
            logger.info(f"\n📄 Sample documents:")
            for i, doc in enumerate(documents[:3]):
                logger.info(f"   {i+1}. {doc.get('type', 'unknown')} - {doc.get('content', '')[:60]}...")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error verifying support data: {e}")
        return False


def show_data_stats():
    """Show current S3 data statistics"""
    logger.info("\n📊 Current S3 Data Statistics:")
    
    try:
        # Get all stats
        all_stats = s3_client.get_data_stats()
        
        # Product stats
        product_stats = all_stats.get('products', {})
        logger.info(f"\n📦 Product Data:")
        logger.info(f"   Available: {product_stats.get('products_available', False)}")
        logger.info(f"   Exists: {product_stats.get('products_exist', False)}")
        logger.info(f"   Cached: {product_stats.get('cached', False)}")
        if product_stats.get('products_exist'):
            logger.info(f"   Total Products: {product_stats.get('total_products', 'unknown')}")
            logger.info(f"   Last Modified: {product_stats.get('last_modified', 'unknown')}")
            logger.info(f"   Size: {product_stats.get('size_bytes', 0)} bytes")
        
        # Support stats
        support_stats = all_stats.get('support', {})
        logger.info(f"\n🎧 Support Data:")
        logger.info(f"   Available: {support_stats.get('support_available', False)}")
        logger.info(f"   Exists: {support_stats.get('support_data_exists', False)}")
        logger.info(f"   Cached: {support_stats.get('cached', False)}")
        if support_stats.get('support_data_exists'):
            logger.info(f"   Total Documents: {support_stats.get('total_documents', 'unknown')}")
            logger.info(f"   Last Modified: {support_stats.get('last_modified', 'unknown')}")
            logger.info(f"   Size: {support_stats.get('size_bytes', 0)} bytes")
            logger.info(f"   Version: {support_stats.get('version', 'unknown')}")
            
    except Exception as e:
        logger.error(f"❌ Error getting data stats: {e}")


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Unified Data Uploader for S3')
    parser.add_argument('data_type', choices=['products', 'support', 'all'], 
                       help='Type of data to upload')
    parser.add_argument('--file', '-f', type=str, 
                       help='Path to JSON file (required for products)')
    parser.add_argument('--no-backup', action='store_true', 
                       help='Skip backup creation')
    parser.add_argument('--stats', action='store_true', 
                       help='Show current data statistics')
    
    args = parser.parse_args()
    
    # Show header
    logger.info("🚀 Unified Data Uploader for S3")
    logger.info("=" * 50)
    
    # Show stats if requested
    if args.stats:
        show_data_stats()
        return
    
    create_backup = not args.no_backup
    success = True
    
    try:
        if args.data_type == 'products':
            if not args.file:
                logger.error("❌ --file argument required for product upload")
                sys.exit(1)
            success = upload_products(args.file, create_backup)
        
        elif args.data_type == 'support':
            success = upload_support(create_backup)
        
        elif args.data_type == 'all':
            if not args.file:
                logger.error("❌ --file argument required when uploading all data")
                sys.exit(1)
            
            # Upload products first
            logger.info("📦 Step 1: Uploading products...")
            success = upload_products(args.file, create_backup)
            
            if success:
                logger.info("🎧 Step 2: Uploading support data...")
                success = upload_support(create_backup)
        
        if success:
            logger.info("\n🎉 Data upload completed successfully!")
            logger.info("💡 The system will now load data from S3")
            if args.data_type in ['support', 'all']:
                logger.info("🔄 Run 'rebuild_embeddings.py' to update vector embeddings")
        else:
            logger.error("\n💥 Upload failed - check logs for details")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("\n❌ Upload cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n💥 Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 