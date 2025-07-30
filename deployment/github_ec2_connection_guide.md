# GitHub → EC2 Auto-Deploy Connection Guide

## 🎯 Overview

This guide documents the complete process for establishing a reliable GitHub → EC2 webhook connection for auto-deployment, including common pitfalls and troubleshooting steps learned from extensive testing.

## 🔍 Connection Architecture

```
GitHub Repository → Webhook → EC2 Webhook Server → Git Pull → Service Restart
```

## ✅ Prerequisites Checklist

### EC2 Instance Setup
- [ ] EC2 instance running with SSH access
- [ ] Security group allows inbound traffic on port 5005 (webhook)
- [ ] Security group allows inbound traffic on port 22 (SSH)
- [ ] Ubuntu user has sudo privileges

### GitHub Repository Setup
- [ ] Repository exists and is accessible
- [ ] Code is pushed to main branch
- [ ] Repository contains deployment scripts

### Local Development Setup
- [ ] SSH key configured for EC2 access
- [ ] Git configured with GitHub credentials
- [ ] Deployment scripts are executable (`chmod +x`)

## 🚀 Step-by-Step Connection Setup

### Step 1: Verify EC2 Connectivity

```bash
# Test SSH connection
ssh -i ~/.ssh/your-key.pem ubuntu@YOUR_EC2_IP

# Test basic connectivity
ping YOUR_EC2_IP

# Verify security group allows port 5005
curl -v http://YOUR_EC2_IP:5005/health
```

### Step 2: Deploy Webhook Server to EC2

```bash
# SSH into EC2
ssh -i ~/.ssh/your-key.pem ubuntu@YOUR_EC2_IP

# Clone your repository
sudo mkdir -p /opt/chatbot
sudo chown ubuntu:ubuntu /opt/chatbot
cd /opt/chatbot
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git .

# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set environment variables
export GITHUB_WEBHOOK_SECRET="your-secure-secret-here"

# Start webhook server
cd deployment
python webhook.py
```

### Step 3: Configure GitHub Webhook

1. Go to your GitHub repository
2. Navigate to **Settings → Webhooks → Add webhook**
3. Configure exactly as follows:
   - **Payload URL**: `http://YOUR_EC2_IP:5005/webhook`
   - **Content type**: `application/json`
   - **Secret**: Your `GITHUB_WEBHOOK_SECRET` value
   - **Which events**: Select "Just the push event"
   - **Active**: ✅ Checked

### Step 4: Test the Connection

```bash
# Make a test change
echo "Test deployment $(date)" >> test.txt
git add test.txt
git commit -m "Test auto-deploy trigger"
git push origin main
```

## 🔍 Verification Methods

### Method 1: Check Webhook Logs
```bash
# SSH into EC2
ssh -i ~/.ssh/your-key.pem ubuntu@YOUR_EC2_IP

# Check webhook server logs
sudo journalctl -f | grep webhook
# OR check process logs
ps aux | grep webhook
```

### Method 2: Check GitHub Webhook Deliveries
1. Go to **Repository Settings → Webhooks**
2. Click on your webhook
3. Check **Recent Deliveries** tab
4. Look for successful 200 responses

### Method 3: Verify Repository Updates
```bash
# SSH into EC2
cd /opt/chatbot
git log --oneline -3
# Should show your latest commit
```

## ❌ Common Issues and Solutions

### Issue 1: "Invalid signature" Error
**Symptoms**: Webhook returns `{"error":"Invalid signature"}`

**Root Cause**: Webhook secret mismatch between GitHub and EC2

**Solution**:
```bash
# Check EC2 webhook server secret
ps eww $(pgrep -f webhook.py) | grep GITHUB_WEBHOOK_SECRET

# Update GitHub webhook secret to match
# OR update EC2 environment variable to match GitHub
```

### Issue 2: Webhook Server Not Accessible
**Symptoms**: `curl: (7) Failed to connect` or timeout

**Root Cause**: Security group or firewall blocking port 5005

**Solution**:
```bash
# Check if webhook server is running
sudo netstat -tlnp | grep :5005
# OR
sudo ss -tlnp | grep :5005

# Check AWS Security Group:
# - Add inbound rule: Custom TCP, Port 5005, Source: 0.0.0.0/0
```

### Issue 3: HTTP 500 Error on Webhook
**Symptoms**: GitHub shows 500 error in webhook deliveries

**Root Cause**: Webhook server fails during git pull execution

**Common Causes**:
- Webhook server not running in git repository directory
- Git repository not initialized
- Permission issues

**Solution**:
```bash
# Ensure webhook server runs from git repository
cd /opt/chatbot
git status  # Should show git repository
git remote -v  # Should show correct repository URL

# Fix permissions if needed
sudo chown -R ubuntu:ubuntu /opt/chatbot
```

### Issue 4: Git Pull Fails
**Symptoms**: Webhook receives request but deployment fails

**Root Cause**: Git authentication or repository issues

**Solution**:
```bash
# Test git pull manually
cd /opt/chatbot
git pull origin main

# If authentication fails, set up SSH keys or tokens
# For HTTPS: git remote set-url origin https://TOKEN@github.com/USER/REPO.git
# For SSH: git remote set-url origin git@github.com:USER/REPO.git
```

## 🔧 Troubleshooting Commands

### Quick Diagnostic Script
```bash
#!/bin/bash
echo "=== GitHub-EC2 Connection Diagnostic ==="
echo "1. Webhook server status:"
ps aux | grep webhook | grep -v grep

echo "2. Port 5005 status:"
sudo ss -tlnp | grep :5005

echo "3. Git repository status:"
cd /opt/chatbot && git status --porcelain

echo "4. Recent webhook activity:"
sudo journalctl --since "10 minutes ago" | grep webhook

echo "5. Test webhook endpoint:"
curl -s http://localhost:5005/health
```

### Manual Webhook Test
```bash
# Test webhook endpoint manually
curl -X POST http://YOUR_EC2_IP:5005/webhook \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: push" \
  -H "X-Hub-Signature-256: sha256=test" \
  -d '{"ref":"refs/heads/main","repository":{"full_name":"USER/REPO"}}'
```

## 🎯 Best Practices

### Security
- Use strong, unique webhook secrets
- Regularly rotate webhook secrets
- Limit security group access to necessary IPs only
- Use HTTPS for webhook URLs when possible

### Reliability
- Monitor webhook server with systemd service
- Set up log rotation for webhook logs
- Implement webhook retry logic
- Use health checks to monitor webhook server

### Deployment
- Test webhook connection before production deployment
- Keep deployment scripts simple and robust
- Implement rollback mechanisms
- Monitor deployment success/failure

## 📊 Success Indicators

**✅ Connection Working When:**
- GitHub webhook deliveries show 200 responses
- EC2 webhook server logs show received POST requests
- Git repository updates after GitHub pushes
- Services restart automatically after deployment

**❌ Connection Broken When:**
- GitHub webhook deliveries show 4xx/5xx errors
- No webhook activity in EC2 logs after GitHub push
- Repository not updating despite successful webhook calls
- Services not restarting after deployment

## 🚀 Production Deployment Checklist

- [ ] EC2 security groups configured
- [ ] Webhook server running as systemd service
- [ ] GitHub webhook configured with correct URL and secret
- [ ] Git repository properly initialized on EC2
- [ ] Deployment scripts tested and working
- [ ] Rollback procedure documented and tested
- [ ] Monitoring and alerting configured
- [ ] Log rotation configured

---

**Note**: This guide is based on extensive testing and real-world troubleshooting. Keep it updated as new issues are discovered and resolved.
