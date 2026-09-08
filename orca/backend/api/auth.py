"""Supabase JWT Authentication Dependency for ORCA Marine Intelligence FastAPI Backend.

Supports:
1. Validating incoming Bearer tokens signed by Supabase Auth
2. Extracting user identity, roles, and metadata
3. Seamless fallback when operating in local offline/guest mode
"""

import logging
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from fastapi import Header, HTTPException, status, Depends

try:
    import jwt
except ImportError:
    jwt = None

from config.settings import Settings

logger = logging.getLogger(__name__)
settings = Settings()


class AuthenticatedUser(BaseModel):
    """Authenticated Supabase user entity."""
    id: str = Field(..., description="Supabase UUID")
    email: Optional[str] = Field(None, description="User email address")
    role: str = Field("FISHERMAN", description="User marine role")
    vessel_class: Optional[str] = Field(None, description="Registered boat/vessel category")
    user_metadata: Dict[str, Any] = Field(default_factory=dict)
    app_metadata: Dict[str, Any] = Field(default_factory=dict)


def decode_supabase_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes and optionally verifies a Supabase JWT token."""
    if not token or not jwt:
        return None

    secret = settings.SUPABASE_JWT_SECRET

    try:
        if secret:
            # Full cryptographically verified decode
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                audience="authenticated",
                options={"verify_exp": True},
            )
            return payload
        else:
            # Development decode without signature check if secret is not set
            payload = jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": True},
            )
            return payload
    except jwt.ExpiredSignatureError:
        logger.warning("[ORCA Auth] Token signature has expired")
        return None
    except Exception as e:
        logger.warning(f"[ORCA Auth] Token decoding failed: {e}")
        return None


async def get_current_user_optional(
    authorization: Optional[str] = Header(None, description="Bearer <token>")
) -> Optional[AuthenticatedUser]:
    """FastAPI dependency for endpoints that accept authenticated or anonymous/guest access."""
    if not authorization:
        return None

    parts = authorization.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    token = parts[1]
    payload = decode_supabase_token(token)
    if not payload or "sub" not in payload:
        return None

    user_meta = payload.get("user_metadata", {})
    app_meta = payload.get("app_metadata", {})

    return AuthenticatedUser(
        id=payload["sub"],
        email=payload.get("email"),
        role=user_meta.get("user_role") or app_meta.get("role") or "FISHERMAN",
        vessel_class=user_meta.get("vessel_class"),
        user_metadata=user_meta,
        app_metadata=app_meta,
    )


async def get_current_user(
    user: Optional[AuthenticatedUser] = Depends(get_current_user_optional),
) -> AuthenticatedUser:
    """FastAPI dependency requiring strict authentication."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid Supabase authorization token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
