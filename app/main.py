from fastapi import FastAPI,Depends
from app.db import get_db
from sqlalchemy.orm import Session
from sqlalchemy import text,select
from app.schemas import TicketOut
from app import models



app=FastAPI()

@app.get("/health")
def health_check():
    return {"status":"ok"}

@app.get("/db-check")
def db_check(db: Session  = Depends(get_db)):

    result = db.execute(text("select 1"))

    return result

@app.get("/tickets",response_model=list[TicketOut])
def get_tickets(db:Session=Depends(get_db)):
    
    tickets = db.scalars(select(models.Ticket).limit(50)).all()

    return tickets

    