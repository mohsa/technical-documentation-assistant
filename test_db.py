import os
from dotenv import load_dotenv
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

load_dotenv()

db_url = os.getenv("DATABASE_URL")
print(f"Testing connection to database...")

try:
    # Connect
    conn = psycopg2.connect(db_url)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    
    print(" Connected successfully!")
    
    # Check PostgreSQL version
    cur.execute("SELECT version();")
    version = cur.fetchone()[0]
    print(f" PostgreSQL version: {version.split(',')[0]}")
    
    # Check pgvector extension
    cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector';")
    result = cur.fetchone()
    if result:
        print(f" pgvector version: {result[0]}")
    else:
        print(" pgvector extension not found!")
        print("  Run: CREATE EXTENSION vector;")
    
    # Test creating a vector table
    cur.execute("""
        DROP TABLE IF EXISTS test_vectors;
        CREATE TABLE test_vectors (
            id SERIAL PRIMARY KEY,
            embedding vector(1536),
            text TEXT
        );
    """)
    print(" Created test table with vector column")
    
    # Test inserting a vector
    test_embedding = [0.1] * 1536  # 1536-dimensional vector
    cur.execute(
        "INSERT INTO test_vectors (embedding, text) VALUES (%s, %s)",
        (test_embedding, "test document")
    )
    print(" Inserted test vector")
    
    # Test querying vectors
    cur.execute("SELECT COUNT(*) FROM test_vectors;")
    count = cur.fetchone()[0]
    print(f" Queried vectors: {count} row(s)")
    
    # Clean up
    cur.execute("DROP TABLE test_vectors;")
    print(" Cleaned up test table")
    
    cur.close()
    conn.close()
    
    print("\n All tests passed! PostgreSQL + pgvector is ready.")
    
except Exception as e:
    print(f"\n Error: {e}")
    print("\nTroubleshooting tips:")
    print("1. Make sure PostgreSQL service is running")
    print("2. Check DATABASE_URL in .env is correct")
    print("3. Verify pgvector extension is installed: psql -U docs_user -d docs_assistant -c '\\dx'")