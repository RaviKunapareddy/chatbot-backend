"""
Manual Product Reindexing for Pinecone (safe, opt-in)

This script loads products from S3 (or local fallback), optionally clears
existing product vectors in Pinecone, and reindexes products using the
existing Pinecone client and embedding pipeline.

Usage:
  python vector_service/manual_reindex_products.py --dry-run
  python vector_service/manual_reindex_products.py --limit 100 --yes
  python vector_service/manual_reindex_products.py --clear --yes

Flags:
  --clear   Clear only product vectors first (filter={"type":"product"}).
  --limit   Index only first N products (for testing).
  --dry-run Load and report counts without writing to Pinecone.
  --yes     Skip interactive confirmations.
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables
load_dotenv()

from data.s3_client import s3_client  # noqa: E402
from .pinecone_client import pinecone_products_client  # noqa: E402
from common.indexing_coordinator import indexing_coordinator  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("manual_reindex_products")


def confirm(prompt: str, assume_yes: bool = False) -> bool:
    if assume_yes:
        return True
    try:
        resp = input(f"{prompt} (y/N): ").strip().lower()
        return resp in ("y", "yes")
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return False


def main():
    parser = argparse.ArgumentParser(description="Manually reindex products into Pinecone")
    parser.add_argument(
        "--clear", action="store_true", help="Clear product vectors before reindexing"
    )
    parser.add_argument("--limit", type=int, default=None, help="Only index first N products")
    parser.add_argument(
        "--dry-run", action="store_true", help="Do not write to Pinecone; show counts only"
    )
    parser.add_argument("--yes", action="store_true", help="Skip interactive confirmations")
    args = parser.parse_args()

    # Check Pinecone availability
    if not pinecone_products_client.is_available():
        logger.error(
            "❌ Pinecone is not available. Set PINECONE_API_KEY and index env vars, then retry."
        )
        sys.exit(1)

    # Load products
    products: List[Dict[str, Any]] = s3_client.load_products(force_refresh=True)
    total = len(products or [])
    logger.info(f"📦 Loaded {total} products from S3/local")
    
    # Get S3 timestamp for coordination
    s3_timestamp = s3_client.get_products_last_modified()

    if args.limit is not None and args.limit >= 0:
        products = products[: args.limit]
        logger.info(f"⚠️ Limiting to first {len(products)} products as requested")

    if args.dry_run:
        logger.info("✅ Dry-run complete. Nothing was written to Pinecone.")
        sys.exit(0)

    # Check for potential coordination conflicts
    recent_indexing = indexing_coordinator.check_recent_indexing(minutes=10)
    if recent_indexing and not args.yes:
        indexed_by = recent_indexing.get("indexed_by")
        minutes_ago = recent_indexing.get("minutes_ago", 0)
        operation = recent_indexing.get("operation", "unknown")
        
        logger.warning(f"⚠️ Recent indexing detected:")
        logger.warning(f"   Indexed by: {indexed_by}")
        logger.warning(f"   Operation: {operation}")
        logger.warning(f"   Time: {minutes_ago} minutes ago")
        
        if not confirm("Continue despite recent indexing activity?", assume_yes=args.yes):
            logger.info("❌ Aborted due to potential coordination conflict.")
            sys.exit(1)

    # Optionally clear product vectors first
    if args.clear:
        if not confirm(
            "This will DELETE all product vectors in Pinecone. Continue?", assume_yes=args.yes
        ):
            logger.info("❌ Aborted by user.")
            sys.exit(1)
        ok = pinecone_products_client.clear_index({"type": "product"})
        if not ok:
            logger.error("❌ Failed to clear product vectors. Aborting.")
            sys.exit(1)
        logger.info("🧹 Cleared existing product vectors.")

    # Confirm indexing
    if not confirm(
        f"Proceed to index {len(products)} products into Pinecone?", assume_yes=args.yes
    ):
        logger.info("❌ Aborted by user.")
        sys.exit(1)

    # Index
    ok = pinecone_products_client.index_products(products)
    if not ok:
        logger.error("❌ Reindexing failed.")
        sys.exit(1)

    # Update coordination info after successful indexing
    operation = "clear_and_index" if args.clear else "index"
    indexing_coordinator.save_coordination_info(
        timestamp=datetime.now().isoformat(),
        source="manual_script",
        operation=operation,
        product_count=len(products),
        s3_timestamp=s3_timestamp
    )

    # Health
    health = pinecone_products_client.get_health()
    logger.info(f"✅ Manual reindexing complete. Pinecone status: {health}")


if __name__ == "__main__":
    main()
