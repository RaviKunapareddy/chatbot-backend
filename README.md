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
scp -i ~/.ssh/your-ssh-key.pem -r . ubuntu@YOUR_SERVER_IP:/home/ubuntu/chatbot/

# SSH to your EC2 instance
ssh -i ~/.ssh/your-ssh-key.pem ubuntu@YOUR_SERVER_IP

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
curl https://your-domain.com/health
```

## 📚 Complete Documentation

For comprehensive guides beyond this quick-start:
- **📖 [Complete Documentation Hub](docs/README.md)** - Navigation to all guides
- **🏗️ [Deployment Guide](docs/deployment/guide.md)** - Detailed setup & architecture
- **⚙️ [Operations Manual](docs/deployment/operations.md)** - Daily operations & commands
- **🔧 [Troubleshooting](docs/deployment/troubleshooting.md)** - Problem resolution
- **💻 [Development Guide](docs/development/codebase-guide.md)** - Complete codebase walkthrough

### GitHub Webhook Setup

1. Go to your GitHub repository → Settings → Webhooks
2. Add webhook:
   - **URL**: `https://your-domain.com/webhook`
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

Example Pinecone variables in your .env:

```bash
# Pinecone (v6 API)
PINECONE_API_KEY=your_key_here
PINECONE_PRODUCTS_INDEX=chatbot-products
PINECONE_SUPPORT_INDEX=chatbot-support-knowledge
```

### Live Demo URLs (✅ CURRENTLY ACTIVE)

Your chatbot is available at:
- **Main API**: `https://your-domain.com`
- **API Docs**: `https://your-domain.com/docs` ← **Show this to recruiters!**
- **Health Check**: `https://your-domain.com/health`
- **GitHub Webhook**: `https://your-domain.com/webhook`

**🎯 DEPLOYMENT STATUS**: ✅ Live and operational (verified 2025-09-21)

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

### Option A: Conda (recommended for macOS/Homebrew Python)

Use the provided `environment.yml` which defines the environment name `chatbot-backend-dev`.

```bash
# Create and activate the conda environment
conda env create -f environment.yml
conda activate chatbot-backend-dev

# Optional: run mechanical formatting/lint pass
ruff check . --fix
black .

# Set up environment variables
cp .env.example .env
# Edit .env with your service credentials

# Run the application
uvicorn main:app --reload
```

### Option B: Python venv (alternative)

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
python -m pip install -r requirements.txt

# Optional: run mechanical formatting/lint pass
ruff check . --fix
black .

# Set up environment variables
cp .env.example .env
# Edit .env with your service credentials

# Run the application
uvicorn main:app --reload
```

### Dev-only local product data fallback

During development, if S3 access fails in `ProductS3Client.load_products()` (see `data/s3_client.py`), the app falls back to a local file: `data/products.json`.

- Supported formats: an array of products or an object with a `products` array.
- Intended for local/dev use only. In production, ensure S3 credentials and bucket are configured.

Example minimal file:
```json
[
  { "id": 1, "title": "Example", "price": 9.99 }
]
```

## Dependency Management

### Overview

This project uses a simplified dependency management approach:

- **requirements.txt**: Single source of truth for all dependencies (both production and development)
- **environment.yml**: Conda environment definition that references requirements.txt

### Key Points

- All Python package dependencies are defined in `requirements.txt` with pinned versions
- Production dependencies are listed first, followed by development dependencies
- The Conda environment (`environment.yml`) references only `requirements.txt` for pip dependencies
- No separate requirements-dev.txt file is used to simplify management

### Package Notes

- **Pinecone client**: This project uses the v6 API via `from pinecone import Pinecone`. Ensure your environment installs `pinecone-client==6.0.0` (already pinned in `requirements.txt`).
- **BeautifulSoup parser**: The code uses `BeautifulSoup(..., "html.parser")`. The `lxml` package is optional and not required for current parsing. If you prefer the `"lxml"` parser for performance/robustness at scale, install `lxml` and change the parser string accordingly.

## API Documentation

Once running (local or AWS), visit:
- **Swagger UI**: http://localhost:8000/docs (local) or https://your-domain.com/docs (AWS)
- **ReDoc**: http://localhost:8000/redoc (local) or https://your-domain.com/redoc (AWS)

## Server-side Tag Filtering

The product search supports server-side tag filtering via Pinecone metadata boolean flags.

- Enable with environment variable in your `.env`:

```bash
# Enables composing tag filters in Pinecone metadata (reduces false-empty results)
SEARCH_TAGS_SERVER_FILTER_ENABLED=true
```

- Query the search endpoint with comma-separated tags (AND semantics):

```bash
# Local example: single tag
curl 'http://localhost:8000/products/search?q=apple%20charger&limit=5&tags=electronics'

