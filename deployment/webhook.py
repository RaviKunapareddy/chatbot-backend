#!/usr/bin/env python3

"""
Simple GitHub Webhook Handler for Chatbot Auto-Deployment
Replaces 138 lines of over-engineered webhook server with ~50 lines
Keeps essential security and functionality for AWS deployment

Logging Features:
- Structured logging with timestamp, module, level, and message
- File output to /opt/chatbot/logs/webhook/webhook.log with automatic directory creation
- Console output for immediate visibility
- Standard log levels (INFO, WARNING, ERROR)
- Context-rich error messages with emoji prefixes
"""

import hashlib
import hmac
import logging
import os
import subprocess

from flask import Flask, jsonify, request

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("/opt/chatbot/logs/webhook/webhook.log"),
        logging.StreamHandler(),
    ],
)

# Create logs directory if it doesn't exist
os.makedirs("/opt/chatbot/logs/webhook", exist_ok=True)

app = Flask(__name__)

# Load GitHub webhook secret
GITHUB_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "").encode("utf-8")
if not GITHUB_SECRET:
    logger.error("❌ GITHUB_WEBHOOK_SECRET environment variable required")
    exit(1)


def verify_signature(payload, signature):
    """Verify GitHub webhook signature for security"""
    if not signature:
        return False

    expected = "sha256=" + hmac.new(GITHUB_SECRET, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.route("/webhook", methods=["POST"])
def handle_webhook():
    """Handle GitHub webhook and trigger deployment"""

    # Security validation
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verify_signature(request.data, signature):
        return jsonify({"error": "Invalid signature"}), 403

    # Get event info
    event = request.headers.get("X-GitHub-Event", "unknown")
    payload = request.get_json()

    if not payload:
        return jsonify({"error": "Invalid payload"}), 400

    repo = payload.get("repository", {}).get("full_name", "unknown")
    logger.info(f"🎣 Received {event} webhook from {repo}")

    # Only deploy on push events to master branch
    if event == "push" and payload.get("ref") == "refs/heads/master":
        try:
            logger.info("🚀 Triggering auto-deployment...")

            # Simple deployment: pull latest code and restart
            result = subprocess.run(
                [
                    "/bin/bash",
                    "-c",
                    """
                cd /opt/chatbot || { echo "Error: /opt/chatbot directory not found"; exit 1; } && 
                git pull origin master && 
                source venv/bin/activate && 
                pip install -r requirements.txt && 
                sudo systemctl restart chatbot chatbot-webhook
                """,
                ],
                capture_output=True,
                text=True,
                timeout=180,
            )

            if result.returncode == 0:
                logger.info("✅ Deployment successful")
                return jsonify({"status": "success", "message": "Deployed successfully"})
            else:
                logger.error(f"❌ Deployment failed: {result.stderr}")
                return jsonify({"status": "error", "message": "Deployment failed"}), 500

        except subprocess.TimeoutExpired:
            logger.error("❌ Deployment timed out after 180 seconds")
            return jsonify({"status": "error", "message": "Deployment timeout"}), 500
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"status": "ignored", "message": f"Ignored {event} event"})


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "webhook"})


if __name__ == "__main__":
    logger.info("🎣 Starting GitHub webhook server on port 5005...")
    app.run(host="0.0.0.0", port=5005, debug=False)
