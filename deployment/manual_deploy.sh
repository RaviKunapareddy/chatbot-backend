#!/bin/bash
# 🚀 Smart Deployment Upload Script
# Excludes unnecessary files and handles .env securely

set -e

# Check if required arguments provided
if [ $# -lt 2 ]; then
    echo "Usage: $0 <key-file.pem> <ec2-ip>"
    echo "Example: $0 my-key.pem 3.84.123.45"
    exit 1
fi

KEY_FILE=$1
EC2_IP=$2

echo "🚀 Starting smart deployment upload..."

# Verify .env exists locally
if [ ! -f ".env" ]; then
    echo "❌ .env file not found! Please create .env with your credentials"
    exit 1
fi

echo "✅ Found .env file"

# Create exclude list for rsync
EXCLUDE_OPTS=(
    --exclude='.git'
    --exclude='.env'
    --exclude='__pycache__'
    --exclude='*.pyc'
    --exclude='.DS_Store'
    --exclude='DEPLOYMENT_ACTION_PLAN.md'
    --exclude='DEPLOYMENT_PLAN_REVISED.md'
    --exclude='aws_cleanup_guide.md'
    --exclude='*.log'
    --exclude='logs/'
    --exclude='venv/'
    --exclude='.pytest_cache'
)

echo "📁 Uploading application files (excluding unnecessary files)..."
rsync -av "${EXCLUDE_OPTS[@]}" \
  -e "ssh -i $KEY_FILE -o StrictHostKeyChecking=no" \
  . ubuntu@$EC2_IP:/home/ubuntu/chatbot/

echo "🔐 Uploading .env securely..."
scp -i $KEY_FILE .env ubuntu@$EC2_IP:/home/ubuntu/chatbot/.env

echo "📂 Moving files to deployment location..."
ssh -i $KEY_FILE ubuntu@$EC2_IP << 'EOF'
sudo mv /home/ubuntu/chatbot /opt/
sudo chown -R ubuntu:ubuntu /opt/chatbot
sudo chmod 644 /opt/chatbot/.env
EOF

echo "✅ Upload completed successfully!"
echo ""
echo "Next steps:"
echo "1. SSH to server: ssh -i $KEY_FILE ubuntu@$EC2_IP"
echo "2. Run setup: cd /opt/chatbot/deployment && ./initial_setup.sh" 