# Local example: brand + category + multiple tags
curl 'http://localhost:8000/products/search?q=phone&brand=Apple&category=mobile-accessories&tags=electronics,ios'

# Production example
curl 'https://your-domain.com/products/search?q=rolex&category=mens-watches&tags=watches'
```

Notes:
- When the flag is enabled, tags are filtered in Pinecone using boolean metadata keys like `tag_<normalized>`.
- Tag normalization: lowercase, trim, non-alphanumeric → `_`, collapse repeats, strip edges. Example: `"4K / Gaming" → tag_4k_gaming`.
- For backward compatibility, if the flag is disabled, a lightweight Python post-filter is applied.

## Production Features

This backend is production-ready with the following implemented features:

### ✅ Security & Performance
- **Rate Limiting**: 10 requests/minute/IP on chat endpoints (using slowapi)
- **Request Timeouts**: All external services have 5-10 second timeouts
- **Enhanced Health Checks**: Real connectivity testing for Redis and Pinecone
- **Comprehensive Logging**: Consistent logger usage with context-rich error tracking and stack traces
- **Daily Log Files**: Automatic log rotation with 7-day cleanup
- **Redis TTL**: 24-hour conversation cleanup to prevent memory leaks

### ✅ Service Reliability
- **Connection Management**: Timeout-protected connections to all services
- **Health Monitoring**: `/health` endpoint tests actual service connectivity
- **Graceful Startup**: Service validation during application startup
- **Error Handling**: Comprehensive logging with contextual error messages and stack traces
- **Logging Consistency**: Standardized logging across all modules with proper log levels

### ✅ Data Management
- **S3 Integration**: Product and support data loaded from cloud storage
- **Vector Search**: Unified Pinecone client for products and support RAG
- **Redis Caching**: Session management and conversation persistence
- **Dev-only fallback**: Local data fallback used during development if S3 is unavailable

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

**Live Demo**: [your-domain.com/docs](https://your-domain.com/docs) ← Interactive API documentation  
**Auto-Deploy**: Push code changes → Automatic deployment to AWS

## Testing

Run basic configuration tests with:
```bash
pytest
```

### Current Test Coverage

This project includes basic configuration validation tests:
- **Configuration loading**: `test_config_loading.py`
- **Service setup**: `simple_config_test.py`

### Service Validation

Instead of extensive integration tests, the application validates all services during startup:
- **Redis connectivity**: Tested in `services.py` during initialization
- **Pinecone availability**: Validated for both products and support indexes  
- **AWS S3 access**: Verified during product data loading
- **Health monitoring**: Available via `/health` endpoint for live service status

### Testing Environment Flags

The following environment variables control testing behavior:
- `FORCE_KEYWORD_FALLBACK=1`: Forces keyword-based intent classification (testing only)
- Various service credentials for configuration validation

**Note**: The application's startup sequence and health checks provide comprehensive service validation without requiring extensive integration test suites.

## Heuristics configuration (repo-local only)

Heuristic lists for the fallback classifier are configurable via a single repo-local file:

- Source of truth: `fallback_config/heuristics.json`

Only provided keys need to be specified; missing sections fall back to safe in-code defaults. There are no environment variable or S3 overrides for heuristics configuration.

Supported keys (examples):

```json
{
  "intent_keywords": {
    "cart": ["cart", "add", "remove", "buy"],
    "support": ["return", "shipping"],
    "recommendation": ["recommend", "popular"],
    "search": ["show", "find", "search"],
    "compare": ["compare", "vs", "which is better"]
  },
  "generic_nouns": ["phone", "phones", "laptop", "laptops", "tablet", "tablets"],
  "phrases": {
    "in_stock": ["in stock", "available now", "instock"],
    "out_of_stock": ["out of stock", "sold out", "unavailable"]
  },
  "rating_patterns": ["(\\d(?:\\.\\d)?)\\s*\\+\\s*stars"],
  "discount_patterns": ["(\\d{1,3})\\s*%\\s*(?:off|discount)"],
  "category_synonyms": { "smartphones": ["phone", "mobile"] },
  "brand_synonyms": {},
  "thresholds": { "fuzzy_similarity_brand": 90, "fuzzy_similarity_category": 90, "fuzzy_unambiguous_margin": 3 },
  "feature_flags": { "fallback_fuzzy_brand": false, "fallback_fuzzy_category": false }
}
```

Notes:
- The heuristics configuration is loaded exclusively from `fallback_config/heuristics.json`.
- Defaults are embedded for safety; behavior remains reasonable if the file is missing or partially specified.

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request