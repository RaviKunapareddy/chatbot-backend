# 🚀 Deployment Guide for Chatbot Backend

This guide covers all deployment operations for the FastAPI chatbot backend on AWS EC2 with GitHub integration.

## 📁 Deployment Files Overview

| File | Purpose | When to Use |
|------|---------|-------------|
| `initial_setup.sh` | One-time server setup | Fresh EC2 instance setup |
| `service_manager.sh` | Daily operations | Start/stop/monitor services |
| `webhook.py` | GitHub auto-deploy | Automatic deployments |
| `manual_deploy.sh` | Emergency upload | Manual code upload only |

---

## 🆕 Initial Deployment (New Server)

### Prerequisites
- AWS EC2 instance (Ubuntu 22.04 LTS)
- Security group allowing ports 80, 22, 5005
- SSH key pair for EC2 access
- GitHub repository with webhook configured

### Step 1: Upload Code to Server
```bash
# From your local machine
cd /path/to/chatbot_backend_backup/deployment
./manual_deploy.sh your-key.pem YOUR_EC2_IP
```

### Step 2: Initial Server Setup
```bash
# SSH to your server
ssh -i your-key.pem ubuntu@YOUR_EC2_IP

# Run one-time setup
cd /opt/chatbot/deployment
chmod +x *.sh
./initial_setup.sh
```

### Step 3: Configure Environment
```bash
# Edit environment variables
nano /opt/chatbot/.env

# Required variables:
# AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
# PINECONE_API_KEY, PINECONE_INDEX_NAME
# REDIS_HOST, REDIS_PORT, REDIS_PASSWORD
# HUGGINGFACE_API_KEY
# GITHUB_WEBHOOK_SECRET
```

### Step 4: Start Services
```bash
cd /opt/chatbot/deployment
./service_manager.sh start
```

### Step 5: Verify Deployment
```bash
# Check service status
./service_manager.sh status

# Test API
curl http://YOUR_EC2_IP/health
```

---

## 🔄 Daily Operations

### Service Management
```bash
cd /opt/chatbot/deployment

# Check if everything is running
./service_manager.sh status

# Start services
./service_manager.sh start

# Stop services
./service_manager.sh stop

# Restart services (after config changes)
./service_manager.sh restart
```

### Monitoring & Debugging
```bash
# View live logs
./service_manager.sh logs

# Check specific service
sudo systemctl status chatbot
sudo systemctl status chatbot-webhook

# View detailed logs
sudo journalctl -u chatbot -f
sudo journalctl -u chatbot-webhook -f
```

### Updates & Maintenance
```bash
# Update from GitHub (manual)
./service_manager.sh update

# Manual deployment (install new dependencies)
./service_manager.sh deploy

# Clean old logs and cache files
./service_manager.sh cleanup
```

---

## 🎣 GitHub Webhook Auto-Deployment

### Setup
1. **GitHub Repository Settings:**
   - Go to Settings → Webhooks
   - Add webhook: `http://YOUR_EC2_IP:5005/webhook`
   - Content type: `application/json`
   - Secret: Same as `GITHUB_WEBHOOK_SECRET` in `.env`
   - Events: Just push events

2. **Verify Webhook Service:**
   ```bash
   sudo systemctl status chatbot-webhook
   curl http://YOUR_EC2_IP:5005/health
   ```

### How It Works
- Push to GitHub → Webhook triggers → Server pulls latest code → Services restart
- Webhook runs on port 5005 as systemd service
- Logs available: `sudo journalctl -u chatbot-webhook -f`

---

## 🔧 Production Features

### Health Monitoring
```bash
# Enhanced health check (tests Redis + Pinecone connectivity)
curl http://YOUR_EC2_IP/health | python3 -m json.tool

# Expected response:
{
  "status": "healthy",
  "services": {
    "redis": "connected",
    "pinecone": "connected"
  },
  "environment": "production"
}
```

### Security Features
- **Rate Limiting:** 10 requests/minute/IP on chat endpoints
- **Request Timeouts:** All external services have 5-10 second timeouts
- **Webhook Security:** GitHub signature verification

