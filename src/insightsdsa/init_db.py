"""Create all tables from ORM models."""
from .db import engine
from .models import Base

def init_schema():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    init_schema()
    print("Schema created/verified successfully.")
