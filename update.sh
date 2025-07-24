#!/bin/bash

# Quick Update Script for Code Changes
# Use this instead of full redeployment for most changes

set -e

if [ -z "$1" ]; then
    echo "Usage: ./update.sh YOUR_EC2_IP"
    echo "Example: ./update.sh 3.15.123.456"
    exit 1
fi

EC2_IP=$1
KEY_FILE=${2:-"your-key.pem"}

echo "🔄 Updating AI Chatbot Backend on EC2: $EC2_IP"
echo "================================================"

# Sync code (excluding .env to preserve production settings)
echo "📤 Syncing code to EC2..."
rsync -avz --exclude='.env' --exclude='__pycache__' --exclude='*.pyc' \
    -e "ssh -i $KEY_FILE" \
    ./ ubuntu@$EC2_IP:/opt/chatbot/

# Restart service
echo "🔄 Restarting chatbot service..."
ssh -i $KEY_FILE ubuntu@$EC2_IP "sudo systemctl restart chatbot"

# Check status
echo "✅ Checking service status..."
ssh -i $KEY_FILE ubuntu@$EC2_IP "sudo systemctl status chatbot --no-pager -l"

echo ""
echo "🎉 Update completed!"
echo "🌐 Test your API: http://$EC2_IP/health" 