### Logging
- **Application Logs:** `/opt/chatbot/logs/chatbot_YYYY-MM-DD.log`
- **System Logs:** `sudo journalctl -u chatbot`
- **Auto-cleanup:** Logs older than 7 days are automatically removed

---

## 🚨 Troubleshooting

### Common Issues

#### Services Won't Start
```bash
# Check service status
./service_manager.sh status

# Check environment variables
cat /opt/chatbot/.env

# Check detailed logs
sudo journalctl -u chatbot -n 50
```

#### Can't Connect to API
```bash
# Check if nginx is running
sudo systemctl status nginx

# Check security group allows port 80
# Check EC2 instance public IP

# Test local connection
curl http://localhost:8000/health
```

#### Webhook Not Working
```bash
# Check webhook service
sudo systemctl status chatbot-webhook

# Check webhook logs
sudo journalctl -u chatbot-webhook -f

# Verify GitHub secret matches
grep GITHUB_WEBHOOK_SECRET /opt/chatbot/.env
```

#### App Crashes or Errors
```bash
# View live application logs
./service_manager.sh logs

# Check for dependency issues
cd /opt/chatbot
source venv/bin/activate
pip check

# Restart services
./service_manager.sh restart
```

### Debug Commands
```bash
# System resources
df -h                    # Disk usage
free -h                  # Memory usage
top                      # CPU usage

# Network
netstat -tlnp | grep :80    # Check port 80
netstat -tlnp | grep :5005  # Check webhook port

# Service logs
sudo journalctl -u chatbot --since "1 hour ago"
sudo journalctl -u chatbot-webhook --since "1 hour ago"
```

---

## 📋 Maintenance Schedule

### Daily
- Monitor health endpoint: `curl http://YOUR_EC2_IP/health`
- Check service status: `./service_manager.sh status`

### Weekly
- Clean old files: `./service_manager.sh cleanup`
- Review logs for errors
- Check disk usage: `df -h`

### Monthly
- Update system packages: `sudo apt update && sudo apt upgrade`
- Review and rotate any large log files
- Backup environment configuration

---

## 🔗 Quick Reference

### Essential Commands
```bash
# Service management
./service_manager.sh {start|stop|restart|status|logs|update|deploy|cleanup}

# Direct systemd commands
sudo systemctl {start|stop|restart|status} chatbot
sudo systemctl {start|stop|restart|status} chatbot-webhook

# Log monitoring
sudo journalctl -u chatbot -f
sudo journalctl -u chatbot-webhook -f
```

### Important Paths
- **Application:** `/opt/chatbot/`
- **Logs:** `/opt/chatbot/logs/`
- **Environment:** `/opt/chatbot/.env`
- **Virtual Environment:** `/opt/chatbot/venv/`
- **Deployment Scripts:** `/opt/chatbot/deployment/`

### Service Ports
- **Main API:** Port 80 (nginx → 8000)
- **Webhook:** Port 5005
- **Health Check:** `http://YOUR_EC2_IP/health`

---

## 📞 Emergency Procedures

### Complete Service Restart
```bash
cd /opt/chatbot/deployment
./service_manager.sh stop
sleep 5
./service_manager.sh start
./service_manager.sh status
```

### Rollback to Previous Version

```bash
# Use the integrated rollback command
./deployment/service_manager.sh rollback

# Follow prompts to select commit
# Services will be stopped, code rolled back, and services restarted
```

### Manual Code Update (if webhook fails)
```bash
cd /opt/chatbot
git pull origin main
./deployment/service_manager.sh restart
```

### Reset Environment (nuclear option)
```bash
# Stop services
./service_manager.sh stop

# Backup current .env
cp /opt/chatbot/.env /opt/chatbot/.env.backup

# Re-run setup (will preserve .env)
cd /opt/chatbot/deployment
./initial_setup.sh

# Restore .env if needed
cp /opt/chatbot/.env.backup /opt/chatbot/.env

# Start services
./service_manager.sh start
```

---

*This deployment guide covers all essential operations for maintaining your chatbot backend in production. For additional support, check the main README.md or application logs.*
