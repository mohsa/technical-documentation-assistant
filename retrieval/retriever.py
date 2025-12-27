from typing import List, Dict, Optional
from collections import defaultdict

from storage.db import VectorDB
from retrieval.embedder import Embedder
from observability.logger import logger

class HybridRetriever:
    """Combines semantic and keyword search for better results"""
    
    def __init__(self):
        self.db = VectorDB()
        self.embedder = Embedder()
    
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        semantic_weight: float = 0.7,
        repo_name: Optional[str] = None,
        file_type: Optional[str] = None
    ) -> List[Dict]:
        """
        Hybrid retrieval: combines semantic + keyword search
        
        Args:
            query: Search query
            top_k: Number of results to return
            semantic_weight: Weight for semantic search (0-1)
            repo_name: Optional repository filter
            file_type: Optional file type filter
        
        Returns:
            List of retrieved documents with scores
        """
        with logger.operation("hybrid_retrieve", query=query[:100], top_k=top_k):
            
            # Generate query embedding
            query_embedding = self.embedder.embed_text(query)
            
            # Semantic search
            semantic_results = self.db.semantic_search(
                query_embedding=query_embedding,
                limit=top_k * 2,  # Get more for reranking
                repo_name=repo_name,
                file_type=file_type,
                similarity_threshold=0.5
            )
            
            logger.info("Semantic search complete", results=len(semantic_results))
            
            # Keyword search
            keyword_results = self.db.keyword_search(
                query=query,
                limit=top_k,
                repo_name=repo_name
            )
            
            logger.info("Keyword search complete", results=len(keyword_results))
            
            # Combine and rerank
            combined = self._rerank(
                semantic_results,
                keyword_results,
                semantic_weight=semantic_weight,
                top_k=top_k
            )
            
            logger.info("Retrieval complete", final_count=len(combined))
            
            return combined
    
    def _rerank(
        self,
        semantic_results: List[Dict],
        keyword_results: List[Dict],
        semantic_weight: float,
        top_k: int
    ) -> List[Dict]:
        """
        Combine and rerank results from semantic and keyword search
        
        Uses reciprocal rank fusion (RRF) for combining rankings
        """
        keyword_weight = 1.0 - semantic_weight
        k = 60  # RRF constant
        
        # Build chunk_id -> document map
        all_docs = {}
        for doc in semantic_results:
            all_docs[doc['chunk_id']] = doc
        for doc in keyword_results:
            if doc['chunk_id'] not in all_docs:
                all_docs[doc['chunk_id']] = doc
        
        # Calculate RRF scores
        scores = defaultdict(float)
        
        # Add semantic scores
        for rank, doc in enumerate(semantic_results, 1):
            chunk_id = doc['chunk_id']
            scores[chunk_id] += semantic_weight * (1.0 / (k + rank))
        
        # Add keyword scores
        for rank, doc in enumerate(keyword_results, 1):
            chunk_id = doc['chunk_id']
            scores[chunk_id] += keyword_weight * (1.0 / (k + rank))
        
        # Sort by combined score
        ranked_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        
        # Build final results
        results = []
        for chunk_id in ranked_ids[:top_k]:
            doc = all_docs[chunk_id].copy()
            doc['combined_score'] = scores[chunk_id]
            results.append(doc)
        
        return results
    
    def retrieve_by_file(
        self,
        file_path: str,
        repo_name: Optional[str] = None
    ) -> List[Dict]:
        """
        Retrieve all chunks from a specific file
        
        Args:
            file_path: File path to retrieve
            repo_name: Repository name
        
        Returns:
            List of chunks from the file
        """
        # Use keyword search with file path as query
        # This is a simple implementation; could be optimized with direct DB query
        results = self.db.keyword_search(
            query=file_path,
            limit=100,
            repo_name=repo_name
        )
        
        # Filter to exact file path match
        filtered = [r for r in results if r['file_path'] == file_path]
        
        return filtered