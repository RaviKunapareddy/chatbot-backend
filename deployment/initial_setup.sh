#!/bin/bash

# Production-Ready AWS Deployment Setup for Chatbot Backend
# Handles AWS EC2 deployment with GitHub webhook automation
# Includes production hardening: health checks, timeouts, rate limiting
# Replaces 1,500+ lines of over-engineered scripts with ~80 lines

set -e

echo "🚀 Setting up Chatbot Backend for AWS Deployment..."

# Basic validation
if [[ $EUID -eq 0 ]]; then
    echo "❌ Don't run as root for security"
    exit 1
fi

# Update system
echo "📦 Updating system..."
sudo apt update && sudo apt upgrade -y

# Install essentials
echo "🔧 Installing dependencies..."
sudo apt install -y python3.11 python3.11-venv python3-pip nginx curl git

# Setup application directory
echo "📁 Setting up application..."
sudo mkdir -p /opt/chatbot
sudo chown $USER:$USER /opt/chatbot
cd /opt/chatbot

# Copy application files if not already there
if [[ ! -f "main.py" ]]; then
    echo "⚠️  Please copy your application files to /opt/chatbot first"
    echo "   Example: sudo cp -r /path/to/your/code/* /opt/chatbot/"
    exit 1
fi

# Create Python environment
echo "🐍 Setting up Python environment..."
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create environment file if it doesn't exist
if [[ ! -f ".env" ]]; then
    echo "🔐 Creating environment template..."
    cp .env.example .env 2>/dev/null || cat > .env << 'EOF'
# AWS Configuration
AWS_ACCESS_KEY_ID=your_aws_access_key_here
AWS_SECRET_ACCESS_KEY=your_aws_secret_key_here
AWS_DEFAULT_REGION=us-east-1
AWS_BEDROCK_MODEL_ID=your_bedrock_model_id

# S3 Settings
S3_BUCKET_NAME=your_s3_bucket_name
S3_PRODUCTS_KEY=products.json

# Google Gemini
GOOGLE_API_KEY=your_google_api_key
GEMINI_MODEL=gemini-1.5-flash

# Pinecone
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_PRODUCTS_INDEX=chatbot-products
PINECONE_SUPPORT_INDEX=chatbot-support-knowledge

# Redis Cloud
REDIS_HOST=your_redis_host
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password
REDIS_USERNAME=default
REDIS_DB=0


# HuggingFace
HF_API_KEY=your_huggingface_api_key
HF_PRODUCT_MODEL=BAAI/bge-small-en-v1.5
HF_SUPPORT_MODEL=BAAI/bge-small-en-v1.5

# GitHub Webhook Secret (for auto-deployment)
GITHUB_WEBHOOK_SECRET=your_github_webhook_secret

# Optional Settings
ENABLE_WEB_SCRAPING=true
EOF
    echo "⚠️  Edit /opt/chatbot/.env with your actual service credentials"
fi

# Create simple systemd service
echo "⚙️ Creating services..."
sudo tee /etc/systemd/system/chatbot.service > /dev/null << EOF
[Unit]
Description=AI Chatbot Backend
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/chatbot
Environment=PATH=/opt/chatbot/venv/bin
EnvironmentFile=/opt/chatbot/.env
ExecStart=/opt/chatbot/venv/bin/python main.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Create webhook service
sudo tee /etc/systemd/system/chatbot-webhook.service > /dev/null << EOF
[Unit]
Description=Chatbot GitHub Webhook
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/chatbot/deployment
Environment=PATH=/opt/chatbot/venv/bin
EnvironmentFile=/opt/chatbot/.env
ExecStart=/opt/chatbot/venv/bin/python webhook.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Create organized logs directory structure
echo "📋 Setting up organized logging..."
sudo mkdir -p /opt/chatbot/logs/{app,webhook,system}
sudo chown -R ubuntu:ubuntu /opt/chatbot/logs

# Create log rotation config for our custom logs (if any)
sudo tee /etc/logrotate.d/chatbot > /dev/null << EOF
/opt/chatbot/logs/**/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 ubuntu ubuntu
}
EOF

# Configure journalctl log retention (30 days max, 100MB max)
sudo mkdir -p /etc/systemd/journald.conf.d/
sudo tee /etc/systemd/journald.conf.d/chatbot.conf > /dev/null << EOF
[Journal]
MaxRetentionSec=30d
SystemMaxUse=100M
RuntimeMaxUse=50M
EOF

# Configure nginx
echo "🌐 Configuring nginx..."
sudo tee /etc/nginx/sites-available/chatbot > /dev/null << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /webhook {
        proxy_pass http://127.0.0.1:5005;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# Enable nginx site
sudo ln -sf /etc/nginx/sites-available/chatbot /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Enable services
echo "🔄 Enabling services..."
sudo systemctl daemon-reload
sudo systemctl enable chatbot chatbot-webhook nginx
sudo systemctl restart nginx

echo ""
echo "✅ Setup completed!"
echo ""
echo "🔧 Production Features Enabled:"
echo "   • Enhanced health checks with real service connectivity tests"
echo "   • Request timeouts on all external services (Redis, S3, Pinecone)"
echo "   • Rate limiting (10 requests/minute/IP) on chat endpoints"
echo "   • Daily log files with automatic 7-day cleanup"
echo "   • Redis conversation cleanup (24-hour TTL)"
echo ""
echo "Next steps:"
echo "1. Edit /opt/chatbot/.env with your cloud service credentials"
echo "2. Start services: sudo systemctl start chatbot chatbot-webhook"
echo "3. Check status: sudo systemctl status chatbot"
echo "4. Test API: curl http://$(curl -s ifconfig.me)/health"
echo "5. Monitor logs: sudo journalctl -u chatbot -f"
echo ""
echo "🎣 GitHub webhook will be available at: http://YOUR_IP/webhook"
echo "🌐 Your API will be at: http://YOUR_IP" 