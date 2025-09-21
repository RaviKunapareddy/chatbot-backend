"""
Conversation Memory Management

This module implements:
- Redis-backed conversation buffer for 6-message history
- User session tracking with persistence
- Context preservation across server restarts
- Memory-aware response generation
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Optional

import redis
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class ConversationMemory:
    """Manages conversation history and context using Redis for persistence"""

    def __init__(self, max_messages: int = 6):
        self.max_messages = max_messages

        # Initialize Redis connection
        self.redis_client = self._init_redis()

        # Redis key prefixes
        self.conversation_prefix = "conv:"
        self.context_prefix = "ctx:"
        self.activity_prefix = "act:"

    def _init_redis(self):
        """Initialize Redis connection - required for production"""
        try:
            from urllib.parse import quote

            # Prefer REDIS_URL if set, otherwise build from individual variables
            redis_url = os.getenv("REDIS_URL")
            if not redis_url:
                host = os.getenv("REDIS_HOST")
                port = os.getenv("REDIS_PORT", "6379")
                db = os.getenv("REDIS_DB", "0")
                username = os.getenv("REDIS_USERNAME", "default")
                password = os.getenv("REDIS_PASSWORD", "")
                encoded_pw = quote(password)
                # Safe logging without exposing secrets
                masked_pw = "***" if password else ""
                logger.info(
                    f"Connecting to Redis with: redis://{username}:{masked_pw}@{host}:{port}/{db}"
                )
                redis_url = f"redis://{username}:{encoded_pw}@{host}:{port}/{db}"
            else:
                logger.info("Connecting to Redis with REDIS_URL (password masked)")
            client = redis.from_url(redis_url, decode_responses=True)
            # Test connection
            client.ping()
            logger.info("✅ Redis connected successfully")
            return client
        except Exception as e:
            logger.exception(f"❌ Redis connection failed: {e.__class__.__name__}: {e}")
            raise Exception(f"Redis connection required but failed: {e}")

    def _is_redis_available(self) -> bool:
        """Check if Redis is available"""
        return hasattr(self.redis_client, "ping")

    def add_message(
        self, session_id: str, user_message: str, bot_response: str, intent: str = None
    ):
        """Add user message and bot response to memory"""
        exchange = {
            "user": user_message,
            "bot": bot_response,
            "intent": intent,
            "timestamp": datetime.now().isoformat(),
        }

        # Redis implementation only
        conv_key = f"{self.conversation_prefix}{session_id}"

        # Get existing conversation
        existing = self.redis_client.lrange(conv_key, 0, -1)
        conversations = [json.loads(msg) for msg in existing]

        # Add new exchange
        conversations.append(exchange)

        # Keep only last max_messages
        if len(conversations) > self.max_messages:
            conversations = conversations[-self.max_messages :]

        # Store back to Redis
        self.redis_client.delete(conv_key)
        for conv in conversations:
            self.redis_client.rpush(conv_key, json.dumps(conv))

        # Set expiration (24 hours)
        self.redis_client.expire(conv_key, 86400)

        # Update last activity
        activity_key = f"{self.activity_prefix}{session_id}"
        self.redis_client.set(activity_key, datetime.now().isoformat(), ex=86400)

    def get_context(self, session_id: str) -> str:
        """Get conversation context for user"""
        # Redis implementation only
        conv_key = f"{self.conversation_prefix}{session_id}"
        conversations = self.redis_client.lrange(conv_key, -5, -1)  # Last 5 exchanges

        if not conversations:
            return ""

        context_parts = []
        for conv_json in conversations:
            exchange = json.loads(conv_json)
            context_parts.append(f"User: {exchange['user']}")
            context_parts.append(f"Bot: {exchange['bot']}")

        return "\n".join(context_parts)

    def get_recent_intent(self, session_id: str) -> Optional[str]:
        """Get the most recent intent from conversation"""
        # Redis implementation only
        conv_key = f"{self.conversation_prefix}{session_id}"
        last_exchange = self.redis_client.lrange(conv_key, -1, -1)

        if last_exchange:
            exchange = json.loads(last_exchange[0])
            return exchange.get("intent")
        return None

    def update_context(self, session_id: str, key: str, value: Any):
        """Update context information for session"""
        # Redis implementation only
        ctx_key = f"{self.context_prefix}{session_id}"
        context = {}

        # Get existing context
        existing_context = self.redis_client.get(ctx_key)
        if existing_context:
            context = json.loads(existing_context)

        # Update and store
        context[key] = value
        self.redis_client.set(ctx_key, json.dumps(context), ex=86400)

    def get_context_value(self, session_id: str, key: str) -> Any:
        """Get specific context value"""
        # Redis implementation only
        ctx_key = f"{self.context_prefix}{session_id}"
        context_json = self.redis_client.get(ctx_key)

        if context_json:
            context = json.loads(context_json)
            return context.get(key)
        return None

    def has_context(self, session_id: str) -> bool:
        """Check if session has conversation history"""
        # Redis implementation only
        conv_key = f"{self.conversation_prefix}{session_id}"
        return self.redis_client.llen(conv_key) > 0

    def clear_memory(self, session_id: str):
        """Clear conversation history for session"""
        # Redis implementation only
        conv_key = f"{self.conversation_prefix}{session_id}"
        ctx_key = f"{self.context_prefix}{session_id}"
        activity_key = f"{self.activity_prefix}{session_id}"

        self.redis_client.delete(conv_key, ctx_key, activity_key)

    def cleanup_inactive_sessions(self, timeout_minutes: int = 30):
        """Remove sessions inactive for more than timeout_minutes"""
        # Redis TTL handles this automatically
        logger.info("✅ Redis TTL handles session cleanup automatically")


# Global memory instance
conversation_memory = ConversationMemory()
