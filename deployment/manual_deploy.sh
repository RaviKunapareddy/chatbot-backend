#!/bin/bash
# 🚀 Smart Deployment Upload Script
# Excludes unnecessary files and handles .env securely

set -euo pipefail

# Check if required arguments provided
if [ $# -lt 2 ]; then
    echo "Usage: $0 <key-file.pem> <ec2-ip>"
    echo "Example: $0 my-key.pem 3.84.123.45"
    exit 1
fi

KEY_FILE=$1
EC2_IP=$2

# Validate SSH key file exists and has correct permissions
if [ ! -f "$KEY_FILE" ]; then
    echo "❌ SSH key file '$KEY_FILE' not found"
    exit 1
fi

# Check and fix SSH key permissions if needed
if [ "$(stat -f %A "$KEY_FILE" 2>/dev/null || stat -c %a "$KEY_FILE" 2>/dev/null)" != "600" ]; then
    echo "⚠️  SSH key permissions should be 600. Fixing..."
    chmod 600 "$KEY_FILE"
    echo "✅ SSH key permissions fixed"
fi

echo "🚀 Starting smart deployment upload..."

# Verify .env exists locally
if [ ! -f ".env" ]; then
    echo "❌ .env file not found! Please create .env with your credentials"
    exit 1
fi

echo "✅ Found .env file"

# Test server connectivity before starting upload
echo "🔍 Testing server connectivity..."
if ! ssh -i "$KEY_FILE" -o ConnectTimeout=10 -o BatchMode=yes ubuntu@"$EC2_IP" "echo 'Connection test successful'" >/dev/null 2>&1; then
    echo "❌ Cannot connect to server $EC2_IP"
    echo "   Check: 1) Server is running 2) Security groups allow SSH 3) Key file is correct"
    exit 1
fi
echo "✅ Server connectivity confirmed"

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
  -e "ssh -i $KEY_FILE -o StrictHostKeyChecking=accept-new" \
  . ubuntu@$EC2_IP:/home/ubuntu/chatbot/

echo "🔐 Uploading .env securely..."
scp -i $KEY_FILE .env ubuntu@$EC2_IP:/home/ubuntu/chatbot/.env

echo "📂 Moving files to deployment location..."
ssh -i $KEY_FILE ubuntu@$EC2_IP << 'EOF'
# Create backup if existing installation exists
if [ -d "/opt/chatbot" ]; then
    BACKUP_NAME="chatbot.backup.$(date +%Y%m%d-%H%M%S)"
    echo "💾 Creating backup: /opt/$BACKUP_NAME"
    sudo mv /opt/chatbot /opt/$BACKUP_NAME
fi

sudo mv /home/ubuntu/chatbot /opt/
sudo chown -R ubuntu:ubuntu /opt/chatbot
sudo chmod 644 /opt/chatbot/.env
EOF

echo "🔄 Restarting services with new code..."
ssh -i $KEY_FILE ubuntu@$EC2_IP << 'EOF'
if [ -f "/opt/chatbot/deployment/service_manager.sh" ]; then
    cd /opt/chatbot/deployment
    ./service_manager.sh restart
else
    echo "⚠️  service_manager.sh not found. Manual service restart may be needed."
fi
EOF

echo "✅ Upload completed successfully!"
echo ""
echo "Next steps:"
echo "1. SSH to server: ssh -i $KEY_FILE ubuntu@$EC2_IP"
echo "2. If first deployment: cd /opt/chatbot/deployment && ./initial_setup.sh"
echo "3. Check services: cd /opt/chatbot/deployment && ./service_manager.sh status" 