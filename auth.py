# QuantumLeap - Auth (JWT + identity scope for ICCP)
from datetime import datetime, timedelta
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select

from config import get_settings
from database.database import async_session
from database.models import Person
from iccp import IdentityScope

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login", auto_error=False)
bearer = HTTPBearer(auto_error=False)

ALGORITHM = "HS256"
ACCESS_EXPIRE_MINUTES = 60
# Bcrypt limit: password must be <= 72 bytes
MAX_PASSWORD_BYTES = 72


def _truncate_password(password: str) -> str:
    """Bcrypt accepts max 72 bytes; truncate to avoid ValueError."""
    if not password:
        return password
    enc = password.encode("utf-8")
    if len(enc) <= MAX_PASSWORD_BYTES:
        return password
    return enc[:MAX_PASSWORD_BYTES].decode("utf-8", errors="ignore")


def get_secret():
    return get_settings().secret_key


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(_truncate_password(plain), hashed)


def hash_password(plain: str) -> str:
    return pwd_context.hash(_truncate_password(plain))


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, get_secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, get_secret(), algorithms=[ALGORITHM])
    except JWTError:
        return None


async def get_current_user_from_token(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict | None:
    if not credentials:
        return None
    payload = decode_token(credentials.credentials)
    if not payload or "sub" not in payload or "role" not in payload:
        return None
    return {"user_id": payload["sub"], "username": payload.get("username"), "role": payload["role"]}


async def require_auth(request: Request, user: dict | None = Depends(get_current_user_from_token)) -> IdentityScope:
    """Set request.state.identity_scope and return it; 401 if not authenticated."""
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    scope = IdentityScope(
        user_id=user["user_id"],
        role=user["role"],
        clearance="FERPA-Authorized" if user["role"] in ("admin", "teacher") else "",
        session_id=request.headers.get("X-Session-ID"),
    )
    request.state.identity_scope = scope
    return scope
