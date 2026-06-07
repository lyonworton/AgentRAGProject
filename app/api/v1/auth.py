from fastapi import APIRouter,Depends,HTTPException,status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime,timezone
from app.core.di import get_db
from app.core.security import hash_password,verify_password,create_access_token,generate_api_key
from app.api.deps import get_current_user
from app.domain.user import User
router=APIRouter(prefix="/auth",tags=["auth"])
class RegisterRequest(BaseModel):username:str;email:str;password:str
class LoginRequest(BaseModel):username:str;password:str
class TokenResponse(BaseModel):access_token:str;token_type:str="bearer";user:dict
class APIKeyResponse(BaseModel):api_key:str
@router.post("/register",status_code=201)
async def register(req:RegisterRequest,db:AsyncSession=Depends(get_db)):
 e=await db.execute(select(User).where(User.username==req.username))
 if e.scalar_one_or_none():raise HTTPException(status_code=status.HTTP_409_CONFLICT,detail="Username taken")
 u=User(username=req.username,email=req.email,password_hash=hash_password(req.password))
 db.add(u);await db.flush()
 return{"id":u.id,"username":u.username}
@router.post("/login",response_model=TokenResponse)
async def login(req:LoginRequest,db:AsyncSession=Depends(get_db)):
 r=await db.execute(select(User).where(User.username==req.username))
 u=r.scalar_one_or_none()
 if not u or not verify_password(req.password,u.password_hash):raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid credentials")
 u.last_login_at=datetime.now(timezone.utc);await db.flush()
 return TokenResponse(access_token=create_access_token(u.id),user={"id":u.id,"username":u.username})
@router.post("/api-key",response_model=APIKeyResponse)
async def create_api_key(user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 raw,kh=generate_api_key();user.api_key_hash=kh;await db.flush()
 return APIKeyResponse(api_key=raw)
