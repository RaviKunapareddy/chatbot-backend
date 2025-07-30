# 🚀 Deployment Checklist & Reference Guide

## 📋 Overview

This document serves as the master reference for understanding the complete AI chatbot deployment system. Based on verified production deployment as of 2025-07-30.

**✅ DEPLOYMENT STATUS: LIVE AND OPERATIONAL**
- **Production URL**: http://YOUR_EC2_IP
- **API Documentation**: http://YOUR_EC2_IP/docs
- **Health Check**: http://YOUR_EC2_IP/health
- **Last Verified**: 2025-07-30 11:25 UTC

---

## 🎯 WHAT We Built

### Core Application
- **FastAPI Backend**: Modern Python web framework for AI chatbot
- **Multi-LLM Support**: AWS Bedrock + Google Gemini integration
- **Vector Search**: Pinecone cloud for RAG (Retrieval-Augmented Generation)
- **Conversation Memory**: Redis Cloud for chat history caching
- **Product Catalog**: S3-based product data with search capabilities

### Architecture Components
```
Frontend Request → Nginx (Port 80) → FastAPI (Port 8000) → Cloud Services
                                                         ├── Pinecone (Vector Search)
                                                         ├── Redis (Caching)
                                                         ├── AWS S3 (Data Storage)
                                                         └── LLM APIs (Bedrock/Gemini)
```

### Auto-Deployment Pipeline
```
GitHub Push → Webhook (Port 5005) → Git Pull → Dependency Install → Service Restart
```

---

## 🔧 HOW We Deployed It

### Deployment Method: GitHub → EC2 Webhook Pipeline

#### Phase 1: Infrastructure Setup
1. **AWS EC2 Instance**: Ubuntu 22.04 LTS (t2.micro - free tier)
2. **Security Groups**: Ports 22 (SSH), 80 (HTTP), 5005 (Webhook)
3. **SSH Access**: Key-based authentication with `chatbot-demo-key.pem`

#### Phase 2: Application Deployment
1. **Code Upload**: Manual initial deployment via SCP
2. **Environment Setup**: Python virtual environment + dependencies
3. **Service Configuration**: Systemd service for auto-start
4. **Web Server**: Nginx reverse proxy for production access

#### Phase 3: Auto-Deploy Setup
1. **Webhook Server**: Python Flask server on port 5005
2. **GitHub Integration**: Repository webhook configuration
3. **Deployment Script**: Automated git pull + service restart
4. **Authentication**: GitHub webhook secret for security

### Key Deployment Commands
```bash
# Initial setup
./deployment/initial_setup.sh

# Service management
./deployment/service_manager.sh start|stop|restart|status

# Manual deployment
./deployment/manual_deploy.sh ~/.ssh/YOUR_SSH_KEY.pem YOUR_EC2_IP
```

---

## 💡 WHY We Made Key Decisions

### Cloud-Only Architecture
**Decision**: Use only cloud services (no local databases)
**Reasoning**: 
- Scalability without infrastructure management
- Free tier availability for cost-effective demo
- Production-ready from day one
- No single points of failure

### Free Tier Services Selection
**Decision**: Pinecone Cloud + Redis Cloud + AWS Free Tier
**Reasoning**:
- Cost-effective for demonstration purposes
- Professional-grade services
- Easy to scale up when needed
- Real production environment experience

### GitHub Webhook Auto-Deploy
**Decision**: Automated deployment via GitHub webhooks
**Reasoning**:
- Continuous deployment for rapid iteration
- Professional development workflow
- Reduces manual deployment errors
- Demonstrates DevOps best practices

### Ubuntu + Systemd + Nginx Stack
**Decision**: Traditional Linux production stack
**Reasoning**:
- Industry standard for Python web applications
- Reliable and well-documented
- Easy to troubleshoot and maintain
- Cost-effective on AWS free tier

---

## 📍 WHERE Everything Is Located

### File Structure
```
/opt/chatbot/                          # Main application directory
├── main.py                           # FastAPI application entry point
├── requirements.txt                  # Python dependencies (includes numpy fix)
├── .env                             # Environment variables (secrets)
├── venv/                            # Python virtual environment
├── deployment/                      # Deployment scripts and configs
│   ├── initial_setup.sh            # One-time server setup
│   ├── service_manager.sh           # Daily operations script
│   ├── webhook.py                   # GitHub webhook server
│   ├── manual_deploy.sh             # Emergency deployment
│   └── github_ec2_deployment_troubleshooting_guide.md
├── router/                          # API route handlers
├── services.py                      # Cloud service integrations
├── config.py                        # Application configuration
└── [other application modules]
```

