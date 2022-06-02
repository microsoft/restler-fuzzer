from fastapi import Depends, HTTPException, APIRouter
from sqlmodel import Session, select

from db import get_session

router = APIRouter(prefix="/api/doc")


@router.get("")
async def root():
    return {"message": "this is the docs"}
