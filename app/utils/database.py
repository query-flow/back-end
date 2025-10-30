from typing import Optional, Dict
from urllib.parse import urlencode, quote
from sqlalchemy.engine import make_url
from fastapi import HTTPException


def parse_database_url(url_str: str) -> Dict:
    """
    Parse a SQLAlchemy database URL into components
    """
    try:
        u = make_url(url_str)
    except Exception:
        raise HTTPException(status_code=400, detail="database_url inválida.")

    if not u.database:
        raise HTTPException(
            status_code=400,
            detail="A database_url deve incluir um DB/schema (ex.: ...:3306/sakila?charset=utf8mb4)."
        )

    return {
        "driver": u.drivername,
        "host": u.host or "127.0.0.1",
        "port": int(u.port or 3306),
        "username": u.username or "",
        "password": u.password or "",
        "database_name": u.database,
        "options": dict(u.query or {}),
    }


def build_sqlalchemy_url(
    driver: str,
    host: str,
    port: int,
    username: str,
    password_plain: str,
    database: str,
    options: Optional[Dict] = None
) -> str:
    """
    Build a SQLAlchemy database URL from components
    """
    pwd_enc = quote(password_plain, safe="")
    qs = "?" + urlencode(options or {}) if options else ""
    return f"{driver}://{username}:{pwd_enc}@{host}:{port}/{database}{qs}"
