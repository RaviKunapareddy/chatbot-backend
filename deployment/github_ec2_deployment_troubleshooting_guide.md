# GitHub → EC2 Deployment Troubleshooting Guide

## 🎯 Overview

This comprehensive troubleshooting guide documents the complete process for establishing a reliable GitHub → EC2 webhook connection for auto-deployment. Based on extensive real-world testing and deployment verification, this guide includes all actual issues encountered and their proven solutions.

**✅ VERIFIED DEPLOYMENT STATUS (2025-07-30):**
- **EC2 Instance**: 18.234.53.50 - ✅ Active and running
- **Chatbot Service**: ✅ Active (running) for 8+ hours
- **Health Endpoint**: ✅ http://18.234.53.50:8000/health - Healthy
- **Webhook Service**: ✅ http://18.234.53.50:5005/health - Healthy
- **Auto-Deploy**: ✅ Git logs synchronized (commit e49dd40)
- **Redis Cloud**: ✅ Connected
- **Pinecone Cloud**: ✅ Connected

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
ssh -i ~/.ssh/chatbot-demo-key.pem ubuntu@18.234.53.50

# Test basic connectivity
ping 18.234.53.50

# Verify security group allows port 5005
curl -v http://18.234.53.50:5005/health
```

### Step 2: Deploy Webhook Server to EC2

```bash
# SSH into EC2
ssh -i ~/.ssh/chatbot-demo-key.pem ubuntu@18.234.53.50

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
   - **Payload URL**: `http://18.234.53.50:5005/webhook`
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
ssh -i ~/.ssh/chatbot-demo-key.pem ubuntu@18.234.53.50

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

## 🚨 Common Issues and Solutions (Real-World Experience)

### Issue 1: Webhook Returns HTTP 403 Forbidden
**Symptoms:**
- GitHub webhook deliveries show failed status
- EC2 webhook logs show: `140.82.115.37 - - [date] "POST /webhook HTTP/1.1" 403 -`
- Repository not updating despite webhook triggers
- Authentication failure from GitHub IPs

**Root Cause:**
- Webhook secret mismatch between GitHub webhook configuration and EC2 environment
- Example: GitHub uses `chatbot-webhook-secret-2025-secure` but EC2 .env has `chatbot-webhook-secret-2025-stranger`

**Solution:**
```bash
# 1. Check current webhook secret on EC2
grep GITHUB_WEBHOOK_SECRET /opt/chatbot/.env
# Output: GITHUB_WEBHOOK_SECRET=chatbot-webhook-secret-2025-stranger

# 2. Update GitHub webhook to match EC2 secret:
# Go to GitHub → Repository → Settings → Webhooks → Edit webhook
# Update Secret field to match .env value exactly

# 3. Verify webhook server uses correct secret
ps eww $(pgrep -f webhook.py) | grep GITHUB_WEBHOOK_SECRET
```

**Verification:**
- Webhook logs should show HTTP 200 instead of 403
- GitHub webhook deliveries should show green checkmarks

### Issue 2: Port 5005 Not Accessible Externally
**Symptoms:**
- External webhook test fails: `curl http://EC2_IP:5005/health` times out
- GitHub webhook shows connection timeout errors
- Local test works: `curl http://localhost:5005/health` returns healthy status

**Root Cause:**
- AWS Security Group blocking inbound traffic on port 5005
- Webhook server listening but not accessible from internet

**Solution:**
```bash
# Add inbound rule to EC2 security group:
# 1. AWS Console → EC2 → Security Groups
# 2. Find security group for your EC2 instance
# 3. Edit inbound rules → Add rule:
#    Type: Custom TCP
#    Port: 5005
#    Source: 0.0.0.0/0 (or GitHub IP ranges for security)
#    Description: GitHub webhook
```

**Verification:**
```bash
# Test external access after security group update
curl -s http://18.234.53.50:5005/health
# Should return: {"service":"webhook","status":"healthy"}
```

### Issue 3: Branch Mismatch - Git Pull Fails
**Symptoms:**
- Webhook authenticates successfully (HTTP 200)
- Repository doesn't update with latest commits
- Git pull errors: `fatal: couldn't find remote ref main`
- Files remain unchanged after GitHub push

**Root Cause:**
- Webhook deployment script uses `git pull origin main`
- Repository actually uses `master` as default branch
- Branch name mismatch prevents successful pull

**Solution:**
```bash
# 1. Check actual repository branch
cd /opt/chatbot
git branch -a
# Shows: * master, remotes/origin/master

# 2. Fix webhook deployment script
cd /opt/chatbot/deployment
sed -i 's/git pull origin main/git pull origin master/g' webhook.py

# 3. Verify the fix
grep -A 3 'git pull origin' webhook.py
# Should show: git pull origin master

# 4. Restart webhook server
pkill -f webhook.py
export GITHUB_WEBHOOK_SECRET='your-secret-from-env'
nohup python3 webhook.py > webhook.log 2>&1 &
```

