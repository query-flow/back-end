import hashlib
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
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
