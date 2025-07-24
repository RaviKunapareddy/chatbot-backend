#!/bin/bash
# GitHub Auto-Deploy Script for EC2 - Production Safe

set -e  # Exit immediately on error
LOG_FILE="/opt/chatbot/github_deploy.log"

{
    echo "🚀 [$(date)] Starting auto-deployment..."

    cd /opt/chatbot || {
        echo "❌ ERROR: /opt/chatbot does not exist!"
        exit 1
    }

    echo "🔄 Pulling latest code from GitHub..."
    git reset --hard HEAD
    git pull origin main

    echo "📦 Reinstalling dependencies (if any changed)..."
    source venv/bin/activate
    pip install -r requirements.txt

    echo "🔁 Restarting chatbot service..."
    sudo systemctl restart chatbot

    echo "✅ Deployment complete at $(date)"
} >> "$LOG_FILE" 2>&1
