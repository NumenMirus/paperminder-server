from fastapi import APIRouter, Depends, HTTPException
from authx import RequestToken
from src.config import auth

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.get('/token')
def login(username: str, password: str):
     if username == "admin" and password == "0000":
          access_token = auth.create_access_token(uid=username)
          refresh_token = auth.create_refresh_token(uid=username)
          return {"access_token": access_token, "refresh_token": refresh_token}
     raise HTTPException(401, detail={"message": "Invalid credentials"})

@router.get("/protected", dependencies=[Depends(auth.get_token_from_request)])
def get_protected(token: RequestToken = Depends()):
     try:
          auth.verify_token(token=token)
          return {"message": "Hello world !"}
     except Exception as e:
          raise HTTPException(401, detail={"message": str(e)}) from e