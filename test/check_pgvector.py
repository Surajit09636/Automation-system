import os
import psycopg
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise ValueError("DATABASE_URL is not set in .env")

# Normalize URL for psycopg3 (psycopg handles postgresql:// directly)
print(f"Connecting to database...")

try:
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            # 1. Check PostgreSQL Connection & Version
            cur.execute("SELECT version();")
            pg_version = cur.fetchone()[0]
            print(" PostgreSQL connected successfully!")
            print(f"   Version: {pg_version.split(',')[0]}\n")

            # 2. Check if pgvector extension is installed
            cur.execute("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';")
            ext = cur.fetchone()

            if ext:
                print(f" pgvector extension is ACTIVE (v{ext[1]}).\n")
            else:
                print("[Warning] pgvector extension is NOT enabled yet. Checking availability...")
                cur.execute("SELECT name, default_version FROM pg_available_extensions WHERE name = 'vector';")
                available = cur.fetchone()

                if available:
                    print(f"   Found available pgvector (v{available[1]}). Enabling now...")
                    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                    conn.commit()
                    print(" pgvector extension has been successfully ENABLED!\n")
                else:
                    raise RuntimeError(
                        "pgvector binary is not installed on this PostgreSQL server.\n"
                        "Please install pgvector for your PostgreSQL instance first."
                    )

            # 3. Test Vector Operations (L2 distance & Cosine similarity)
            print(" Testing vector calculations...")
            cur.execute("SELECT '[1, 2, 3]'::vector <-> '[4, 5, 6]'::vector AS l2_dist;")
            l2_dist = cur.fetchone()[0]
            print(f"   L2 Distance ([1,2,3] <-> [4,5,6]): {l2_dist:.4f}")

            cur.execute("SELECT '[1, 0, 0]'::vector <=> '[0, 1, 0]'::vector AS cosine_dist;")
            cos_dist = cur.fetchone()[0]
            print(f"   Cosine Distance ([1,0,0] <=> [0,1,0]): {cos_dist:.4f}\n")

            # 4. Test Table Creation & Querying
            print(" Testing temporary vector table and search...")
            cur.execute("""
                CREATE TEMP TABLE test_vectors (
                    id SERIAL PRIMARY KEY,
                    content TEXT,
                    embedding vector(3)
                );
            """)
            cur.execute("""
                INSERT INTO test_vectors (content, embedding) VALUES
                    ('Document A', '[1.0, 0.0, 0.0]'),
                    ('Document B', '[0.0, 1.0, 0.0]'),
                    ('Document C', '[0.9, 0.1, 0.0]');
            """)

            # Query nearest neighbor to [1.0, 0.0, 0.0]
            cur.execute("""
                SELECT content, embedding <-> '[1.0, 0.0, 0.0]' AS distance
                FROM test_vectors
                ORDER BY distance
                LIMIT 2;
            """)
            results = cur.fetchall()
            print("   Nearest neighbor query results:")
            for item in results:
                print(f"     - {item[0]}: distance = {item[1]:.4f}")

    print("\n SUCCESS: pgvector is fully accessible and operational!")

except Exception as err:
    print(f"\n[Failed] {type(err).__name__}")
    print(f"Details: {err}")
