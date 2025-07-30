# 🚀 Comprehensive Deployment & Operations Guide
## Ravi's Chatbot Backend - Complete Reference Manual

**Repository**: `https://github.com/RaviKunapareddy/chatbot-backend`  
**EC2 Instance**: `18.234.53.50`  
**SSH Key**: `~/.ssh/chatbot-demo-key.pem`  
**Deployment Path**: `/opt/chatbot`

---

## 📋 TABLE OF CONTENTS

1. [GitHub Operations](#github-operations)
2. [EC2 & SSH Operations](#ec2--ssh-operations)
3. [Deployment Operations](#deployment-operations)
4. [Service Management](#service-management)
5. [Webhook Setup & Management](#webhook-setup--management)
6. [Monitoring & Troubleshooting](#monitoring--troubleshooting)
7. [Security & Maintenance](#security--maintenance)
8. [Emergency Procedures](#emergency-procedures)

---

## 🐙 GITHUB OPERATIONS

### **Repository Management**

```bash
# Clone repository locally
git clone git@github.com:RaviKunapareddy/chatbot-backend.git
cd chatbot-backend

# Check repository status
git status
git log --oneline -5

# View remote configuration
git remote -v
```

### **Making Changes & Commits**

```bash
# Stage changes
git add .
git add specific-file.py

# Commit changes
git commit -m "Description of changes"

# Push to GitHub
git push origin master

# Create and push tags
git tag -a v1.1.0 -m "Version 1.1.0 release"
git push origin v1.1.0
```

### **Branch Management**

```bash
# List branches
git branch -a

# Create new branch
git checkout -b feature-branch

# Switch branches
git checkout master
git checkout feature-branch

# Merge branches
git checkout master
git merge feature-branch
```

### **Repository Maintenance**

```bash
# Pull latest changes
git pull origin master

# Check for uncommitted changes
git diff
git diff --staged

# Undo changes
git checkout -- filename.py  # Undo file changes
git reset HEAD filename.py   # Unstage file
git reset --hard HEAD~1      # Undo last commit (dangerous!)
```

---

## 🖥️ EC2 & SSH OPERATIONS

### **SSH Connection**

```bash
# Connect to EC2 instance
ssh -i ~/.ssh/chatbot-demo-key.pem ubuntu@18.234.53.50

# Connect with verbose output (for debugging)
ssh -v -i ~/.ssh/chatbot-demo-key.pem ubuntu@18.234.53.50

# Copy files to EC2
scp -i ~/.ssh/chatbot-demo-key.pem local-file.txt ubuntu@18.234.53.50:/opt/chatbot/

# Copy files from EC2
scp -i ~/.ssh/chatbot-demo-key.pem ubuntu@18.234.53.50:/opt/chatbot/remote-file.txt ./
```

### **EC2 System Management**

```bash
# Check system resources
df -h                    # Disk usage
free -h                  # Memory usage
top                      # Running processes
htop                     # Enhanced process viewer
ps aux | grep python     # Find Python processes

# System updates
sudo apt update
sudo apt upgrade
sudo apt autoremove

# Check system logs
sudo journalctl -f       # Follow system logs
sudo journalctl -u chatbot  # Service-specific logs
```

### **File & Directory Operations**

```bash
# Navigate to project directory
cd /opt/chatbot

# List files with details
ls -la
ls -lah                  # Human-readable sizes

# Check file permissions
ls -la filename
stat filename

# Change permissions
chmod 600 .env           # Secure .env file
chmod +x script.sh       # Make script executable
sudo chown ubuntu:ubuntu filename  # Change ownership
```

---

## 🚀 DEPLOYMENT OPERATIONS

### **Initial Deployment**

```bash
# 1. SSH into EC2
ssh -i ~/.ssh/chatbot-demo-key.pem ubuntu@18.234.53.50

# 2. Set up deployment directory
sudo mkdir -p /opt/chatbot
sudo chown ubuntu:ubuntu /opt/chatbot
cd /opt/chatbot

# 3. Clone repository
git clone https://github.com/RaviKunapareddy/chatbot-backend.git .

# 4. Create .env file (NEVER commit this to GitHub)
nano .env
# Add all your API keys and secrets
chmod 600 .env

# 5. Run initial setup
./deployment/initial_setup.sh
```

### **Environment Setup**

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --no-cache-dir -r requirements.txt

# Verify installation
python3 -c "import fastapi, uvicorn, pinecone, boto3, redis; print('✅ All packages imported successfully')"
```

### **Configuration Management**

```bash
# View current configuration
cat config.py
cat .env.example

# Test configuration loading
cd /opt/chatbot
source venv/bin/activate
python3 -c "import config; print('✅ Configuration loaded successfully')"

# Check environment variables
env | grep -E "(PINECONE|REDIS|AWS|HUGGING|GITHUB)"
```

### **Update Deployment**

```bash
# Method 1: Manual update
cd /opt/chatbot
git pull origin master
source venv/bin/activate
pip install --no-cache-dir -r requirements.txt
./deployment/service_manager.sh restart

# Method 2: Using deployment script
./deployment/manual_deploy.sh
```

---

## ⚙️ SERVICE MANAGEMENT

### **Service Manager Commands**

```bash
# Navigate to project directory
cd /opt/chatbot

# Start all services
./deployment/service_manager.sh start

# Stop all services
./deployment/service_manager.sh stop

# Restart all services
./deployment/service_manager.sh restart

# Check service status
./deployment/service_manager.sh status

# View live logs
./deployment/service_manager.sh logs

# Update from GitHub
./deployment/service_manager.sh update

# Clean old logs and cache
./deployment/service_manager.sh cleanup

# Rollback to previous version
./deployment/service_manager.sh rollback
```

### **Manual Service Operations**

```bash
# Start FastAPI application manually
cd /opt/chatbot
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000

# Start with Gunicorn (production)
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# Start webhook server
cd /opt/chatbot/deployment
python3 webhook.py

# Check running processes
ps aux | grep -E "(uvicorn|gunicorn|webhook)"
```

### **Systemd Service Management**

```bash
# Check service status
sudo systemctl status chatbot
sudo systemctl status chatbot-webhook

# Start/stop services
sudo systemctl start chatbot
sudo systemctl stop chatbot
sudo systemctl restart chatbot

# Enable/disable auto-start
sudo systemctl enable chatbot
sudo systemctl disable chatbot

# View service logs
sudo journalctl -u chatbot -f
sudo journalctl -u chatbot-webhook -f
```

---

## 🔗 WEBHOOK SETUP & MANAGEMENT

### **GitHub Webhook Configuration**

1. **Go to GitHub Repository Settings**
   - Navigate to: `https://github.com/RaviKunapareddy/chatbot-backend/settings/hooks`

2. **Add Webhook**
   - **Payload URL**: `http://18.234.53.50:5005/webhook`
   - **Content type**: `application/json`
   - **Secret**: Your `GITHUB_WEBHOOK_SECRET` from .env file
   - **Which events**: Select "Just the push event"
   - **Active**: ✅ Checked

### **Webhook Server Management**

```bash
# Start webhook server
cd /opt/chatbot/deployment
export GITHUB_WEBHOOK_SECRET="your-secret-here"
python3 webhook.py

# Check webhook server status
ps aux | grep webhook
netstat -tlnp | grep :5005

# Test webhook endpoint
curl -X GET http://18.234.53.50:5005/health
curl -X GET http://localhost:5005/health  # From EC2
```

### **Webhook Troubleshooting**

```bash
# Check webhook logs
sudo journalctl -f | grep webhook

# Test webhook manually
curl -X POST http://18.234.53.50:5005/webhook \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: push" \
  -H "X-Hub-Signature-256: sha256=test" \
  -d '{"ref":"refs/heads/master","repository":{"full_name":"RaviKunapareddy/chatbot-backend"}}'

# Check GitHub webhook deliveries
# Go to: https://github.com/RaviKunapareddy/chatbot-backend/settings/hooks
# Click on your webhook → Recent Deliveries tab
```

### **Auto-Deploy Testing**

```bash
# Test auto-deploy with small change
echo "Test auto-deploy $(date)" >> test.txt
git add test.txt
git commit -m "Test auto-deploy trigger"
git push origin master

# Verify deployment on EC2
ssh -i ~/.ssh/chatbot-demo-key.pem ubuntu@18.234.53.50 "cd /opt/chatbot && git log --oneline -2"
```

---

## 📊 MONITORING & TROUBLESHOOTING

### **Health Checks**

```bash
# Check application health
curl http://18.234.53.50:8000/health
curl http://localhost:8000/health  # From EC2

# Check specific endpoints
curl http://18.234.53.50:8000/
curl http://18.234.53.50:8000/docs  # API documentation

# Test chat endpoint
curl -X POST http://18.234.53.50:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello", "session_id": "test"}'
```

### **Log Analysis**

```bash
# View application logs
cd /opt/chatbot
tail -f logs/chatbot.log
tail -f logs/chatbot-$(date +%Y-%m-%d).log

# View system logs
sudo journalctl -u chatbot -f
sudo journalctl -u chatbot-webhook -f

# Search logs for errors
grep -i error logs/chatbot.log
grep -i "500\|error\|exception" logs/chatbot.log
```

### **Performance Monitoring**

```bash
# Check resource usage
htop
free -h
df -h

# Monitor network connections
netstat -tlnp
ss -tlnp

# Check disk I/O
iostat -x 1

# Monitor specific processes
ps aux | grep -E "(python|uvicorn|gunicorn)"
```

### **External Service Testing**

```bash
# Test external service connections
cd /opt/chatbot
source venv/bin/activate

# Test Redis connection
python3 -c "import redis; r=redis.Redis(host='your-redis-host'); print(r.ping())"

# Test Pinecone connection
python3 -c "import pinecone; print('Pinecone client imported successfully')"

# Test AWS S3 connection
python3 -c "import boto3; s3=boto3.client('s3'); print('S3 client created successfully')"

# Test Google Gemini connection
python3 -c "import google.generativeai as genai; print('Gemini client imported successfully')"
```

---

## 🔒 SECURITY & MAINTENANCE

### **Security Best Practices**

```bash
# Check .env file permissions (should be 600)
ls -la /opt/chatbot/.env

# Secure .env file
chmod 600 /opt/chatbot/.env
chown ubuntu:ubuntu /opt/chatbot/.env

# Check for exposed secrets
grep -r "sk-\|pk-\|secret" /opt/chatbot/ --exclude-dir=.git --exclude="*.env*"

# Update system packages
sudo apt update && sudo apt upgrade

# Check for security updates
sudo unattended-upgrades --dry-run
```

### **Backup Operations**

```bash
# Backup .env file (store securely)
cp /opt/chatbot/.env ~/backup/.env.$(date +%Y%m%d)

# Backup logs
tar -czf ~/backup/logs-$(date +%Y%m%d).tar.gz /opt/chatbot/logs/

# Create full backup (excluding venv)
tar --exclude='venv' --exclude='.git' -czf ~/backup/chatbot-$(date +%Y%m%d).tar.gz /opt/chatbot/
```

### **Regular Maintenance**

```bash
# Clean old logs (automated in service_manager.sh cleanup)
find /opt/chatbot/logs -name "*.log" -mtime +7 -delete

# Clean Python cache
find /opt/chatbot -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find /opt/chatbot -name "*.pyc" -delete 2>/dev/null || true

# Clean pip cache
pip cache purge

# Update dependencies (be careful in production)
cd /opt/chatbot
source venv/bin/activate
pip list --outdated
# pip install --upgrade package-name
```

---

## 🚨 EMERGENCY PROCEDURES

### **Service Recovery**

```bash
# If services are down
ssh -i ~/.ssh/chatbot-demo-key.pem ubuntu@18.234.53.50
cd /opt/chatbot
./deployment/service_manager.sh status
./deployment/service_manager.sh restart

# If restart fails, check logs
./deployment/service_manager.sh logs
sudo journalctl -u chatbot -n 50
```

### **Rollback Procedures**

```bash
# Quick rollback using service manager
cd /opt/chatbot
./deployment/service_manager.sh rollback

# Manual rollback to specific commit
git log --oneline -10  # Find commit hash
git reset --hard COMMIT_HASH
./deployment/service_manager.sh restart
```

### **Disk Space Emergency**

```bash
# Check disk usage
df -h

# Clean up space quickly
cd /opt/chatbot
./deployment/service_manager.sh cleanup

# Remove old logs manually
sudo find /var/log -name "*.log" -mtime +7 -delete
sudo apt autoremove
sudo apt autoclean

# Clear pip cache
pip cache purge
```

### **Connection Issues**

```bash
# If SSH connection fails
ssh -v -i ~/.ssh/chatbot-demo-key.pem ubuntu@18.234.53.50

# Check EC2 instance status in AWS Console
# Verify security group allows SSH (port 22) and HTTP (port 8000, 5005)

# If webhook not working
curl -v http://18.234.53.50:5005/health
# Check GitHub webhook delivery logs
# Verify GITHUB_WEBHOOK_SECRET matches
```

---

## 📞 QUICK REFERENCE COMMANDS

### **Daily Operations**
```bash
# Check everything is running
ssh -i ~/.ssh/chatbot-demo-key.pem ubuntu@18.234.53.50 "cd /opt/chatbot && ./deployment/service_manager.sh status"

# Deploy latest changes
ssh -i ~/.ssh/chatbot-demo-key.pem ubuntu@18.234.53.50 "cd /opt/chatbot && ./deployment/service_manager.sh update"

# View recent logs
ssh -i ~/.ssh/chatbot-demo-key.pem ubuntu@18.234.53.50 "cd /opt/chatbot && tail -20 logs/chatbot.log"
```

### **Emergency Commands**
```bash
# Restart everything
ssh -i ~/.ssh/chatbot-demo-key.pem ubuntu@18.234.53.50 "cd /opt/chatbot && ./deployment/service_manager.sh restart"

# Check disk space
ssh -i ~/.ssh/chatbot-demo-key.pem ubuntu@18.234.53.50 "df -h"

# Quick cleanup
ssh -i ~/.ssh/chatbot-demo-key.pem ubuntu@18.234.53.50 "cd /opt/chatbot && ./deployment/service_manager.sh cleanup"
```

---

## 🔧 CUSTOMIZATION NOTES

**Your Specific Configuration:**
- **Repository**: `RaviKunapareddy/chatbot-backend`
- **EC2 IP**: `18.234.53.50`
- **SSH Key**: `chatbot-demo-key.pem`
- **Main Branch**: `master`
- **Python Version**: `3.10.12`
- **Architecture**: Cloud-first (Pinecone, HuggingFace API, AWS S3, Redis Cloud)

**Important Environment Variables:**
- `GITHUB_WEBHOOK_SECRET`: For auto-deployment
- `PINECONE_API_KEY`: Vector database access
- `HUGGINGFACE_API_KEY`: Embedding generation
- `REDIS_URL`: Session management
- `AWS_ACCESS_KEY_ID` & `AWS_SECRET_ACCESS_KEY`: S3 access
- `GOOGLE_API_KEY`: Gemini LLM access

---

**📚 This guide covers all operations you'll need for managing your chatbot backend deployment. Keep it handy for reference!**
