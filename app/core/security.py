import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from jose import JWTError, jwt
import bcrypt

from app.core.config import settings

# Initialize Fernet cipher
fernet = Fernet(settings.FERNET_KEY_B64)


def encrypt_str(s: str) -> str:
    """Encrypt a string using Fernet"""
    return fernet.encrypt(s.encode()).decode()


def decrypt_str(s: str) -> str:
    """Decrypt a string using Fernet"""
    try:
        return fernet.decrypt(s.encode()).decode()
    except InvalidToken as e:
        raise HTTPException(
            status_code=400,
            detail="Não foi possível decifrar a senha armazenada."
        ) from e


def sha256_hex(s: str) -> str:
    """Generate SHA256 hash of a string"""
    return hashlib.sha256(s.encode()).hexdigest()


# ========== JWT & Password Hashing ==========

# JWT configuration
SECRET_KEY = getattr(settings, "JWT_SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
REFRESH_TOKEN_EXPIRE_DAYS = 30


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Note: bcrypt has a 72-byte limit, so we truncate longer passwords.

    Args:
        password: Plain text password

    Returns:
        Hashed password (string)
    """
    # bcrypt has a 72-byte limit
    password_bytes = password.encode('utf-8')[:72]
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to compare against

    Returns:
        True if password matches, False otherwise
    """
    # bcrypt has a 72-byte limit, truncate to match hash_password behavior
    password_bytes = plain_password.encode('utf-8')[:72]
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    Args:
        data: Data to encode in the token (typically {"sub": user_id})
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """
    Create a JWT refresh token (longer expiration).

    Args:
        data: Data to encode in the token

    Returns:
        Encoded JWT refresh token
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    })

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT token.

    Args:
        token: JWT token to decode

    Returns:
        Decoded token payload

    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=401,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"}
        ) from e


def generate_invite_token() -> str:
    """
    Generate a secure random token for user invitations.

    Returns:
        32-character hexadecimal token
    """
    return secrets.token_hex(32)
