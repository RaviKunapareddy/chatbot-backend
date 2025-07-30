# 🚀 Deployment Quick Reference
## Public-Safe Documentation for GitHub

**Note**: This file contains generic placeholders for public GitHub repository. For actual deployment details, see `PERSONAL_OPERATIONS_GUIDE.md` (local only).

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
# Check service status
sudo systemctl status chatbot

# Restart service
sudo systemctl restart chatbot

# View logs
sudo journalctl -u chatbot -n 20
```

---

## 🔧 Common Operations

### Deploy New Code
1. `git add . && git commit -m "Description"`
2. `git push origin master`
3. Auto-deploy triggers automatically
4. Verify: `curl -s http://YOUR_EC2_IP/health`

### Emergency Restart
```bash
# Connect to EC2
ssh -i ~/.ssh/your-key.pem ubuntu@YOUR_EC2_IP

# Restart service
sudo systemctl restart chatbot

# Verify
curl -s http://localhost:8000/health
```

---

## 📍 Important Locations

### On EC2
- Main app: `/opt/chatbot/main.py`
- Environment: `/opt/chatbot/.env`
- Service config: `/etc/systemd/system/chatbot.service`
- Webhook logs: `/opt/chatbot/deployment/webhook.log`

### URLs
- API Docs: `http://YOUR_EC2_IP/docs`
- Health Check: `http://YOUR_EC2_IP/health`
- Webhook: `http://YOUR_EC2_IP:5005/webhook`

---

## 🔐 Security Notes

- Never commit `.env` files
- Keep SSH keys secure (600 permissions)
- Use actual IPs/credentials in local documentation only
- Monitor free tier usage limits

---

**For complete operational details with actual IPs and credentials, see `PERSONAL_OPERATIONS_GUIDE.md` (local file only)**
