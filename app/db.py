from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()


def require_env(config_key):

    print(config_key)

    value = os.getenv(config_key)


    if not value:
        raise RuntimeError(f"{config_key} is not set check your .env file")
    
    return value

DATABASE_URL = require_env("DATABASE_URL")

engine = create_engine(DATABASE_URL)






