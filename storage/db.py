import psycopg2
from psycopg2.extras import execute_values
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from typing import List, Dict, Optional
from datetime import datetime

from config.settings import settings
from observability.logger import logger

class VectorDB:
    """PostgreSQL + pgvector database operations"""
    
    def __init__(self):
        self.db_url = settings.database.url
        self._ensure_schema()
    
    def _get_connection(self):
        """Get database connection"""
        conn = psycopg2.connect(self.db_url)
        return conn
    
    def _ensure_schema(self):
        """Create tables and indexes if they don't exist"""
        with logger.operation("ensure_schema"):
            conn = self._get_connection()
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cur = conn.cursor()
            
            try:
                # Enable pgvector extension
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                
                # Create documents table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS documents (
                        id SERIAL PRIMARY KEY,
                        chunk_id TEXT UNIQUE NOT NULL,
                        repo_name TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        file_type TEXT,
                        text TEXT NOT NULL,
                        embedding vector(1536),
                        commit_hash TEXT,
                        commit_date TIMESTAMP,
                        author TEXT,
                        github_url TEXT,
                        last_indexed TIMESTAMP DEFAULT NOW(),
                        metadata JSONB,
                        created_at TIMESTAMP DEFAULT NOW()
                    );
                """)
                
                # Create indexes for fast retrieval
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_documents_repo 
                    ON documents(repo_name);
                """)
                
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_documents_file_path 
                    ON documents(file_path);
                """)
                
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_documents_file_type 
                    ON documents(file_type);
                """)
                
                # Vector similarity index (HNSW for fast approximate search)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_documents_embedding_hnsw 
                    ON documents USING hnsw (embedding vector_cosine_ops);
                """)
                
                # Full-text search index
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_documents_text_fts 
                    ON documents USING gin(to_tsvector('english', text));
                """)
                
                logger.info("Database schema initialized")
                
            except Exception as e:
                logger.error("Failed to create schema", error=str(e))
                raise
            finally:
                cur.close()
                conn.close()
    
    def upsert_chunks(self, chunks: List[Dict]) -> int:
        """
        Insert or update document chunks
        
        Args:
            chunks: List of chunk dictionaries with keys:
                - chunk_id, repo_name, file_path, text, embedding, etc.
        
        Returns:
            Number of chunks inserted/updated
        """
        if not chunks:
            return 0
        
        with logger.operation("upsert_chunks", count=len(chunks)):
            conn = self._get_connection()
            cur = conn.cursor()
            
            try:
                # Prepare data for insertion
                values = [
                    (
                        chunk['chunk_id'],
                        chunk['repo_name'],
                        chunk['file_path'],
                        chunk.get('file_type', 'unknown'),
                        chunk['text'],
                        chunk['embedding'],
                        chunk.get('commit_hash'),
                        chunk.get('commit_date'),
                        chunk.get('author'),
                        chunk.get('github_url'),
                        datetime.utcnow(),
                        None  # metadata (can be extended)
                    )
                    for chunk in chunks
                ]
                
                # Use ON CONFLICT to update existing chunks
                execute_values(
                    cur,
                    """
                    INSERT INTO documents 
                    (chunk_id, repo_name, file_path, file_type, text, embedding, 
                     commit_hash, commit_date, author, github_url, last_indexed, metadata)
                    VALUES %s
                    ON CONFLICT (chunk_id) DO UPDATE SET
                        text = EXCLUDED.text,
                        embedding = EXCLUDED.embedding,
                        commit_hash = EXCLUDED.commit_hash,
                        commit_date = EXCLUDED.commit_date,
                        author = EXCLUDED.author,
                        last_indexed = EXCLUDED.last_indexed
                    """,
                    values
                )
                
                conn.commit()
                logger.info("Chunks upserted", count=len(chunks))
                return len(chunks)
                
            except Exception as e:
                conn.rollback()
                logger.error("Failed to upsert chunks", error=str(e))
                raise
            finally:
                cur.close()
                conn.close()
    
    def semantic_search(
        self,
        query_embedding: List[float],
        limit: int = 10,
        repo_name: Optional[str] = None,
        file_type: Optional[str] = None,
        similarity_threshold: float = 0.7
    ) -> List[Dict]:
        """
        Semantic search using vector similarity
        
        Args:
            query_embedding: Query vector (1536 dimensions)
            limit: Maximum number of results
            repo_name: Optional repository filter
            file_type: Optional file type filter
            similarity_threshold: Minimum cosine similarity (0-1)
        
        Returns:
            List of matching documents with similarity scores
        """
        conn = self._get_connection()
        cur = conn.cursor()
        
        try:
            # Convert embedding list to string format for pgvector
            embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
            
            # Build WHERE clause with optional filters
            where_clauses = ["1 - (embedding <=> %s::vector) >= %s"]
            params = [embedding_str, similarity_threshold]
            
            if repo_name:
                where_clauses.append("repo_name = %s")
                params.append(repo_name)
            
            if file_type:
                where_clauses.append("file_type = %s")
                params.append(file_type)
            
            where_sql = " AND ".join(where_clauses)
            
            # Add embedding_str and limit to params
            query_params = [embedding_str] + params + [embedding_str, limit]
            
            cur.execute(f"""
                SELECT 
                    chunk_id,
                    repo_name,
                    file_path,
                    file_type,
                    text,
                    commit_hash,
                    commit_date,
                    author,
                    github_url,
                    1 - (embedding <=> %s::vector) as similarity
                FROM documents
                WHERE {where_sql}
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """, query_params)
            
            results = []
            for row in cur.fetchall():
                results.append({
                    'chunk_id': row[0],
                    'repo_name': row[1],
                    'file_path': row[2],
                    'file_type': row[3],
                    'text': row[4],
                    'commit_hash': row[5],
                    'commit_date': row[6].isoformat() if row[6] else None,
                    'author': row[7],
                    'github_url': row[8],
                    'similarity': float(row[9])
                })
            
            return results
            
        finally:
            cur.close()
            conn.close()
    
    def keyword_search(
        self,
        query: str,
        limit: int = 5,
        repo_name: Optional[str] = None
    ) -> List[Dict]:
        """
        Keyword search using PostgreSQL full-text search
        
        Args:
            query: Search query
            limit: Maximum number of results
            repo_name: Optional repository filter
        
        Returns:
            List of matching documents with relevance scores
        """
        conn = self._get_connection()
        cur = conn.cursor()
        
        try:
            where_clauses = ["to_tsvector('english', text) @@ plainto_tsquery('english', %s)"]
            params = [query]
            
            if repo_name:
                where_clauses.append("repo_name = %s")
                params.append(repo_name)
            
            where_sql = " AND ".join(where_clauses)
            params.append(limit)
            
            cur.execute(f"""
                SELECT 
                    chunk_id,
                    repo_name,
                    file_path,
                    file_type,
                    text,
                    commit_hash,
                    commit_date,
                    author,
                    github_url,
                    ts_rank(to_tsvector('english', text), plainto_tsquery('english', %s)) as rank
                FROM documents
                WHERE {where_sql}
                ORDER BY rank DESC
                LIMIT %s
            """, [query] + params)
            
            results = []
            for row in cur.fetchall():
                results.append({
                    'chunk_id': row[0],
                    'repo_name': row[1],
                    'file_path': row[2],
                    'file_type': row[3],
                    'text': row[4],
                    'commit_hash': row[5],
                    'commit_date': row[6].isoformat() if row[6] else None,
                    'author': row[7],
                    'github_url': row[8],
                    'rank': float(row[9])
                })
            
            return results
            
        finally:
            cur.close()
            conn.close()
    
    def get_stats(self) -> Dict:
        """Get database statistics"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                SELECT 
                    COUNT(*) as total_chunks,
                    COUNT(DISTINCT repo_name) as total_repos,
                    COUNT(DISTINCT file_path) as total_files,
                    MAX(last_indexed) as last_sync
                FROM documents
            """)
            
            row = cur.fetchone()
            return {
                'total_chunks': row[0],
                'total_repos': row[1],
                'total_files': row[2],
                'last_sync': row[3].isoformat() if row[3] else None
            }
            
        finally:
            cur.close()
            conn.close()
    
    def delete_repo(self, repo_name: str) -> int:
        """Delete all chunks from a repository"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("DELETE FROM documents WHERE repo_name = %s", (repo_name,))
            deleted = cur.rowcount
            conn.commit()
            logger.info("Deleted repo chunks", repo=repo_name, count=deleted)
            return deleted
            
        except Exception as e:
            conn.rollback()
            logger.error("Failed to delete repo", repo=repo_name, error=str(e))
            raise
        finally:
            cur.close()
            conn.close()