### Issue 4: Uncommitted Changes Block Git Pull
**Symptoms:**
- Webhook authentication works (HTTP 200)
- Git pull fails silently
- Repository shows modified files: `git status` shows changes
- Deployment appears successful but files don't update

**Root Cause:**
- Local modifications (e.g., webhook.py edits) prevent git pull
- Git refuses to pull when working directory has uncommitted changes
- Common after making deployment script fixes

**Solution:**
```bash
# Enhanced webhook deployment with git stash handling:
# Update webhook.py deployment command to:
cd /opt/chatbot && 
echo "🧹 Stashing uncommitted changes..." &&
git stash push -m "Auto-stash before deployment $(date)" 2>/dev/null || echo "No changes to stash" &&
echo "📥 Pulling latest changes..." &&
git pull origin master && 
echo "📦 Updating dependencies..." &&
source venv/bin/activate && 
pip install -r requirements.txt && 
echo "🔄 Restarting service..." &&
sudo systemctl restart chatbot
```

### Issue 5: SSL Verification Errors
**Symptoms:**
- GitHub webhook configuration shows SSL warnings
- Webhook deliveries fail with SSL/certificate errors

**Root Cause:**
- Webhook server running on HTTP (not HTTPS)
- GitHub SSL verification enabled for non-SSL endpoint

**Solution:**
```bash
# In GitHub webhook configuration:
# SSL verification: Select "Disable (not recommended)"
# This is acceptable for development/testing environments
```

### Issue 6: Virtual Environment Path Issues
**Symptoms:**
- Service fails after deployment: `ModuleNotFoundError: No module named 'fastapi'`
- Dependencies appear installed but service can't find them
- Systemd service shows exit code 1

**Root Cause:**
- Virtual environment not properly configured in systemd service
- Dependencies installed globally vs in virtual environment

**Solution:**
```bash
# 1. Verify virtual environment and packages
cd /opt/chatbot
source venv/bin/activate
pip list | grep fastapi

# 2. Check systemd service configuration
sudo systemctl cat chatbot
# Verify: ExecStart=/opt/chatbot/venv/bin/python main.py

# 3. Recreate virtual environment if needed
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart chatbot
```

### Issue 7: Missing Numpy Dependency (CRITICAL FIX)
**Symptoms:**
- Service starts but crashes immediately
- Health endpoint returns 500 errors or timeouts
- Service logs show: `ModuleNotFoundError: No module named 'numpy'`
- Auto-deploy completes successfully but chatbot service fails

**Root Cause:**
- Numpy dependency missing from requirements.txt
- Required by underlying ML/AI libraries but not explicitly declared
- Service startup fails when trying to import dependent packages

**Solution (VERIFIED WORKING):**
```bash
# 1. Add numpy to requirements.txt
echo "numpy==1.24.3" >> /opt/chatbot/requirements.txt

# 2. Install the missing dependency
cd /opt/chatbot
source venv/bin/activate
pip install numpy==1.24.3

# 3. Restart the service
sudo systemctl restart chatbot

# 4. Verify the fix
sudo systemctl status chatbot
curl http://localhost:8000/health
```

**✅ VERIFIED SOLUTION (2025-07-30):**
- This fix resolved the final service startup issue
- Numpy 1.24.3 added to requirements.txt line 16
- Service now runs successfully for 8+ hours
- Health endpoint returns proper JSON response
- **This was the critical missing piece for production deployment**

## 🔧 Complete Troubleshooting Workflow

When GitHub → EC2 auto-deploy fails, follow this systematic approach:

### Step 1: Test Webhook Connectivity
```bash
# External access test
curl -s http://18.234.53.50:5005/health
# Expected: {"service":"webhook","status":"healthy"}
# If timeout: Check security group (Issue 2)
```

### Step 2: Verify Webhook Authentication
```bash
# Check recent webhook logs
ssh -i ~/.ssh/chatbot-demo-key.pem ubuntu@18.234.53.50
cd /opt/chatbot/deployment
tail -10 webhook.log
# Look for: HTTP 200 (success) vs HTTP 403 (Issue 1)
```

### Step 3: Check Repository Synchronization
```bash
# Compare local vs EC2 repository state
# Local:
git log --oneline -3

# EC2:
ssh -i ~/.ssh/chatbot-demo-key.pem ubuntu@18.234.53.50
cd /opt/chatbot
git log --oneline -3
# Should match if sync working (Issues 3,4 if not)
```

### Step 4: Test Manual Deployment
```bash
# Manual deployment test on EC2
cd /opt/chatbot
git stash push -m "Test stash"
git pull origin master  # Use your actual branch
# Should succeed without errors
```

### Step 5: Verify Service Status
```bash
# Check service after deployment
sudo systemctl status chatbot
# Look for: Active vs Failed (Issue 6 if failed)
```

## 📋 Success Indicators (VERIFIED 2025-07-30)

When everything works correctly, you should see:

