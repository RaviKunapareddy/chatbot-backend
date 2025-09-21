# Chatbot-Backend Codebase Debugging Plan

**Last Updated:** 2025-09-18

This document outlines our systematic approach to debugging the chatbot-backend codebase folder by folder. We'll track progress here as we complete each section.

## Debugging Progress Tracker

| Folder | Status | Notes |
|--------|--------|-------|
| common/ | 🔄 In Progress | |
| fallback_config/ | ⏱️ Pending | |
| data/ | ⏱️ Pending | |
| deployment/ | ✅ Completed | Logging improvements implemented |
| docs/ | ✅ Completed | Documentation review complete |
| frontend/ | ⏱️ Pending | |
| llm/ | ✅ Completed | Logging improvements implemented |
| memory/ | ⏱️ Pending | |
| router/ | ✅ Completed | Logging improvements implemented |
| search/ | ⏱️ Pending | |
| support_docs/ | ✅ Completed | Logging improvements implemented |
| test/ | ⏱️ Pending | |
| vector_service/ | ✅ Completed | Logging improvements implemented |

## Specific Tasks

### 1. common/
- [ ] Review `heuristics.py` for configuration loading issues
- [ ] Check `limiter.py` for rate limiting functionality
- [ ] Verify environment variable handling

### 2. fallback_config/
- [ ] Validate `heuristics.json` structure and content
- [ ] Check for any missing configuration keys

### 3. data/
- [ ] Test S3 client connectivity
- [ ] Verify data uploader functionality
- [ ] Check product data format

### 4. deployment/
- [ ] Review webhook functionality
- [ ] Test deployment scripts
- [ ] Verify reindexing process

### 5. docs/
- [x] Ensure documentation is up-to-date
- [x] Check enhancement plan alignment with code

### 6. frontend/
- [ ] Test API connectivity
- [ ] Verify React component rendering
- [ ] Check proxy configuration

### 7. llm/
- [ ] Test AWS Bedrock connectivity
- [ ] Test Google Gemini fallback
- [ ] Verify response formatting

### 8. memory/
- [ ] Test Redis connectivity
- [ ] Verify conversation history management
- [ ] Check session persistence

### 9. router/
- [ ] Test chat endpoint functionality
- [ ] Verify intent classification accuracy
- [ ] Check error handling

### 10. search/
- [ ] Test product data loading
- [ ] Verify search functionality
- [ ] Check filtering and sorting

### 11. support_docs/
- [ ] Test support knowledge base loading
- [ ] Verify RAG functionality
- [ ] Check policy scraping

### 12. test/
- [ ] Run live-gated integration tests
- [ ] Remove diagnostic tools (like `test_connections.py`)
- [ ] Verify test coverage

### 13. vector_service/
- [ ] Test Pinecone connectivity
- [ ] Verify embedding generation
- [ ] Check vector search functionality

## High-Priority Issues

1. [ ] Remove `test_connections.py` diagnostic tool
2. [x] Consolidated environment files into single `.env`

## Testing Commands

```bash
# Activate the conda environment
conda activate chatbot-backend-dev

# Run the integration tests with live services
RUN_LIVE_TESTS=1 RUN_LIVE_MEMORY_TESTS=1 pytest test/test_multiturn_flow.py -v

# Test specific components
python -c "from vector_service.pinecone_client import pinecone_products_client; print(pinecone_products_client.health_check())"
python -c "from memory.conversation_memory import conversation_memory; print(conversation_memory.is_available())"

# Check application logs
tail -f logs/app_$(date +%Y-%m-%d).log
```

## Logging System

The codebase now uses a standardized logging approach across all modules:

```python
# Module-level logger initialization
import logging
logger = logging.getLogger(__name__)

# Info level logging with emoji for visual scanning
logger.info("✅ Service connected successfully")

# Warning level for non-critical issues
logger.warning("⚠️ Service degraded but operational")

# Error level with context and stack trace
logger.error(f"❌ Error in operation: {error_details}", exc_info=True)
```

Key logging features:
- Daily log rotation with 7-day retention
- Consistent emoji prefixes for visual scanning
- Context-rich error messages with relevant parameters
- Stack traces for all exceptions
- Standard log format across all modules

## Debugging Approach

1. For each folder:
   - Run relevant tests first
   - Check logs for errors or warnings
   - Verify connectivity to external services
   - Test functionality with simple inputs
   - Document any issues found

2. Focus on core services first:
   - Start with `vector_service/` and `memory/` as they're foundational
   - Then move to `llm/` and `search/`
   - Finally test the integration points in `router/`

3. Update this document after completing each folder's debugging
