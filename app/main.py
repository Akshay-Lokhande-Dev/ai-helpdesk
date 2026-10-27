from fastapi import FastAPI,Depends
from app.db import get_db
from sqlalchemy.orm import Session
from sqlalchemy import text,select
from app.schemas import TicketOut
from app import models
from app.routers import tickets
from app.routers import users



app=FastAPI(redirect_slashes=False)
app.include_router(tickets.router)
app.include_router(users.router)

@app.get("/health")
def health_check():
    return {"status":"ok"}

@app.get("/db-check")
def db_check(db: Session  = Depends(get_db)):

    result = db.execute(text("select 1"))

    return result



    