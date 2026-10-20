from fastapi import FastAPI,Depends
from app.db import get_db
from sqlalchemy.orm import Session
from sqlalchemy import text


app=FastAPI()

@app.get("/health")
def health_check():
    return {"status":"ok"}

@app.get("/db-check")
def db_check(db: Session  = Depends(get_db)):

    result = db.execute(text("select 1"))

    return result

