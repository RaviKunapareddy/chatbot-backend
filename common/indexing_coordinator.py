"""
Simple File-Based Indexing Coordination

This module provides lightweight coordination between automatic and manual indexing
to prevent conflicts and provide visibility into indexing operations.

Uses simple file-based storage to avoid Redis dependency and complexity.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

# Coordination file location (in system temp directory for reliability)
COORDINATION_FILE = "/tmp/chatbot_indexing_coordination.json"


class IndexingCoordinator:
    """Simple file-based coordination for indexing operations"""

    @staticmethod
    def get_coordination_info() -> Optional[Dict[str, Any]]:
        """Get current indexing coordination information"""
        try:
            if not os.path.exists(COORDINATION_FILE):
                return None
                
            with open(COORDINATION_FILE, 'r') as f:
                data = json.load(f)
                
            # Validate data structure
            if not isinstance(data, dict):
                logger.warning("Invalid coordination file format")
                return None
                
            return data
            
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Could not read coordination file: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error reading coordination: {e}")
            return None

    @staticmethod
    def save_coordination_info(
        timestamp: str,
        source: str,
        operation: str = "index",
        product_count: int = 0,
        s3_timestamp: Optional[str] = None
    ) -> bool:
        """Save indexing coordination information"""
        try:
            coordination_data = {
                "last_indexed_timestamp": timestamp,
                "indexed_by": source,  # "automatic" or "manual_script"
                "operation": operation,  # "index", "clear_and_index", etc.
                "product_count": product_count,
                "s3_data_timestamp": s3_timestamp or timestamp,
                "coordination_version": "1.0"
            }
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(COORDINATION_FILE), exist_ok=True)
            
            with open(COORDINATION_FILE, 'w') as f:
                json.dump(coordination_data, f, indent=2)
                
            logger.info(f"📝 Saved coordination info: {source} {operation} at {timestamp}")
            return True
            
        except (OSError, json.JSONEncodeError) as e:
            logger.warning(f"Could not save coordination file: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error saving coordination: {e}")
            return False

    @staticmethod
    def check_recent_indexing(minutes: int = 10) -> Optional[Dict[str, Any]]:
        """Check if indexing happened recently (potential conflict)"""
        try:
            info = IndexingCoordinator.get_coordination_info()
            if not info:
                return None
                
            last_indexed = info.get("last_indexed_timestamp")
            if not last_indexed:
                return None
                
            # Parse timestamp
            try:
                last_time = datetime.fromisoformat(last_indexed.replace('Z', ''))
                now = datetime.now()
                time_diff = now - last_time
                
                if time_diff < timedelta(minutes=minutes):
                    return {
                        "indexed_by": info.get("indexed_by"),
                        "operation": info.get("operation"),
                        "minutes_ago": int(time_diff.total_seconds() / 60),
                        "timestamp": last_indexed
                    }
                    
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse timestamp {last_indexed}: {e}")
                
            return None
            
        except Exception as e:
            logger.warning(f"Error checking recent indexing: {e}")
            return None

    @staticmethod
    def should_skip_automatic_indexing(current_s3_timestamp: str) -> bool:
        """Check if automatic indexing should be skipped due to recent manual indexing"""
        try:
            info = IndexingCoordinator.get_coordination_info()
            if not info:
                return False  # No coordination info, proceed with indexing
                
            indexed_by = info.get("indexed_by")
            s3_data_timestamp = info.get("s3_data_timestamp")
            
            # Skip if manual script recently indexed the same or newer data
            if indexed_by == "manual_script" and s3_data_timestamp:
                if s3_data_timestamp >= current_s3_timestamp:
                    logger.info(f"✅ Manual script already indexed this data ({s3_data_timestamp}) - skipping automatic indexing")
                    return True
                    
            return False
            
        except Exception as e:
            logger.warning(f"Error checking coordination for automatic indexing: {e}")
            return False  # Error checking, proceed with indexing to be safe

    @staticmethod
    def clear_coordination_info() -> bool:
        """Clear coordination information (used when data changes)"""
        try:
            if os.path.exists(COORDINATION_FILE):
                os.remove(COORDINATION_FILE)
                logger.info("🔄 Cleared indexing coordination info - data was updated")
                return True
            return True  # File didn't exist, that's fine
            
        except OSError as e:
            logger.warning(f"Could not clear coordination file: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error clearing coordination: {e}")
            return False

    @staticmethod
    def get_status_summary() -> Dict[str, Any]:
        """Get human-readable status summary for monitoring"""
        try:
            info = IndexingCoordinator.get_coordination_info()
            if not info:
                return {"status": "no_coordination_info"}
                
            return {
                "status": "coordination_active",
                "last_indexed": info.get("last_indexed_timestamp", "unknown"),
                "indexed_by": info.get("indexed_by", "unknown"),
                "operation": info.get("operation", "unknown"),
                "product_count": info.get("product_count", 0),
                "s3_data_timestamp": info.get("s3_data_timestamp", "unknown")
            }
            
        except Exception as e:
            return {"status": "error", "error": str(e)}


# Global instance for easy access
indexing_coordinator = IndexingCoordinator()
