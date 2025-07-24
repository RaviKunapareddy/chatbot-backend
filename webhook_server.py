from flask import Flask, request
import subprocess
import hmac
import hashlib

app = Flask(__name__)
GITHUB_SECRET = b"ChatbotWebhook#5005"  # Replace this after GitHub setup

def verify_signature(payload, signature):
    mac = hmac.new(GITHUB_SECRET, msg=payload, digestmod=hashlib.sha256)
    return hmac.compare_digest("sha256=" + mac.hexdigest(), signature)

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.data
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verify_signature(payload, signature):
        return "Invalid signature", 403

    subprocess.run(["bash", "/opt/chatbot/github_auto_deploy.sh"])
    return "✅ Deployment triggered", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005)
