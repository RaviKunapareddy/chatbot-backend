# Logging Improvement Plan

Last updated: 2025-09-18

## Overview

This document outlines the plan for improving the logging system in the chatbot backend to ensure consistency and better debugging capabilities in production.

## Issues to Address

1. **Log Level Consistency**
   - Replace print() statements with proper logger calls
   - Ensure consistent log format across all modules

2. **Error Context Enhancement**
   - Add more context to exception logging
   - Improve traceability for debugging

## Implementation Plan

### 1. Replace print() Statements with Logger Calls

| File | Line | Current | Replacement |
|------|------|---------|-------------|
| main.py | 109 | `print(f"🚀 Initializing {settings.PROJECT_NAME} (ID: {settings.PROJECT_ID})...")` | `logger.info(f"🚀 Initializing {settings.PROJECT_NAME} (ID: {settings.PROJECT_ID})...")` |
| main.py | 112 | `print("🔍 Validating cloud service credentials...")` | `logger.info("🔍 Validating cloud service credentials...")` |
| main.py | 119 | `print("📦 Loading product data and initializing Pinecone vector database...")` | `logger.info("📦 Loading product data and initializing Pinecone vector database...")` |
| main.py | 122 | `print("✅ Backend fully initialized")` | `logger.info("✅ Backend fully initialized")` |
| main.py | 238-240 | `print("❌ Missing required cloud credentials:")` and `print(f"   - {cred}")` | `logger.error("❌ Missing required cloud credentials:")` and `logger.error(f"   - {cred}")` |
| main.py | 243 | `print("✅ All cloud credentials validated")` | `logger.info("✅ All cloud credentials validated")` |
| services.py | 125 | `print("✅ Redis connected successfully")` | `logger.info("✅ Redis connected successfully")` |
| services.py | 127 | `print(f"⚠️ Redis connection failed: {e}")` | `logger.warning(f"⚠️ Redis connection failed: {e}")` |
| services.py | 134 | `print("✅ Pinecone Products Search connected successfully")` | `logger.info("✅ Pinecone Products Search connected successfully")` |
| services.py | 143 | `print("✅ Pinecone Support RAG connected successfully")` | `logger.info("✅ Pinecone Support RAG connected successfully")` |
| llm/llm_service.py | 23 | `print("🤖 Initializing LLM Service...")` | `logger.info("🤖 Initializing LLM Service...")` |
| llm/llm_service.py | 35 | `print("✅ LLM Service ready")` | `logger.info("✅ LLM Service ready")` |
| llm/llm_service.py | 53 | `print("✅ AWS Bedrock LLM connected")` | `logger.info("✅ AWS Bedrock LLM connected")` |
| llm/llm_service.py | 55 | `print(f"⚠️ AWS Bedrock unavailable: {e}")` | `logger.warning(f"⚠️ AWS Bedrock unavailable: {e}")` |
| llm/llm_service.py | 65 | `print("✅ Google Gemini LLM connected")` | `logger.info("✅ Google Gemini LLM connected")` |
| llm/llm_service.py | 67 | `print(f"⚠️ Google Gemini unavailable: {e}")` | `logger.warning(f"⚠️ Google Gemini unavailable: {e}")` |
| llm/llm_service.py | 139 | `print(f"❌ AWS Bedrock error: {e}")` | `logger.error(f"❌ AWS Bedrock error: {e}")` |
| llm/llm_service.py | 147 | `print(f"❌ Google Gemini error: {e}")` | `logger.error(f"❌ Google Gemini error: {e}")` |
| support_docs/support_loader.py | 23 | `print("⚠️ Pinecone not available. Using fallback support responses.")` | `logger.warning("⚠️ Pinecone not available. Using fallback support responses.")` |
| support_docs/support_loader.py | 37 | `print(f"✅ Loaded {len(support_docs)} support documents from S3")` | `logger.info(f"✅ Loaded {len(support_docs)} support documents from S3")` |
| support_docs/support_loader.py | 39 | `print("⚠️ No support data found in S3, falling back to generation")` | `logger.warning("⚠️ No support data found in S3, falling back to generation")` |
| support_docs/support_loader.py | 42 | `print(f"⚠️ S3 loading failed: {s3_error}, falling back to generation")` | `logger.warning(f"⚠️ S3 loading failed: {s3_error}, falling back to generation")` |
| support_docs/support_loader.py | 47 | `print("🔄 Generating support data from products and FAQs...")` | `logger.info("🔄 Generating support data from products and FAQs...")` |
| support_docs/support_loader.py | 57 | `print(f"📊 Generated {len(all_support_docs)} support documents")` | `logger.info(f"📊 Generated {len(all_support_docs)} support documents")` |
| support_docs/support_loader.py | 60 | `print("🔄 Updating Pinecone support knowledge base...")` | `logger.info("🔄 Updating Pinecone support knowledge base...")` |
| deployment/webhook.py | 21 | `print("❌ GITHUB_WEBHOOK_SECRET environment variable required")` | `logger.error("❌ GITHUB_WEBHOOK_SECRET environment variable required")` |
| deployment/webhook.py | 51 | `print(f"🎣 Received {event} webhook from {repo}")` | `logger.info(f"🎣 Received {event} webhook from {repo}")` |
| deployment/webhook.py | 56 | `print("🚀 Triggering auto-deployment...")` | `logger.info("🚀 Triggering auto-deployment...")` |
| deployment/webhook.py | 77 | `print("✅ Deployment successful")` | `logger.info("✅ Deployment successful")` |
| deployment/webhook.py | 80 | `print(f"❌ Deployment failed: {result.stderr}")` | `logger.error(f"❌ Deployment failed: {result.stderr}")` |
| deployment/webhook.py | 98 | `print("🎣 Starting GitHub webhook server on port 5005...")` | `logger.info("🎣 Starting GitHub webhook server on port 5005...")` |

