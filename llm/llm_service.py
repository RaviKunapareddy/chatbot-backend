"""
LLM Response Generation

This module provides LLM functionality for generating conversational responses.
Uses AWS Bedrock and Google Gemini as fallback.
"""

import os
import json
from typing import Optional
import boto3
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

class LLMService:
    """Handles LLM response generation for conversational AI"""
    
    def __init__(self):
        print("🤖 Initializing LLM Service...")
        
        # Initialize LLM services
        self.bedrock_client = None
        self.aws_available = False
        self.gemini_client = None
        self.gemini_available = False
        self.aws_model_id = None
        
        self._init_aws_bedrock()
        self._init_gemini()
        
        print("✅ LLM Service ready")
    
    def _init_aws_bedrock(self):
        """Initialize AWS Bedrock for LLM responses"""
        try:
            aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
            if aws_access_key and aws_access_key != "your_aws_access_key_here":
                self.bedrock_client = boto3.client(
                    'bedrock-runtime',
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                    region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1")
                )
                
                self.aws_model_id = os.getenv("AWS_BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
                self.aws_available = True
                print("✅ AWS Bedrock LLM connected")
        except Exception as e:
            print(f"⚠️ AWS Bedrock unavailable: {e}")
    
    def _init_gemini(self):
        """Initialize Google Gemini as fallback LLM"""
        try:
            google_api_key = os.getenv("GOOGLE_API_KEY")
            if google_api_key and google_api_key != "your_google_api_key_here":
                genai.configure(api_key=google_api_key)
                self.gemini_client = genai.GenerativeModel("gemini-1.5-flash")
                self.gemini_available = True
                print("✅ Google Gemini LLM connected")
        except Exception as e:
            print(f"⚠️ Google Gemini unavailable: {e}")
    
    def _generate_with_llm(self, prompt: str) -> Optional[str]:
        """Generate response using available LLM (AWS Bedrock or Gemini fallback)"""
        
        # Try AWS Bedrock first
        if self.aws_available and self.bedrock_client:
            try:
                # Handle different model formats
                if "claude" in self.aws_model_id:
                    # Claude Messages API format
                    body = json.dumps({
                        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
                        "max_tokens": 200,
                        "temperature": 0.7,
                        "anthropic_version": "bedrock-2023-05-31"
                    })
                elif "nova" in self.aws_model_id:
                    # Nova format
                    body = json.dumps({
                        "messages": [{"role": "user", "content": [{"text": prompt}]}],
                        "inferenceConfig": {"maxTokens": 200, "temperature": 0.7}
                    })
                elif "titan" in self.aws_model_id:
                    # Titan format
                    body = json.dumps({
                        "inputText": prompt,
                        "textGenerationConfig": {"maxTokenCount": 200, "temperature": 0.7}
                    })
                else:
                    # Default to Claude format
                    body = json.dumps({
                        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
                        "max_tokens": 200,
                        "temperature": 0.7,
                        "anthropic_version": "bedrock-2023-05-31"
                    })
                
                response = self.bedrock_client.invoke_model(
                    modelId=self.aws_model_id,
                    body=body
                )
                
                response_body = json.loads(response['body'].read())
                
                # Parse response based on model type
                if "claude" in self.aws_model_id:
                    content = response_body.get('content', [])
                    return content[0].get('text', '') if content else None
                elif "nova" in self.aws_model_id:
                    output = response_body.get('output', {})
                    message = output.get('message', {})
                    content = message.get('content', [])
                    return content[0].get('text', '') if content else None
                elif "titan" in self.aws_model_id:
                    results = response_body.get('results', [])
                    return results[0].get('outputText', '') if results else None
                else:
                    # Default Claude parsing
                    content = response_body.get('content', [])
                    return content[0].get('text', '') if content else None
                
            except Exception as e:
                print(f"❌ AWS Bedrock error: {e}")
        
        # Try Gemini fallback
        if self.gemini_available and self.gemini_client:
            try:
                response = self.gemini_client.generate_content(prompt)
                return response.text.strip()
            except Exception as e:
                print(f"❌ Google Gemini error: {e}")
        
        return None

# Global instance
llm_service = LLMService() 