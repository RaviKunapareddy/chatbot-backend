import os
import uuid
from typing import List, Dict, Any, Optional
import requests
from dotenv import load_dotenv

# Optional Pinecone import - using v7.x API
try:
    from pinecone import Pinecone
    PINECONE_AVAILABLE = True
except ImportError:
    PINECONE_AVAILABLE = False
    print("⚠️ Pinecone not available - support RAG will be disabled")

# Load environment variables from .env file
load_dotenv()

class PineconeSupport:
    def __init__(self, api_key: str = None, environment: str = "us-east-1", index_name: str = "chatbot-support-knowledge"):
        self.api_key = api_key or os.getenv("PINECONE_API_KEY")
        self.environment = environment
        self.index_name = index_name
        self.dimension = 384  # BAAI/bge-small-en-v1.5 dimension
        
        # Initialize Hugging Face API
        self.hf_api_key = os.getenv("HF_API_KEY")
        self.hf_model = os.getenv("HF_SUPPORT_MODEL", "BAAI/bge-small-en-v1.5")
        # Use direct models API for feature extraction  
        self.hf_api_url = f"https://api-inference.huggingface.co/models/{self.hf_model}"
        
        # Initialize Pinecone
        self.pc = None
        self.index = None
        self._initialize_pinecone()
    
    def _initialize_pinecone(self):
        """Initialize Pinecone connection with v6.x API"""
        if not PINECONE_AVAILABLE:
            print("⚠️ Pinecone package not available. Support RAG will be disabled.")
            return
            
        try:
            if not self.api_key:
                print("⚠️ PINECONE_API_KEY not found. Support RAG will be disabled.")
                return
            
            # Initialize Pinecone with new v6.x API
            self.pc = Pinecone(api_key=self.api_key)
            
            # Connect to existing serverless index
            try:
                self.index = self.pc.Index(self.index_name)
                # Test the connection
                stats = self.index.describe_index_stats()
                print(f"✅ Connected to Pinecone serverless index: {self.index_name}")
                print(f"📊 Index has {stats.total_vector_count} vectors")
            except Exception as connect_error:
                print(f"❌ Could not connect to index '{self.index_name}': {connect_error}")
                raise connect_error
            
        except Exception as e:
            print(f"❌ Pinecone initialization failed: {e}")
            self.pc = None
            self.index = None
    
    def is_available(self) -> bool:
        """Check if Pinecone is available"""
        return self.index is not None
    
    def create_embedding(self, text: str) -> List[float]:
        """Create embedding using Hugging Face API"""
        try:
            headers = {"Authorization": f"Bearer {self.hf_api_key}"}
            response = requests.post(
                self.hf_api_url,
                headers=headers,
                json={"inputs": [text]}  # Correct format: array of strings
            )
            
            if response.status_code == 200:
                embeddings = response.json()
                if isinstance(embeddings, list) and len(embeddings) > 0:
                    return embeddings[0]  # First (and only) embedding
                else:
                    print(f"Unexpected embedding format: {embeddings}")
                    return []
            else:
                print(f"Error creating embedding: {response.text}")
                return []
        except Exception as e:
            print(f"Error creating embedding: {e}")
            return []
    
    def upsert_document(self, doc: Dict[str, Any]) -> bool:
        """Upsert a single support document"""
        if not self.is_available():
            return False
        
        try:
            # Create embedding for content
            embedding = self.create_embedding(doc['content'])
            if not embedding:
                return False
            
            # Create unique ID
            doc_id = doc.get('faq_id', str(uuid.uuid4()))
            
            # Prepare metadata (Pinecone has size limits)
            metadata = {
                'type': doc.get('type', ''),
                'category': doc.get('category', ''),
                'source': doc.get('source', ''),
                'content': doc['content'][:1000]  # Limit content size in metadata
            }
            
            # Add specific fields based on document type
            if 'product_count' in doc:
                metadata['product_count'] = doc['product_count']
            
            # Upsert to Pinecone with v6.x API
            self.index.upsert(vectors=[{
                'id': doc_id,
                'values': embedding,
                'metadata': metadata
            }])
            return True
            
        except Exception as e:
            print(f"Error upserting document: {e}")
            return False
    
    def upsert_documents(self, docs: List[Dict[str, Any]]) -> int:
        """Upsert multiple support documents"""
        if not self.is_available():
            return 0
        
        successful_upserts = 0
        vectors_to_upsert = []
        
        for doc in docs:
            try:
                # Create embedding
                embedding = self.create_embedding(doc['content'])
                if not embedding:
                    continue
                
                # Create unique ID
                doc_id = doc.get('faq_id', str(uuid.uuid4()))
                
                # Prepare metadata
                metadata = {
                    'type': doc.get('type', ''),
                    'category': doc.get('category', ''),
                    'source': doc.get('source', ''),
                    'content': doc['content'][:1000]
                }
                
                if 'product_count' in doc:
                    metadata['product_count'] = doc['product_count']
                
                vectors_to_upsert.append({
                    'id': doc_id,
                    'values': embedding,
                    'metadata': metadata
                })
                
            except Exception as e:
                print(f"Error preparing document for upsert: {e}")
                continue
        
        # Batch upsert with v6.x API
        try:
            if vectors_to_upsert:
                self.index.upsert(vectors=vectors_to_upsert)
                successful_upserts = len(vectors_to_upsert)
                print(f"✅ Upserted {successful_upserts} support documents to Pinecone")
        except Exception as e:
            print(f"Error during batch upsert: {e}")
        
        return successful_upserts
    
    def search_support(self, query: str, top_k: int = 3, filter_dict: Dict = None) -> List[Dict[str, Any]]:
        """Search for relevant support documents"""
        if not self.is_available():
            return []
        
        try:
            # Create query embedding
            query_embedding = self.create_embedding(query)
            if not query_embedding:
                return []
            
            # Search Pinecone with v6.x API
            results = self.index.query(
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True,
                filter=filter_dict
            )
            
            # Format results
            support_docs = []
            for match in results.matches:
                doc = {
                    'content': match.metadata.get('content', ''),
                    'type': match.metadata.get('type', ''),
                    'category': match.metadata.get('category', ''),
                    'source': match.metadata.get('source', ''),
                    'score': float(match.score),
                    'id': match.id
                }
                
                if 'product_count' in match.metadata:
                    doc['product_count'] = match.metadata['product_count']
                
                support_docs.append(doc)
            
            return support_docs
            
        except Exception as e:
            print(f"Error searching support documents: {e}")
            return []
    
    def get_index_stats(self) -> Dict[str, Any]:
        """Get Pinecone index statistics"""
        if not self.is_available():
            return {"status": "unavailable"}
        
        try:
            stats = self.index.describe_index_stats()
            return {
                "status": "connected",
                "total_vector_count": stats.total_vector_count,
                "dimension": stats.dimension
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def clear_index(self) -> bool:
        """Clear all vectors from the index (use with caution)"""
        if not self.is_available():
            return False
        
        try:
            self.index.delete(delete_all=True)
            print("✅ Cleared Pinecone support index")
            return True
        except Exception as e:
            print(f"Error clearing index: {e}")
            return False 