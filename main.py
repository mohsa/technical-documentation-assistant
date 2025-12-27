#!/usr/bin/env python3
import sys

from config.settings import settings
from ingestion.indexer import DocumentIndexer
from orchestration.orchestrator import LLMOrchestrator
from storage.db import VectorDB
from observability.logger import logger
from observability.metrics import metrics_collector

def index_repos():
    """Index all configured GitHub repos"""
    logger.info("Starting repository indexing")
    
    indexer = DocumentIndexer()
    
    for repo in settings.github.repos:
        try:
            metrics = indexer.index_repo(repo)
            logger.info(
                f"Indexing completed for {repo}",
                files=metrics.files_processed,
                chunks=metrics.chunks_created
            )
        except Exception as e:
            logger.error(f"Failed to index {repo}", error=str(e))
    
    # Print summary
    db = VectorDB()
    stats = db.get_stats()
    summary = metrics_collector.get_summary()
    
    print("\n=== Indexing Summary ===")
    print(f"Total repos: {stats['total_repos']}")
    print(f"Total files: {stats['total_files']}")
    print(f"Total chunks: {stats['total_chunks']}")
    print(f"Last sync: {stats['last_sync']}")
    print(f"\n=== Metrics ===")
    for key, value in summary.items():
        print(f"{key}: {value}")

def query_docs(question: str):
    """Query documentation with real retrieval"""
    orchestrator = LLMOrchestrator()
    
    result = orchestrator.query(question)
    
    print("\n" + "="*60)
    print("RESPONSE")
    print("="*60)
    print(result["response"])
    
    print("\n" + "="*60)
    print("CITATIONS")
    print("="*60)
    if result["citations"]:
        for citation in result["citations"]:
            print(f"  • {citation}")
    else:
        print("  (No citations)")
    
    print("\n" + "="*60)
    print("VALIDATION")
    print("="*60)
    validation = result["validation"]
    print(f"  Valid: {validation['is_valid']}")
    if validation['errors']:
        print(f"  Errors: {', '.join(validation['errors'])}")
    if validation['warnings']:
        print(f"  Warnings:")
        for warning in validation['warnings']:
            print(f"    - {warning}")
    
    print("\n" + "="*60)
    print("METRICS")
    print("="*60)
    metrics = result["metrics"]
    print(f"  Duration: {metrics.get('duration_ms', 0)}ms")
    print(f"  Tokens: {metrics.get('tokens_used', 0)}")
    print(f"  Cost: ${metrics.get('cost_usd', 0):.4f}")
    print(f"  Chunks retrieved: {metrics.get('chunks_retrieved', 0)}")

def show_stats():
    """Show database statistics"""
    db = VectorDB()
    stats = db.get_stats()
    
    print("\n=== Database Statistics ===")
    print(f"Total chunks: {stats['total_chunks']}")
    print(f"Total repos: {stats['total_repos']}")
    print(f"Total files: {stats['total_files']}")
    print(f"Last sync: {stats['last_sync']}")

def main():
    """Main CLI entry point"""
    try:
        settings.validate_required()
    except ValueError as e:
        print(f"Configuration error: {e}")
        print("Please check your .env file")
        sys.exit(1)
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python main.py index                   - Index GitHub repos")
        print("  python main.py query 'your question'   - Query documentation")
        print("  python main.py stats                   - Show database stats")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "index":
        index_repos()
    elif command == "query":
        if len(sys.argv) < 3:
            print("Please provide a question")
            sys.exit(1)
        query_docs(sys.argv[2])
    elif command == "stats":
        show_stats()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()