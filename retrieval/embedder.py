from typing import List, Union
import openai
import time

from config.settings import settings
from observability.logger import logger

class Embedder:
    """Generate embeddings using OpenAI API"""
    
    def __init__(self):
        self.client = openai.OpenAI(api_key=settings.llm.api_key)
        self.model = settings.llm.embedding_model
        self.batch_size = 100  # OpenAI allows up to 2048 texts per request
    
    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text
        
        Args:
            text: Text to embed
        
        Returns:
            1536-dimensional embedding vector
        """
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text
            )
            
            embedding = response.data[0].embedding
            return embedding
            
        except Exception as e:
            logger.error("Failed to generate embedding", error=str(e))
            raise
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts
        
        Args:
            texts: List of texts to embed
        
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        embeddings = []
        
        # Process in batches
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            
            with logger.operation("embed_batch", batch_size=len(batch)):
                try:
                    response = self.client.embeddings.create(
                        model=self.model,
                        input=batch
                    )
                    
                    batch_embeddings = [item.embedding for item in response.data]
                    embeddings.extend(batch_embeddings)
                    
                    logger.info(
                        "Generated embeddings",
                        count=len(batch),
                        total=len(embeddings)
                    )
                    
                    # Rate limiting - be nice to the API
                    if i + self.batch_size < len(texts):
                        time.sleep(0.1)
                    
                except Exception as e:
                    logger.error(
                        "Failed to generate batch embeddings",
                        batch_index=i,
                        error=str(e)
                    )
                    raise
        
        return embeddings