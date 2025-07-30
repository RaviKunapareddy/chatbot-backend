# AI Chatbot Backend

A modern AI chatbot backend built with FastAPI, featuring cloud-only services:
- **Pinecone Cloud** for vector search and RAG support
- **Redis Cloud** for conversation caching
- **AWS S3** for product data storage
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
- Product search with Pinecone vector search
- Support RAG with Pinecone
- Multi-LLM chat capabilities
- S3-based product catalog

## 🚀 AWS Deployment (Recruiter Demo Ready)

**Professional deployment system for AWS EC2 with GitHub webhook automation.**

### What This Deployment Provides
- **Live AWS Demo**: Working chatbot URL for recruiters to test
- **GitHub Auto-Deploy**: Push code changes, they deploy automatically  
- **Production Setup**: Nginx, systemd services, proper security
- **Simple Management**: Easy start/stop/restart commands

### Quick Setup (5 Minutes)

#### 1. Upload Files to EC2
```bash
# Copy your chatbot code to EC2
scp -i your-key.pem -r . ubuntu@YOUR_EC2_IP:/home/ubuntu/chatbot/

# SSH to your EC2 instance
ssh -i your-key.pem ubuntu@YOUR_EC2_IP

# Move files to deployment location
sudo mv /home/ubuntu/chatbot/* /opt/chatbot/
```

#### 2. Run Setup
```bash
cd /opt/chatbot/deployment
chmod +x *.sh
./initial_setup.sh
```

#### 3. Configure Environment  
```bash
# Edit with your actual service credentials
sudo nano /opt/chatbot/.env

# Start services
sudo systemctl start chatbot chatbot-webhook
```

#### 4. Test Everything
```bash
# Check status
./service_manager.sh status

# Test your API
curl http://YOUR_EC2_IP/health
```

### GitHub Webhook Setup

1. Go to your GitHub repository → Settings → Webhooks
2. Add webhook:
   - **URL**: `http://YOUR_EC2_IP/webhook`
   - **Content type**: `application/json`  
   - **Secret**: Use the same value as `GITHUB_WEBHOOK_SECRET` in your `.env`
   - **Events**: Just push events

Now when you push to main branch, your chatbot auto-updates! 🎉

### Daily Operations

```bash
# Check if everything is running
./service_manager.sh status

# View live logs
./service_manager.sh logs

# Restart services (after config changes)
./service_manager.sh restart

# Manual update from GitHub
./service_manager.sh update

# See all available commands
./service_manager.sh
```

### Required Environment Variables

Edit `/opt/chatbot/.env` with your service credentials:

- **AWS**: Access keys, S3 bucket, Bedrock model
- **Google**: API key for Gemini
- **Pinecone**: API key for vector storage (products and support)
- **Redis**: Host, password for caching  
- **HuggingFace**: API key for embeddings
- **GitHub**: Webhook secret for auto-deployment

### Live Demo URLs

After setup, your chatbot will be available at:
- **Main API**: `http://YOUR_EC2_IP`
- **API Docs**: `http://YOUR_EC2_IP/docs` ← **Show this to recruiters!**
- **Health Check**: `http://YOUR_EC2_IP/health`
- **GitHub Webhook**: `http://YOUR_EC2_IP/webhook`

### Troubleshooting

```bash
# Services not starting?
./service_manager.sh status
sudo journalctl -u chatbot -n 20

# Environment issues?
cat /opt/chatbot/.env
source /opt/chatbot/venv/bin/activate && python -c "import os; print('Redis:', os.getenv('REDIS_HOST'))"

# Webhook not working?
curl -X POST http://localhost:5005/health
tail -f /var/log/nginx/error.log
```

## Local Development Setup

For local development and testing:

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

Once running (local or AWS), visit:
- **Swagger UI**: http://localhost:8000/docs (local) or http://YOUR_EC2_IP/docs (AWS)
- **ReDoc**: http://localhost:8000/redoc (local) or http://YOUR_EC2_IP/redoc (AWS)

## Production Features

This backend is production-ready with the following implemented features:

### ✅ Security & Performance
- **Rate Limiting**: 10 requests/minute/IP on chat endpoints (using slowapi)
- **Request Timeouts**: All external services have 5-10 second timeouts
- **Enhanced Health Checks**: Real connectivity testing for Redis and Pinecone
- **Daily Log Files**: Automatic log rotation with 7-day cleanup
- **Redis TTL**: 24-hour conversation cleanup to prevent memory leaks

### ✅ Service Reliability
- **Connection Management**: Timeout-protected connections to all services
- **Health Monitoring**: `/health` endpoint tests actual service connectivity
- **Graceful Startup**: Service validation during application startup
- **Error Handling**: Comprehensive logging with structured error messages

### ✅ Data Management
- **S3 Integration**: Product and support data loaded from cloud storage
- **Vector Search**: Unified Pinecone client for products and support RAG
- **Redis Caching**: Session management and conversation persistence
- **Fallback Mechanisms**: Local data fallback if S3 is unavailable

### 🔄 Future Enhancements
- Connection pooling for higher concurrency
- Load balancing for multiple instances
- Advanced monitoring and alerting
- Automated scaling based on usage

## For Recruiters

This project demonstrates:

✅ **Modern AI Architecture**: Multi-LLM support, vector search, RAG implementation  
✅ **Production Deployment**: Professional AWS setup with auto-deployment  
✅ **Clean Code**: Well-structured FastAPI application with proper separation of concerns  
✅ **Cloud Integration**: Real-world cloud services (Redis, Pinecone, S3)  
✅ **DevOps Skills**: GitHub webhooks, systemd services, Nginx configuration  

**Live Demo**: [YOUR_EC2_IP/docs] ← Interactive API documentation  
**Auto-Deploy**: Push code changes → Automatic deployment to AWS

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