### System Services
```
/etc/systemd/system/chatbot.service   # Systemd service definition
/etc/nginx/sites-available/default    # Nginx configuration
/var/log/nginx/                       # Web server logs
/home/ubuntu/.ssh/                    # SSH keys and config
```

### Network Endpoints
- **Main Application**: http://YOUR_EC2_IP (Port 80 → 8000)
- **API Documentation**: http://YOUR_EC2_IP/docs
- **Health Check**: http://YOUR_EC2_IP/health
- **Webhook Receiver**: http://YOUR_EC2_IP:5005/webhook
- **SSH Access**: ssh -i ~/.ssh/YOUR_SSH_KEY.pem ubuntu@YOUR_EC2_IP

### Cloud Service Locations
- **Pinecone Index**: Cloud-hosted vector database
- **Redis Instance**: Cloud-hosted cache
- **S3 Bucket**: AWS cloud storage for product data
- **GitHub Repository**: Source code and version control

---

## ✅ Deployment Verification Checklist

### Pre-Deployment Requirements
- [ ] AWS EC2 instance running Ubuntu 22.04
- [ ] Security groups configured (ports 22, 80, 5005)
- [ ] SSH key pair created and accessible
- [ ] GitHub repository with webhook configured
- [ ] Cloud service credentials available (.env file)

### Post-Deployment Verification
- [ ] **Service Status**: `sudo systemctl status chatbot` shows Active
- [ ] **Health Endpoint**: `curl http://YOUR_EC2_IP/health` returns JSON
- [ ] **Webhook Status**: `curl http://YOUR_EC2_IP:5005/health` returns healthy
- [ ] **Auto-Deploy**: Git push triggers automatic deployment
- [ ] **Cloud Services**: Redis and Pinecone show "connected" status
- [ ] **Dependencies**: All requirements.txt packages installed (including numpy)

### Critical Success Indicators
```bash
# Quick verification commands
ssh -i ~/.ssh/YOUR_SSH_KEY.pem ubuntu@YOUR_EC2_IP "sudo systemctl status chatbot"
curl -s http://YOUR_EC2_IP/health | python3 -m json.tool
curl -s http://YOUR_EC2_IP:5005/health
```

---

## 🔧 Maintenance & Operations

### Daily Operations
```bash
# Check system health
./deployment/service_manager.sh status

# Restart services if needed
./deployment/service_manager.sh restart

# View recent logs
./deployment/service_manager.sh logs
```

### Emergency Procedures
```bash
# Full system restart
ssh -i ~/.ssh/YOUR_SSH_KEY.pem ubuntu@YOUR_EC2_IP "sudo reboot"

# Manual deployment (if auto-deploy fails)
./deployment/manual_deploy.sh ~/.ssh/YOUR_SSH_KEY.pem YOUR_EC2_IP

# Service recovery
ssh -i ~/.ssh/YOUR_SSH_KEY.pem ubuntu@YOUR_EC2_IP "sudo systemctl restart chatbot"
```

### Monitoring Commands
```bash
# System resources
ssh -i ~/.ssh/YOUR_SSH_KEY.pem ubuntu@YOUR_EC2_IP "htop"

# Service logs
ssh -i ~/.ssh/YOUR_SSH_KEY.pem ubuntu@YOUR_EC2_IP "journalctl -u chatbot -f"

# Webhook logs
ssh -i ~/.ssh/YOUR_SSH_KEY.pem ubuntu@YOUR_EC2_IP "tail -f /opt/chatbot/deployment/webhook.log"
```

---

## 📚 Related Documentation

- **Troubleshooting Guide**: `deployment/github_ec2_deployment_troubleshooting_guide.md`
- **Operations Guide**: `DEPLOYMENT_OPERATIONS_GUIDE.md`
- **Project README**: `README.md`
- **API Documentation**: http://YOUR_EC2_IP/docs (Live Swagger UI)

---

## 🎯 Quick Reference

### Essential Information
- **EC2 IP**: YOUR_EC2_IP
- **SSH Key**: ~/.ssh/YOUR_SSH_KEY.pem
- **Git Branch**: master
- **Python Path**: /opt/chatbot/venv/bin/python
- **Critical Dependency**: numpy==1.24.3 (REQUIRED for service startup)

### One-Line Health Check
```bash
curl -s http://YOUR_EC2_IP/health && echo " ✅ HEALTHY" || echo " ❌ UNHEALTHY"
```

---

**📝 Document Status**: Complete deployment reference as of 2025-07-30. All information verified in production environment.
