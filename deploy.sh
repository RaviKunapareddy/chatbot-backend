#!/bin/bash

# AI Chatbot Backend - EC2 Deployment Script
# For Ubuntu 22.04 LTS on t2.micro (Free Tier)

set -e

echo "🚀 Starting AI Chatbot Backend Deployment on EC2"
echo "================================================="

# Update system
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Python 3.11 and pip
echo "🐍 Installing Python 3.11..."
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip

# Install system dependencies
echo "🔧 Installing system dependencies..."
sudo apt install -y build-essential curl git nginx supervisor

# Create application directory
echo "📁 Setting up application directory..."
sudo mkdir -p /opt/chatbot
sudo chown $USER:$USER /opt/chatbot
cd /opt/chatbot

# Clone or copy application files
echo "📥 Setting up application files..."
# Note: You'll copy your files here or clone from git

# Create Python virtual environment
echo "🔨 Creating Python virtual environment..."
python3.11 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "📚 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create environment file
echo "🔐 Setting up environment variables..."
if [ ! -f .env ]; then
    echo "Creating .env file template..."
    cat > .env << 'EOF'
# Project Settings
PROJECT_NAME=chatbot-api
PROJECT_ID=ec2-production
ENVIRONMENT=production

# Redis Cloud (Required)
REDIS_HOST=your-redis-host
REDIS_PORT=6379
REDIS_PASSWORD=your-redis-password

# Elasticsearch Cloud (Required)
ELASTICSEARCH_HOST=your-elasticsearch-host
ELASTICSEARCH_PORT=443
ELASTICSEARCH_API_KEY=your-elasticsearch-api-key

# AWS Services (Required)
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET_NAME=chatbot-products-data

# LLM Services (Required)
GOOGLE_API_KEY=your-google-api-key
PINECONE_API_KEY=your-pinecone-api-key
HF_API_KEY=your-huggingface-api-key

# Optional LLM Settings
AWS_BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
GEMINI_MODEL=gemini-1.5-flash
EOF
    echo "⚠️  Please edit /opt/chatbot/.env with your actual credentials"
fi

# Create systemd service
echo "⚙️  Creating systemd service..."
sudo tee /etc/systemd/system/chatbot.service > /dev/null << EOF
[Unit]
Description=AI Chatbot Backend API
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/chatbot
Environment=PATH=/opt/chatbot/venv/bin
ExecStart=/opt/chatbot/venv/bin/gunicorn main:app -w 2 -k uvicorn.workers.UvicornWorker -b 127.0.0.1:8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Configure Nginx
echo "🌐 Configuring Nginx reverse proxy..."
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
        
        # CORS headers
        add_header 'Access-Control-Allow-Origin' '*' always;
        add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS' always;
        add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range' always;
        
        # Handle preflight requests
        if ($request_method = 'OPTIONS') {
            add_header 'Access-Control-Allow-Origin' '*';
            add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS';
            add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range';
            add_header 'Access-Control-Max-Age' 1728000;
            add_header 'Content-Type' 'text/plain; charset=utf-8';
            add_header 'Content-Length' 0;
            return 204;
        }
    }

    # Health check endpoint
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        access_log off;
    }
}
EOF

# Enable Nginx site
sudo ln -sf /etc/nginx/sites-available/chatbot /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test Nginx configuration
sudo nginx -t

# Enable and start services
echo "🔄 Starting services..."
sudo systemctl daemon-reload
sudo systemctl enable chatbot
sudo systemctl enable nginx
sudo systemctl restart nginx

echo ""
echo "✅ Deployment completed!"
echo "================================================="
echo "📝 Next Steps:"
echo "1. Edit /opt/chatbot/.env with your cloud service credentials"
echo "2. Start the service: sudo systemctl start chatbot"
echo "3. Check status: sudo systemctl status chatbot"
echo "4. View logs: sudo journalctl -u chatbot -f"
echo ""
echo "🌐 Your API will be available at:"
echo "   http://YOUR_EC2_PUBLIC_IP/health"
echo "   http://YOUR_EC2_PUBLIC_IP/docs"
echo "=================================================" 