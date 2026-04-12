import os
from psycopg_pool import ConnectionPool
from dotenv import load_dotenv

load_dotenv()

DB_URI = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"

# 1. Initialize as None
_pool = None

def get_pool():
    global _pool
    # 2. Only create the pool if it doesn't exist for THIS worker
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=DB_URI,
            min_size=1,        # Keep this low on the free tier
            max_size=4,
            kwargs={"autocommit": False,"connect_timeout": 10}
        )
    return _pool

def getDBConnection():
    # 3. Always get the connection from the worker-specific pool
    return get_pool().connection()