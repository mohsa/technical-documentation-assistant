from typing import List
import tiktoken

from config.settings import settings

class TextChunker:
    """Chunks text into token-sized pieces"""
    
    def __init__(self):
        self.chunk_size = settings.chunking.chunk_size
        self.chunk_overlap = settings.chunking.chunk_overlap
        self.encoding = tiktoken.get_encoding("cl100k_base")
    
    def chunk_text(self, text: str) -> List[str]:
        """
        Chunk text into overlapping pieces
        
        Args:
            text: Text to chunk
        
        Returns:
            List of text chunks
        """
        tokens = self.encoding.encode(text)
        
        if len(tokens) <= self.chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(tokens):
            end = start + self.chunk_size
            chunk_tokens = tokens[start:end]
            chunk_text = self.encoding.decode(chunk_tokens)
            chunks.append(chunk_text)
            
            start = end - self.chunk_overlap
        
        return chunks