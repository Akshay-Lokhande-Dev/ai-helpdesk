from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL=os.getenv("DATABASE_URL")
engine=create_engine(DATABASE_URL)

print(f"engine ban gaya {engine}")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set check your .env file")
