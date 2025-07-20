from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from decouple import config

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="assistants/login")  # or your login endpoint

SECRET_KEY = config("JWT_SECRET")
ALGORITHM = config("JWT_ALGORITHM")

class TokenData(BaseModel):
    id: str
    role: str

def get_current_assistant(token: str = Depends(oauth2_scheme)) -> TokenData:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        role: str = payload.get("role")
        if role != "assistant":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only assistants are allowed"
            )
        return TokenData(id=payload.get("id"), role=role)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
