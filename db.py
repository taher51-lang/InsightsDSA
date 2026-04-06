import os
from psycopg_pool import ConnectionPool
from dotenv import load_dotenv
load_dotenv()
# Use your existing .env logic
DB_URI = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"

# The Pool lives here now
pool = ConnectionPool(
    conninfo=DB_URI,
    min_size=2,
    max_size=10,
    kwargs={"autocommit": False}
)

def getDBConnection():
    return pool.connection()