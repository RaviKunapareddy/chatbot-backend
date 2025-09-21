# Chatbot Greeting and Mid-Conversation Handling

Last updated: 2025-09-18

## Overview

This document describes the implementation of greeting detection and mid-conversation handling in the chatbot. The system now intelligently detects greeting messages and provides appropriate responses based on whether it's an initial greeting or a mid-conversation social message.

## Implementation Details

### 1. Intent Classification

The chatbot now recognizes a new "GREETING" intent through both LLM-based classification and keyword-based fallback:

- **LLM-based Detection**: Both AWS Bedrock and Google Gemini models have been updated to recognize greeting patterns
- **Keyword-based Fallback**: For simple greetings or when LLMs are unavailable
- **Examples**: "hi", "hello", "how are you", "good morning", etc.

### 2. Greeting Handler

A new `handle_greeting` function in `router/chat.py` provides context-aware responses:

- **Initial Greetings**: Welcoming messages that introduce the chatbot's capabilities
- **Mid-conversation Greetings**: Friendly acknowledgments that redirect to shopping
- **Product Context**: References previously viewed product categories to maintain conversation flow

### 3. Session Awareness

The greeting handler uses Redis-based conversation memory to:
- Determine if a greeting is initial or mid-conversation
- Retrieve previous product context
- Reference previous products in responses

## Usage Notes

### Session Management

- Session IDs persist in Redis with conversation history
- New sessions receive initial greeting responses
- Existing sessions receive context-aware mid-conversation responses
- To test with a fresh session, use a unique session ID or clear browser storage

### Testing

To test with a new session via curl:
```bash
curl -X POST http://localhost:8002/chat -H "Content-Type: application/json" -d '{"message": "hi", "session_id": "new_session_id"}'
```

To test in the browser:
1. Clear local storage in developer tools
2. Refresh the page
3. Or use an incognito/private window

## Integration with Follow-up Detection

This greeting implementation complements the follow-up detection system:
- Both use the same conversation memory system
- Both maintain context across multiple exchanges
- Together they provide a more natural conversation experience

## Future Enhancements

Potential improvements to consider:
- Time-based session expiration (e.g., treat as new session after 24 hours)
- More sophisticated greeting detection for complex social messages
- Personalization based on user preferences and history
