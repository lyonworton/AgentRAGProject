from fastapi import Depends,HTTPException,status
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.di import get_db
from app.core.security import decode_access_token,hash_api_key
from app.domain.user import User
bearer_scheme=HTTPBearer(auto_error=False)
async def get_current_user(credentials:HTTPAuthorizationCredentials|None=Depends(bearer_scheme),db:AsyncSession=Depends(get_db))->User:
 if not credentials:raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail='Missing token')
 t=credentials.credentials
 try:
  p=decode_access_token(t)
  r=await db.execute(select(User).where(User.id==p.get('sub')))
  u=r.scalar_one_or_none()
  if u and u.is_active:return u
 except:pass
 kh=hash_api_key(t)
 r=await db.execute(select(User).where(User.api_key_hash==kh))
 u=r.scalar_one_or_none()
 if u and u.is_active:return u
 raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail='Invalid credentials')
