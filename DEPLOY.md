# 🚀 EC2 Free Tier Deployment Guide

Deploy your AI Chatbot Backend API to AWS EC2 Free Tier.

## 📋 Prerequisites

### 1. AWS Account Setup
- Create AWS account (free tier eligible)
- Launch EC2 t2.micro instance (Ubuntu 22.04 LTS)
- Configure Security Group (ports 22, 80, 8000)
- Create/download key pair for SSH access

### 2. Cloud Services (Free Tiers Available)
- **Redis Cloud**: https://redis.com/try-free/ (30MB free)
- **Elasticsearch Cloud**: https://cloud.elastic.co/ (14-day trial)
- **Google AI**: https://makersuite.google.com/app/apikey (free quota)
- **Pinecone**: https://www.pinecone.io/ (1 index free)
- **HuggingFace**: https://huggingface.co/settings/tokens (free API)
- **AWS S3**: Included in free tier (5GB storage)

## 🚀 Deployment Steps

### Step 1: Connect to EC2
```bash
# SSH to your EC2 instance
ssh -i your-key.pem ubuntu@YOUR_EC2_PUBLIC_IP
```

### Step 2: Upload Application Files
```bash
# Option A: Using SCP
scp -i your-key.pem -r ./backend ubuntu@YOUR_EC2_PUBLIC_IP:/home/ubuntu/

# Option B: Using Git (if you have a repo)
git clone https://github.com/your-username/your-repo.git
cd your-repo/backend
```

### Step 3: Run Deployment Script
```bash
# Make script executable and run
chmod +x deploy.sh
./deploy.sh
```

### Step 4: Configure Environment Variables
```bash
# Edit the environment file with your credentials
sudo nano /opt/chatbot/.env

# Fill in your actual values:
REDIS_HOST=your-redis-host
REDIS_PASSWORD=your-redis-password
ELASTICSEARCH_HOST=your-elasticsearch-host
ELASTICSEARCH_API_KEY=your-elasticsearch-api-key
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
GOOGLE_API_KEY=your-google-api-key
PINECONE_API_KEY=your-pinecone-api-key
HF_API_KEY=your-huggingface-api-key
```

### Step 5: Start the Service
```bash
# Start the chatbot service
sudo systemctl start chatbot

# Check if it's running
sudo systemctl status chatbot

# View logs
sudo journalctl -u chatbot -f
```

## 🌐 Testing Your API

### Health Check
```bash
curl http://YOUR_EC2_PUBLIC_IP/health
```

### API Documentation
Open in browser: `http://YOUR_EC2_PUBLIC_IP/docs`

### Test Chat Endpoint
```bash
curl -X POST "http://YOUR_EC2_PUBLIC_IP/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello", "session_id": "test"}'
```

## 🔧 Management Commands

### Service Control
```bash
# Start service
sudo systemctl start chatbot

# Stop service
sudo systemctl stop chatbot

# Restart service
sudo systemctl restart chatbot

# Check status
sudo systemctl status chatbot

# View logs
sudo journalctl -u chatbot -f
```

### Nginx Control
```bash
# Restart nginx
sudo systemctl restart nginx

# Check nginx status
sudo systemctl status nginx

# Test nginx config
sudo nginx -t
```

## 📊 Monitoring

### Check Resource Usage
```bash
# CPU and Memory usage
htop

# Disk usage
df -h

# Service logs
sudo journalctl -u chatbot --since "1 hour ago"
```

### Log Locations
- Application logs: `sudo journalctl -u chatbot`
- Nginx logs: `/var/log/nginx/`
- System logs: `/var/log/syslog`

## 🔒 Security Notes

### Basic Security (Recommended)
```bash
# Update system regularly
sudo apt update && sudo apt upgrade

# Configure UFW firewall
sudo ufw enable
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow 8000

# Change default SSH port (optional)
sudo nano /etc/ssh/sshd_config
```

## 💰 Cost Optimization

### Free Tier Limits
- **EC2 t2.micro**: 750 hours/month (1 instance 24/7)
- **EBS Storage**: 30GB free
- **Data Transfer**: 1GB outbound/month

### Tips to Stay Within Free Tier
- Use only 1 t2.micro instance
- Monitor data transfer usage
- Stop instance when not needed for testing
- Use CloudWatch free tier for monitoring

## 🐛 Troubleshooting

### Common Issues

#### Service Won't Start
```bash
# Check logs for errors
sudo journalctl -u chatbot -n 50

# Check if all environment variables are set
sudo -u ubuntu /opt/chatbot/venv/bin/python -c "
import os
from dotenv import load_dotenv
load_dotenv('/opt/chatbot/.env')
print('Redis:', os.getenv('REDIS_HOST'))
print('Elasticsearch:', os.getenv('ELASTICSEARCH_HOST'))
"
```

#### High Memory Usage
```bash
# Reduce Gunicorn workers in systemd service
sudo nano /etc/systemd/system/chatbot.service
# Change -w 2 to -w 1

sudo systemctl daemon-reload
sudo systemctl restart chatbot
```

#### Connection Errors
```bash
# Test individual services
curl -X GET "http://127.0.0.1:8000/health"
sudo systemctl status nginx
```

## 📝 Next Steps

After successful deployment:
1. Configure domain name (optional)
2. Setup SSL certificate with Let's Encrypt
3. Configure monitoring and alerts
4. Setup automated backups
5. Consider upgrading to paid tiers for production use

## 🆘 Support

If you encounter issues:
1. Check the logs: `sudo journalctl -u chatbot -f`
2. Verify all environment variables are set correctly
3. Ensure all cloud services are properly configured
4. Check EC2 security group allows traffic on ports 80 and 8000 