1. **External webhook access**: `curl http://18.234.53.50:5005/health` returns `{"service":"webhook","status":"healthy"}` ✅
2. **Authentication success**: Webhook logs show HTTP 200 from GitHub IPs ✅
3. **Repository sync**: Latest commits appear on EC2 after GitHub push (commit e49dd40 verified) ✅
4. **Service running**: `systemctl status chatbot` shows Active (running) for 8+ hours ✅
5. **Application accessible**: `curl http://18.234.53.50:8000/health` returns comprehensive health JSON ✅
6. **Cloud services connected**: Redis Cloud and Pinecone Cloud both showing "connected" status ✅

## 🏆 Real-World Deployment Experience

### Timeline of Issues Encountered and Resolved

**Phase 1: Initial Setup Issues**
- ❌ Security group port 5005 not open → ✅ Fixed via AWS console
- ❌ Webhook authentication failures → ✅ Fixed with proper GitHub secret
- ❌ Git branch mismatch (main vs master) → ✅ Updated webhook.py

**Phase 2: Service Deployment Issues**
- ❌ Virtual environment path problems → ✅ Fixed systemd service configuration
- ❌ Uncommitted changes blocking git pull → ✅ Added git stash to deployment
- ❌ SSL verification warnings → ✅ Disabled for development environment

**Phase 3: Critical Service Startup Issue**
- ❌ **CRITICAL**: Missing numpy dependency → ✅ **FINAL FIX**: Added numpy==1.24.3 to requirements.txt

### Lessons Learned

1. **Dependency Management**: Always explicitly declare all dependencies, even transitive ones
2. **Systematic Testing**: Test each component individually before integration
3. **Real Verification**: Use actual terminal commands to verify claims, not assumptions
4. **Documentation**: Keep troubleshooting guides updated with real-world experience
5. **Git Branch Consistency**: Ensure local, remote, and deployment scripts use same branch names

## 🎯 Real-World Timeline

Our actual deployment experience:
1. **Initial setup**: Webhook server running ✅
2. **First test**: HTTP 403 → Fixed secret mismatch (Issue 1)
3. **Second test**: Connection timeout → Fixed security group (Issue 2) 
4. **Third test**: Auth success but no repo update → Fixed branch mismatch (Issue 3)
5. **Fourth test**: Still no update → Fixed uncommitted changes (Issue 4)
6. **Final test**: Full auto-deploy working ✅, service startup issue (Issue 6)

**Result**: Complete GitHub → EC2 auto-deploy pipeline functional!
## 🛠️ Quick Diagnostic Script

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
curl -X POST http://18.234.53.50:5005/webhook \
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

## 📚 Complete Reference Commands

### Quick Health Check (Copy-Paste Ready)
```bash
# Test all components quickly
echo "=== CHATBOT SERVICE STATUS ==="
ssh -i ~/.ssh/chatbot-demo-key.pem ubuntu@18.234.53.50 "sudo systemctl status chatbot"

echo "=== HEALTH ENDPOINT ==="
ssh -i ~/.ssh/chatbot-demo-key.pem ubuntu@18.234.53.50 "curl -s http://localhost:8000/health | python3 -m json.tool"

echo "=== WEBHOOK STATUS ==="
ssh -i ~/.ssh/chatbot-demo-key.pem ubuntu@18.234.53.50 "curl -s http://localhost:5005/health"

echo "=== GIT SYNC STATUS ==="
echo "Local:"
git log --oneline -3
echo "EC2:"
ssh -i ~/.ssh/chatbot-demo-key.pem ubuntu@18.234.53.50 "cd /opt/chatbot && git log --oneline -3"
```

### Emergency Restart Commands
```bash
# Restart chatbot service
ssh -i ~/.ssh/chatbot-demo-key.pem ubuntu@18.234.53.50 "sudo systemctl restart chatbot"

# Restart webhook server
ssh -i ~/.ssh/chatbot-demo-key.pem ubuntu@18.234.53.50 "pkill -f webhook.py && cd /opt/chatbot/deployment && nohup python3 webhook.py > webhook.log 2>&1 &"

# Full system restart
ssh -i ~/.ssh/chatbot-demo-key.pem ubuntu@18.234.53.50 "cd /opt/chatbot/deployment && ./service_manager.sh restart"
```

### Current Verified Configuration (2025-07-30)
- **EC2 Instance**: 18.234.53.50
- **SSH Key**: ~/.ssh/chatbot-demo-key.pem
- **Chatbot Port**: 8000 (internal), 80 (external via nginx)
- **Webhook Port**: 5005
- **Git Branch**: master
- **Python Environment**: /opt/chatbot/venv
- **Service Status**: Active (running) 8+ hours
- **Critical Dependencies**: numpy==1.24.3 (REQUIRED)

---

**📝 MAINTENANCE NOTE**: This guide documents real-world deployment experience as of 2025-07-30. All commands and solutions have been verified in production. Update this guide when new issues are discovered and resolved.
