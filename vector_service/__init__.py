"""
Common utilities and shared components
"""

from .pinecone_client import (
    PineconeClient,
    create_pinecone_client,
    pinecone_products_client,
    pinecone_support_client
)

__all__ = [
    'PineconeClient',
    'create_pinecone_client',
    'pinecone_products_client',
    'pinecone_support_client'
]