### 2. Enhance Exception Logging with More Context

| File | Line | Current | Enhanced |
|------|------|---------|----------|
| router/intent_classifier.py | 108 | `logger.error(f"AWS Bedrock initialization failed: {e}")` | `logger.error(f"AWS Bedrock initialization failed for intent classification: {e}", exc_info=True)` |
| router/intent_classifier.py | 123 | `logger.error(f"Google Gemini initialization failed: {e}")` | `logger.error(f"Google Gemini initialization failed for intent classification: {e}", exc_info=True)` |
| router/intent_classifier.py | 348 | `logger.error(f"Bedrock classification error: {e}")` | `logger.error(f"Bedrock intent classification error for query: {e}", exc_info=True)` |
| router/intent_classifier.py | 450 | `logger.error(f"Gemini classification error: {e}")` | `logger.error(f"Gemini intent classification error for query: {e}", exc_info=True)` |
| router/chat.py | 86 | `logger.error(f"Chat processing error: {e}")` | `logger.error(f"Chat processing error for session {session_id}: {e}", exc_info=True)` |
| router/chat.py | 883 | `logger.error(f"Error in support RAG: {e}")` | `logger.error(f"Error in support RAG for query '{user_message}': {e}", exc_info=True)` |
| main.py | 204 | `usage_info = {"error": "Could not retrieve usage stats", "details": str(e)}` | `logger.error(f"Failed to retrieve usage stats: {e}", exc_info=True)` and keep current line |
| main.py | 302 | `return {"error": f"Failed to fetch products: {str(e)}", "products": []}` | `logger.error(f"Failed to fetch products with category={category}: {e}", exc_info=True)` and keep current line |
| main.py | 353 | `return {"error": f"Search failed: {str(e)}", "products": []}` | `logger.error(f"Product search failed for query '{q}': {e}", exc_info=True)` and keep current line |
| vector_service/pinecone_client.py | 126 | `logger.error(f"❌ Pinecone initialization failed: {e}")` | `logger.error(f"❌ Pinecone initialization failed for index '{self.index_name}': {e}", exc_info=True)` |
| vector_service/pinecone_client.py | 195 | `logger.warning(f"Error getting embedding from API (attempt {attempt}/{max_retries}): {e}")` | `logger.warning(f"Error getting embedding from API for text '{text[:30]}...' (attempt {attempt}/{max_retries}): {e}", exc_info=True)` |

## Implementation Progress Tracking

- [x] Replace print() statements with logger calls
- [x] Enhance exception logging with more context
- [x] Test logging in development environment
- [x] Verify log output format and content
- [x] Update documentation

## Benefits

1. **Consistency**: All log messages will follow the same format and appear in the same log files
2. **Traceability**: Enhanced context will make it easier to trace issues in production
3. **Filtering**: Proper log levels will allow filtering logs by severity
4. **Monitoring**: Improved logs will be more suitable for log aggregation and monitoring tools

## Notes

- All logger calls should include appropriate emoji prefixes for visual scanning
- Exception logging should include `exc_info=True` for stack traces where helpful
- Context should include relevant identifiers (session_id, query text, etc.)
