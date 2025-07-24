# AI Chatbot Backend

A modern AI chatbot backend built with FastAPI, featuring cloud-only services:
- **Elasticsearch Cloud** for hybrid vector search
- **Redis Cloud** for conversation caching
- **AWS S3** for product data storage
- **Pinecone Cloud** for RAG support
- **Multi-LLM support** (AWS Bedrock, Google Gemini)
- **HuggingFace Cloud** for embedding generation

## Cloud-Only Implementation

This implementation is designed for production cloud deployment:

### Architecture
- **100% Cloud Services** - No localhost fallbacks
- **Credential Validation** - Startup validation of all required credentials
- **S3-Based Data** - All data sourced from cloud storage
- **Secure Connections** - HTTPS/TLS for all service connections

### Features
- Product search with Elasticsearch
- Support RAG with Pinecone
- Multi-LLM chat capabilities
- S3-based product catalog

## Production Considerations

For production deployment, consider the following enhancements:

### Connection Management
- Implement connection pooling for Redis and Elasticsearch
- Add automatic reconnection logic
- Add connection health monitoring
- Implement circuit breakers

### Data Management
- Add Redis caching for products
- Implement lazy loading
- Add cache invalidation
- Add data refresh mechanisms

### Error Handling
- Add comprehensive error logging
- Implement retry mechanisms
- Add graceful degradation
- Monitor service health

### Performance
- Add request/response logging
- Implement performance monitoring
- Add load balancing
- Optimize search queries

### Security
- Implement rate limiting
- Add request validation
- Enhance error messages
- Add security headers

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your service credentials
```

3. Run the application:
```bash
uvicorn main:app --reload
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Testing

Run tests with:
```bash
pytest
```

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request 