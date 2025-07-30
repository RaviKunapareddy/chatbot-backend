import os
import json
import logging
from typing import Dict, Any
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class IntentClassifier:
    def __init__(self):
        self.aws_available = False
        self.gemini_available = False
        
        # Initialize AWS Bedrock (Primary)
        self._init_aws_bedrock()
        
        # Initialize Google Gemini (Fallback)
        self._init_gemini()
        
        # Status summary - use logging instead of print
        if self.aws_available:
            logger.info("AWS Bedrock ready (Primary)")
        elif self.gemini_available:
            logger.info("Google Gemini ready (Fallback)")
        else:
            logger.warning("Using keyword-based classification (Final fallback)")
    
    def _init_aws_bedrock(self):
        """Initialize AWS Bedrock client"""
        aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        
        if (aws_access_key and aws_secret_key and 
            aws_access_key != "your_aws_access_key_here" and
            aws_secret_key != "your_aws_secret_access_key_here"):
            
            try:
                self.bedrock_client = boto3.client(
                    'bedrock-runtime',
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key,
                    region_name=aws_region
                )
                self.aws_model_id = os.getenv("AWS_BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
                self.aws_available = True
                
            except Exception as e:
                logger.error(f"AWS Bedrock initialization failed: {e}")
                self.aws_available = False
    
    def _init_gemini(self):
        """Initialize Google Gemini client"""
        google_api_key = os.getenv("GOOGLE_API_KEY")
        
        if google_api_key and google_api_key != "your_google_api_key_here":
            try:
                genai.configure(api_key=google_api_key)
                self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
                self.gemini_client = genai.GenerativeModel(self.gemini_model)
                self.gemini_available = True
                
            except Exception as e:
                logger.error(f"Google Gemini initialization failed: {e}")
                self.gemini_available = False
    
    async def classify_intent(self, user_message: str) -> Dict[str, Any]:
        """Classify user intent: AWS Bedrock → Gemini → Keyword fallback"""
        
        # Try AWS Bedrock first (Primary)
        if self.aws_available:
            result = await self._classify_with_bedrock(user_message)
            if result:
                # Add price extraction
                result = self._enhance_with_price_extraction(user_message, result)
                return result
        
        # Try Google Gemini (Fallback)
        if self.gemini_available:
            result = await self._classify_with_gemini(user_message)
            if result:
                # Add price extraction
                result = self._enhance_with_price_extraction(user_message, result)
                return result
        
        # Final fallback to keyword-based
        logger.info("Using keyword-based classification (final fallback)")
        result = self._fallback_classification(user_message)
        # Add price extraction
        result = self._enhance_with_price_extraction(user_message, result)
        return result
    
    async def _classify_with_bedrock(self, user_message: str) -> Dict[str, Any]:
        """Classify using AWS Bedrock"""
        try:
            prompt_content = f"""You are an intent classifier for an e-commerce chatbot. 
Classify this message into one of these intents:

1. SEARCH - Find/browse products OR ask about specific products (e.g., "show me laptops", "tell me about the first option", "can you tell me about that product")
2. CART - Cart operations (e.g., "add to cart", "remove item", "view cart")  
3. RECOMMENDATION - Product suggestions (e.g., "recommend me a phone", "what's trending")
4. SUPPORT - Help with policies ONLY (e.g., "return policy", "shipping info", "warranty", "contact support")

IMPORTANT: Questions about specific products (like "tell me about the first option" or "can you tell me about that product") are SEARCH, not SUPPORT.

User message: "{user_message}"

Respond with ONLY valid JSON:
{{
    "intent": "SEARCH|CART|RECOMMENDATION|SUPPORT",
    "confidence": 0.0-1.0,
    "entities": {{
        "product_type": "extracted product category if any",
        "action": "specific action if any",
        "keywords": ["relevant", "keywords"]
    }}
}}"""

            # Different body format based on model type
            if "claude" in self.aws_model_id:
                # Claude Messages API format (new)
                body = json.dumps({
                    "messages": [
                        {
                            "role": "user",
                            "content": [{"type": "text", "text": prompt_content}]
                        }
                    ],
                    "max_tokens": 200,
                    "temperature": 0.1,
                    "anthropic_version": "bedrock-2023-05-31"
                })
            elif "llama" in self.aws_model_id:
                # Llama format
                body = json.dumps({
                    "prompt": prompt_content,
                    "max_gen_len": 200,
                    "temperature": 0.1
                })
            elif "titan" in self.aws_model_id:
                # Titan format
                body = json.dumps({
                    "inputText": prompt_content,
                    "textGenerationConfig": {
                        "maxTokenCount": 200,
                        "temperature": 0.1
                    }
                })
            elif "nova" in self.aws_model_id:
                # Nova format
                body = json.dumps({
                    "messages": [
                        {
                            "role": "user",
                            "content": [{"text": prompt_content}]
                        }
                    ],
                    "inferenceConfig": {
                        "maxTokens": 200,
                        "temperature": 0.1
                    }
                })
            else:
                # Default to Claude Messages API
                body = json.dumps({
                    "messages": [
                        {
                            "role": "user",
                            "content": [{"type": "text", "text": prompt_content}]
                        }
                    ],
                    "max_tokens": 200,
                    "temperature": 0.1,
                    "anthropic_version": "bedrock-2023-05-31"
                })
            
            response = self.bedrock_client.invoke_model(
                modelId=self.aws_model_id,
                body=body
            )
            
            # Parse response body
            response_body = json.loads(response['body'].read())
            
            # Extract text based on model type
            if "claude" in self.aws_model_id:
                # Claude Messages API response format
                content = response_body.get('content', [])
                result_text = content[0].get('text', '') if content else ''
            elif "llama" in self.aws_model_id:
                result_text = response_body.get('generation', '')
            elif "titan" in self.aws_model_id:
                results = response_body.get('results', [])
                result_text = results[0].get('outputText', '') if results else ''
            elif "nova" in self.aws_model_id:
                # Nova response format
                output = response_body.get('output', {})
                message = output.get('message', {})
                content = message.get('content', [])
                result_text = content[0].get('text', '') if content else ''
            else:
                # Default to Claude Messages API
                content = response_body.get('content', [])
                result_text = content[0].get('text', '') if content else ''
            
            # Clean up the response and parse JSON
            result_text = result_text.strip()
            if result_text.startswith('```json'):
                result_text = result_text.replace('```json', '').replace('```', '').strip()
            
            intent_data = json.loads(result_text)
            
            logger.info(f"Bedrock classified: {intent_data['intent']} (confidence: {intent_data['confidence']})")
            return intent_data
            
        except Exception as e:
            logger.error(f"Bedrock classification error: {e}")
            return None
    
    async def _classify_with_gemini(self, user_message: str) -> Dict[str, Any]:
        """Classify using Google Gemini"""
        try:
            prompt = f"""You are an intent classifier for an e-commerce chatbot. 
Classify this message into one of these intents:

1. SEARCH - Find/browse products OR ask about specific products (e.g., "show me laptops", "tell me about the first option", "can you tell me about that product")
2. CART - Cart operations (e.g., "add to cart", "remove item", "view cart")  
3. RECOMMENDATION - Product suggestions (e.g., "recommend me a phone", "what's trending")
4. SUPPORT - Help with policies ONLY (e.g., "return policy", "shipping info", "warranty", "contact support")

IMPORTANT: Questions about specific products (like "tell me about the first option" or "can you tell me about that product") are SEARCH, not SUPPORT.

User message: "{user_message}"

Respond with ONLY valid JSON:
{{
    "intent": "SEARCH|CART|RECOMMENDATION|SUPPORT",
    "confidence": 0.0-1.0,
    "entities": {{
        "product_type": "extracted product category if any",
        "action": "specific action if any",
        "keywords": ["relevant", "keywords"]
    }}
}}"""

            response = self.gemini_client.generate_content(prompt)
            result_text = response.text.strip()
            
            # Clean up the response and parse JSON
            if result_text.startswith('```json'):
                result_text = result_text.replace('```json', '').replace('```', '').strip()
            
            intent_data = json.loads(result_text)
            
            logger.info(f"Gemini classified: {intent_data['intent']} (confidence: {intent_data['confidence']})")
            return intent_data
            
        except Exception as e:
            logger.error(f"Gemini classification error: {e}")
            return None
    
    def _fallback_classification(self, user_message: str) -> Dict[str, Any]:
        """Keyword-based classification (final fallback)"""
        message_lower = user_message.lower()
        
        # Enhanced keyword matching with priority order
        cart_keywords = ['cart', 'add', 'remove', 'buy', 'purchase', 'order']
        support_keywords = ['policy', 'return', 'shipping', 'warranty', 'support', 'contact']
        recommendation_keywords = ['recommend', 'suggest', 'trending', 'popular', 'gift']
        search_keywords = ['show', 'find', 'search', 'browse', 'get', 'want', 'need', 'tell me about', 'about the', 'first option', 'second option', 'third option']
        
        # Check for follow-up questions about products first (most specific for context)
        if any(phrase in message_lower for phrase in ['tell me about', 'about the', 'first option', 'second option', 'third option', 'more details', 'more info']):
            intent = "SEARCH"
        # Check cart 
        elif any(word in message_lower for word in cart_keywords):
            intent = "CART"
        # Check support (only for actual policy questions)
        elif any(word in message_lower for word in support_keywords) and not any(phrase in message_lower for phrase in ['about the', 'tell me about']):
            intent = "SUPPORT"
        # Check for explicit recommendation requests
        elif any(word in message_lower for word in recommendation_keywords):
            intent = "RECOMMENDATION"
        # Check for explicit search terms
        elif any(word in message_lower for word in search_keywords):
            intent = "SEARCH"
        # If just product names or general queries, default to search
        else:
            intent = "SEARCH"
            
        # Extract potential product type
        product_categories = ['laptop', 'phone', 'watch', 'shoes', 'dress', 'shirt', 'bag', 'beauty', 'fragrance']
        product_type = None
        for category in product_categories:
            if category in message_lower:
                product_type = category
                break
                
        return {
            "intent": intent,
            "confidence": 0.8,
            "entities": {
                "product_type": product_type,
                "action": None,
                "keywords": [word for word in message_lower.split()[:5] if len(word) > 2]
            }
        }
    
    def _enhance_with_price_extraction(self, user_message: str, intent_result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract price information from user message"""
        import re
        
        message_lower = user_message.lower()
        
        # Extract price patterns
        price_patterns = [
            r'under\s+\$?(\d+)',  # "under $500"
            r'less\s+than\s+\$?(\d+)',  # "less than $500"
            r'below\s+\$?(\d+)',  # "below $500"
            r'up\s+to\s+\$?(\d+)',  # "up to $500"
            r'max\s+\$?(\d+)',  # "max $500"
            r'\$?(\d+)\s+or\s+less',  # "$500 or less"
            r'\$?(\d+)\s+and\s+under',  # "$500 and under"
        ]
        
        price_mentioned = None
        for pattern in price_patterns:
            match = re.search(pattern, message_lower)
            if match:
                price_mentioned = float(match.group(1))
                break
        
        # Add price information to intent result
        intent_result['price_mentioned'] = price_mentioned
        intent_result['corrected_query'] = user_message
        intent_result['key_terms'] = intent_result.get('entities', {}).get('keywords', [])
        
        return intent_result

# Global instance
intent_classifier = IntentClassifier() 