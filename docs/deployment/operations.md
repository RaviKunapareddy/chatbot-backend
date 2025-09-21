# 🚀 Deployment Quick Reference
## Public-Safe Documentation for GitHub

**Note**: This file contains generic placeholders for public GitHub repository. Replace YOUR_EC2_IP and key paths with actual values for your deployment.

---

## 📋 Quick Commands

### Health Check
```bash
# Replace YOUR_EC2_IP with your actual EC2 IP
curl -s http://YOUR_EC2_IP/health
```

### SSH Access
```bash
# Replace with your actual key path and EC2 IP
ssh -i ~/.ssh/your-key.pem ubuntu@YOUR_EC2_IP
```

### Service Management
```bash
# Check service status (both services)
sudo systemctl status chatbot chatbot-webhook

# Restart services
sudo systemctl restart chatbot chatbot-webhook

# Restart individual services
sudo systemctl restart chatbot
sudo systemctl restart chatbot-webhook

# View service logs
sudo journalctl -u chatbot -n 20
sudo journalctl -u chatbot-webhook -n 20

# View application logs
tail -f /opt/chatbot/logs/app_$(date +%Y-%m-%d).log

# View webhook logs
tail -f /opt/chatbot/logs/webhook/webhook.log
```

---

## 🔧 Common Operations

### Deploy New Code
1. `git add . && git commit -m "Description"`
2. `git push origin master`
3. Auto-deploy triggers automatically
4. Verify: `curl -s http://YOUR_EC2_IP/health`

### Vector Search Maintenance
```bash
# Test reindexing (dry run)
python vector_service/manual_reindex_products.py --dry-run

# Perform actual reindexing
python vector_service/manual_reindex_products.py --yes

# Clear and reindex (nuclear option)
python vector_service/manual_reindex_products.py --clear --yes
```

### System Status & Coordination
```bash
# Comprehensive system status
./deployment/service_manager.sh status

# Check indexing coordination
./deployment/service_manager.sh status | grep -A 10 "Coordination Status"
```

### Emergency Restart
```bash
# Connect to EC2
ssh -i ~/.ssh/your-key.pem ubuntu@YOUR_EC2_IP

# Restart both services
sudo systemctl restart chatbot chatbot-webhook

# Verify
curl -s http://localhost:8000/health
```

---

## 📍 Important Locations

### On EC2
- Main app: `/opt/chatbot/main.py`
- Environment: `/opt/chatbot/.env`
- Service config: `/etc/systemd/system/chatbot.service`
- Application logs: `/opt/chatbot/logs/app_YYYY-MM-DD.log`
- Webhook logs: `/opt/chatbot/logs/webhook/webhook.log`

### URLs
- API Docs: `http://YOUR_EC2_IP/docs`
- Health Check: `http://YOUR_EC2_IP/health`
- Webhook: `http://YOUR_EC2_IP:5005/webhook`

## 🧪 Smoke Tests

### Local (developer machine)
```bash
# Activate your Python environment (adjust name as needed)
conda activate chatbot-backend-dev
# OR if using venv:
# source venv/bin/activate

# Run unit/integration tests
pytest -q

# Run live health smoke test (requires env configured; skips unless enabled)
RUN_LIVE_TESTS=1 pytest -q test/test_live_health.py
```

Notes:
- Live test hits the FastAPI app and checks cloud deps (Redis, Pinecone). Ensure `.env` is present locally.
- Uses Pinecone v6 env vars only: PINECONE_API_KEY, PINECONE_PRODUCTS_INDEX, PINECONE_SUPPORT_INDEX.

### EC2 (remote)
```bash
# Simple health check via public IP (HTTP)
curl -fsSL http://YOUR_EC2_IP/health && echo "✅ OK" || echo "❌ FAIL"

# From within the instance against localhost
ssh -i ~/.ssh/your-key.pem ubuntu@YOUR_EC2_IP "curl -fsSL http://localhost:8000/health && echo OK || echo FAIL"

# Check application logs
ssh -i ~/.ssh/your-key.pem ubuntu@YOUR_EC2_IP "tail -n 20 /opt/chatbot/logs/app_$(date +%Y-%m-%d).log"
```

---

## 🚨 Quick Troubleshooting

### Service Won't Start
```bash
# Check service status details
sudo systemctl status chatbot -l
sudo journalctl -u chatbot -n 50

# Check for port conflicts
sudo netstat -tlnp | grep :8000
sudo netstat -tlnp | grep :5005

# Check disk space
df -h /opt/chatbot
```

### High Memory/CPU Usage
```bash
# Check resource usage
htop
ps aux | grep python

# Check application logs for errors
tail -f /opt/chatbot/logs/app_$(date +%Y-%m-%d).log | grep -i error
```

### Auto-Deploy Issues
```bash
# Check webhook service
sudo systemctl status chatbot-webhook
curl -s http://YOUR_EC2_IP:5005/health

# Manual deployment fallback
./deployment/manual_deploy.sh ~/.ssh/your-key.pem YOUR_EC2_IP
```

---

## 🔐 Security Notes

- Never commit `.env` files
- Keep SSH keys secure (600 permissions)
- Use actual IPs/credentials in local documentation only
- Monitor free tier usage limits

---

## 📝 **Document Maintenance**

**Last Updated**: 2025-09-20  
**Document Version**: 1.2  
**Status**: ✅ Production-ready operations guide  

**Recent Updates:**
- 2025-09-20: Added vector search maintenance commands and troubleshooting section
- 2025-09-20: Enhanced service management for dual services (chatbot + webhook)  
- 2025-09-20: Added cross-references and fixed webhook log paths

---

## 📚 **Related Documentation**

**Quick Navigation:**
- **📋 Deployment Guide**: `guide.md` - Complete deployment architecture and decision rationale
- **🔧 Troubleshooting**: `troubleshooting.md` - When something breaks, start with [Issue 1: HTTP 403](troubleshooting.md#issue-1-webhook-returns-http-403-forbidden)
- **🎓 Code Understanding**: `../development/codebase-guide.md` - Deep dive into system architecture and components

**Cross-References:**
- **Service Issues**: See troubleshooting guide [Issue 6: Virtual Environment Path Issues](#issue-6-virtual-environment-path-issues)
- **Git Problems**: See troubleshooting guide [Issue 3: Branch Mismatch](#issue-3-branch-mismatch-git-pull-fails)
- **Webhook Failures**: See troubleshooting guide [Issue 1-2: Authentication & Connectivity](#common-issues)
