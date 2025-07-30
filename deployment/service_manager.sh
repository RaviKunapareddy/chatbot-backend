#!/bin/bash

# Simple Chatbot Management Script
# Replaces 524 lines of over-engineered deploy_manager.sh with ~50 lines
# Provides essential operations for AWS deployment

rollback() {
    echo "🔄 CHATBOT ROLLBACK UTILITY"
    echo "============================================================"
    
    # Check if we're in the right directory
    if [ ! -f "main.py" ]; then
        echo "❌ Error: Please run this from the chatbot root directory"
        exit 1
    fi
    
    # Show recent commits
    echo "📋 Recent commits (last 10):"
    echo ""
    git log --oneline -10 --decorate
    
    echo ""
    echo "============================================================"
    echo "🎯 Enter the commit hash you want to rollback to:"
    echo "   (or 'cancel' to abort)"
    read -p "Commit hash: " commit_hash
    
    # Handle cancellation
    if [ "$commit_hash" = "cancel" ] || [ -z "$commit_hash" ]; then
        echo "❌ Rollback cancelled"
        exit 0
    fi
    
    # Validate commit hash exists
    if ! git rev-parse --verify "$commit_hash" >/dev/null 2>&1; then
        echo "❌ Error: Invalid commit hash '$commit_hash'"
        exit 1
    fi
    
    # Show commit details
    echo ""
    echo "📋 Rollback target:"
    git show --no-patch --format="%h - %s (%cr) <%an>" "$commit_hash"
    
    echo ""
    echo "⚠️  WARNING: This will reset your working directory to the selected commit."
    echo "   Any uncommitted changes will be lost!"
    read -p "Are you sure you want to continue? (yes/no): " confirm
    
    if [ "$confirm" != "yes" ]; then
        echo "❌ Rollback cancelled"
        exit 0
    fi
    
    echo ""
    echo "🔄 Rolling back to $commit_hash..."
    
    # Stop services before rollback
    echo "🛑 Stopping services..."
    sudo systemctl stop chatbot chatbot-webhook 2>/dev/null || true
    
    # Perform rollback
    git reset --hard "$commit_hash"
    
    if [ $? -eq 0 ]; then
        echo "✅ Successfully rolled back to $commit_hash"
        echo ""
        echo "🚀 Restarting services..."
        sudo systemctl start chatbot chatbot-webhook
        echo ""
        echo "✅ Rollback completed successfully!"
        echo "📋 Current commit:"
        git log --oneline -1
    else
        echo "❌ Rollback failed"
        exit 1
    fi
}

case "$1" in
    start)
        echo "🚀 Starting chatbot services..."
        sudo systemctl start chatbot chatbot-webhook
        echo "✅ Services started"
        ;;
    
    stop)
        echo "⏹️ Stopping chatbot services..."
        sudo systemctl stop chatbot chatbot-webhook
        echo "✅ Services stopped"
        ;;
    
    restart)
        echo "🔄 Restarting chatbot services..."
        sudo systemctl restart chatbot chatbot-webhook
        echo "✅ Services restarted"
        ;;
    
    status)
        echo "📊 Service Status:"
        echo ""
        sudo systemctl status chatbot --no-pager -l
        echo ""
        echo "🔍 Health Check:"
        curl -s http://localhost:8000/health | python3 -m json.tool 2>/dev/null || echo "❌ Health check failed"
        echo ""
        sudo systemctl status chatbot-webhook --no-pager -l
        echo ""
        echo "🌐 Health Check:"
        curl -s http://localhost:8000/health | python3 -m json.tool 2>/dev/null || echo "Main API: Not responding"
        curl -s http://localhost:5005/health | python3 -m json.tool 2>/dev/null || echo "Webhook: Not responding"
        ;;
    
    logs)
        echo "📋 Recent logs (use Ctrl+C to exit):"
        sudo journalctl -u chatbot -u chatbot-webhook -f
        ;;
    
    update)
        echo "🔄 Updating from GitHub..."
        cd /opt/chatbot
        git pull origin main
        source venv/bin/activate
        pip install -r requirements.txt
        sudo systemctl restart chatbot
        echo "✅ Update completed"
        ;;
    
    deploy)
        echo "🚀 Manual deployment..."
        cd /opt/chatbot
        source venv/bin/activate
        pip install -r requirements.txt
        sudo systemctl restart chatbot chatbot-webhook
        echo "✅ Deployment completed"
        ;;
    
    cleanup)
        echo "🧹 Starting chatbot cleanup..."
        
        # Clean old log files (older than 7 days)
        echo "📋 Cleaning old log files..."
        find /opt/chatbot/logs -name "*.log" -mtime +7 -delete 2>/dev/null || true
        find /opt/chatbot/logs -name "*.log.gz" -mtime +14 -delete 2>/dev/null || true
        
        # Clean Python cache
        echo "🐍 Cleaning Python cache..."
        find /opt/chatbot -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
        find /opt/chatbot -name "*.pyc" -delete 2>/dev/null || true
        
        # Clean old pip cache (if any)
        echo "📦 Cleaning pip cache..."
        /opt/chatbot/venv/bin/pip cache purge 2>/dev/null || true
        
        # Clean any temp files in /tmp related to our app
        echo "🗑️ Cleaning temp files..."
        sudo find /tmp -name "*chatbot*" -mtime +1 -delete 2>/dev/null || true
        
        # Display current disk usage
        echo "💾 Current disk usage:"
        df -h /opt/chatbot | grep -v Filesystem
        
        echo ""
        echo "✅ Cleanup completed!"
        echo ""
        echo "Summary:"
        echo "- Removed log files older than 7 days"
        echo "- Removed compressed logs older than 14 days"
        echo "- Cleaned Python cache files"
        echo "- Cleaned pip cache"
        echo "- Cleaned temp files"
        ;;
    
    rollback)
        rollback
        ;;
    
    *)
        echo "🤖 Chatbot Management Script"
        echo ""
        echo "Usage: $0 {start|stop|restart|status|logs|update|deploy|cleanup|rollback}"
        echo ""
        echo "Commands:"
        echo "  start    - Start chatbot services"
        echo "  stop     - Stop chatbot services"  
        echo "  restart  - Restart chatbot services"
        echo "  status   - Show service status and health"
        echo "  logs     - Show live service logs"
        echo "  update   - Pull latest code from GitHub and restart"
        echo "  deploy   - Manual deployment (install deps + restart)"
        echo "  cleanup  - Clean old logs, Python cache, and temporary files"
        echo "  rollback - Rollback to previous commit"
        echo ""
        echo "Examples:"
        echo "  $0 status    # Check if everything is running"
        echo "  $0 restart   # Restart after making changes"
        echo "  $0 logs      # Monitor live logs"
        echo "  $0 update    # Update from GitHub"
        echo "  $0 cleanup   # Clean old logs and temp files"
        exit 1
        ;;
esac 