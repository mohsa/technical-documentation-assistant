from pathlib import Path
from typing import List, Dict
import hashlib

from ingestion.github_sync import GitHubSyncer
from ingestion.parser import ContentParser
from ingestion.chunker import TextChunker
from retrieval.embedder import Embedder
from storage.db import VectorDB
from observability.logger import logger
from observability.metrics import SyncMetrics, metrics_collector

class DocumentIndexer:
    """Indexes documents from GitHub into vector database"""
    
    def __init__(self):
        self.syncer = GitHubSyncer()
        self.parser = ContentParser()
        self.chunker = TextChunker()
        self.embedder = Embedder()
        self.db = VectorDB()
    
    def index_repo(self, repo: str) -> SyncMetrics:
        """
        Index a GitHub repository
        
        Args:
            repo: Repository in format "owner/repo"
        
        Returns:
            SyncMetrics with indexing results
        """
        with logger.operation("index_repo", repo=repo):
            # Step 1: Sync repository from GitHub
            metrics = self.syncer.sync_repo(repo)
            
            if metrics.errors:
                logger.error("Sync failed, skipping indexing", repo=repo)
                return metrics
            
            # Step 2: Get all files to process
            repo_path = self.syncer._get_repo_path(repo)
            files = self.syncer._get_files_to_process(repo_path)
            
            logger.info("Starting indexing", repo=repo, files=len(files))
            
            # Step 3: Process files in batches
            all_chunks = []
            
            for file_path in files:
                try:
                    chunks = self._process_file(repo, repo_path, file_path)
                    all_chunks.extend(chunks)
                    
                except Exception as e:
                    logger.error(
                        "Failed to process file",
                        repo=repo,
                        file=str(file_path.relative_to(repo_path)),
                        error=str(e)
                    )
                    metrics.errors.append(f"{file_path.name}: {str(e)}")
            
            # Step 4: Generate embeddings in batches
            if all_chunks:
                logger.info("Generating embeddings", count=len(all_chunks))
                
                texts = [chunk['text'] for chunk in all_chunks]
                embeddings = self.embedder.embed_batch(texts)
                
                # Add embeddings to chunks
                for chunk, embedding in zip(all_chunks, embeddings):
                    chunk['embedding'] = embedding
                
                # Step 5: Store in database
                logger.info("Storing chunks in database", count=len(all_chunks))
                stored_count = self.db.upsert_chunks(all_chunks)
                
                metrics.chunks_created = stored_count
                logger.info(
                    "Indexing complete",
                    repo=repo,
                    files=len(files),
                    chunks=stored_count
                )
            else:
                logger.warning("No chunks created", repo=repo)
            
            return metrics
    
    def _process_file(
        self,
        repo: str,
        repo_path: Path,
        file_path: Path
    ) -> List[Dict]:
        """
        Process a single file into chunks
        
        Args:
            repo: Repository name
            repo_path: Local repository path
            file_path: File to process
        
        Returns:
            List of chunk dictionaries
        """
        relative_path = file_path.relative_to(repo_path)
        
        # Parse file content
        content = self.parser.parse_file(file_path)
        if not content:
            return []
        
        # Get file metadata from git
        metadata = self.syncer.get_file_metadata(repo_path, file_path)
        
        # Chunk the content
        text_chunks = self.chunker.chunk_text(content)
        
        # Create chunk objects
        chunks = []
        for i, text in enumerate(text_chunks):
            # Generate unique chunk ID
            chunk_id = self._generate_chunk_id(repo, str(relative_path), i)
            
            # Build GitHub URL
            github_url = f"https://github.com/{repo}/blob/main/{relative_path}"
            
            chunk = {
                'chunk_id': chunk_id,
                'repo_name': repo,
                'file_path': str(relative_path).replace('\\', '/'),
                'file_type': file_path.suffix.lstrip('.'),
                'text': text,
                'commit_hash': metadata['commit_hash'],
                'commit_date': metadata['commit_date'],
                'author': metadata['author'],
                'github_url': github_url
            }
            
            chunks.append(chunk)
        
        return chunks
    
    def _generate_chunk_id(self, repo: str, file_path: str, chunk_index: int) -> str:
        """Generate unique chunk ID"""
        content = f"{repo}::{file_path}::{chunk_index}"
        return hashlib.md5(content.encode()).hexdigest()