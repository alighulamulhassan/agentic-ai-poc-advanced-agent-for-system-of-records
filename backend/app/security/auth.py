"""
Authentication & Authorization middleware.

Provides:
  - API key auth (lightweight, for internal services)
  - JWT bearer token auth (for user-facing APIs)
  - Role-based access control (RBAC) for tool-level permissions

In production this integrates with AWS Cognito — swap the
JWT_SECRET and issuer to point at your Cognito User Pool.

Session for audience:
  - Knowledge fuel: explain JWT, OAuth2, Cognito flow
  - Lab: swap the hardcoded secret for Cognito JWKS endpoint validation
"""
import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Set
from functools import wraps

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config (swap these env vars with Secrets Manager in production)
# ---------------------------------------------------------------------------
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_MINUTES = int(os.getenv("JWT_EXPIRY_MINUTES", "60"))
VALID_API_KEYS: Set[str] = set(
    filter(None, os.getenv("API_KEYS", "dev-key-12345").split(","))
)

# FastAPI security schemes
_bearer_scheme = HTTPBearer(auto_error=False)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


# ---------------------------------------------------------------------------
# Role definitions — maps role → allowed tools
# ---------------------------------------------------------------------------
ROLE_PERMISSIONS: Dict[str, Set[str]] = {
    "readonly": {
        "lookup_order", "get_customer_info", "find_customer_by_email",
        "get_customer_order_history", "search_products", "search_documents",
    },
    "agent": {
        # readonly tools +
        "lookup_order", "get_customer_info", "find_customer_by_email",
        "get_customer_order_history", "search_products", "search_documents",
        # write tools
        "cancel_order", "process_refund", "update_order_status",
        "update_shipping_address", "apply_discount_code",
        "add_loyalty_points", "update_customer_profile",
        "expedite_order_shipping",
    },
    "supervisor": {
        # all tools
        "*",
    },
    "admin": {
        "*",
    },
}


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------
def create_access_token(
    subject: str,
    role: str = "agent",
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Create a signed JWT access token.

    Args:
        subject: User/service identifier (sub claim)
        role: One of readonly | agent | supervisor | admin
        extra_claims: Additional claims to embed (e.g. tenant_id)

    Returns:
        Signed JWT string
    """
    try:
        import jwt  # PyJWT
    except ImportError:
        logger.warning("PyJWT not installed — returning placeholder token")
        return f"dev-token-{subject}"

    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=JWT_EXPIRY_MINUTES),
        **(extra_claims or {}),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT. Raises HTTPException on failure."""
    try:
        import jwt
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------
async def get_current_user(
    bearer: Optional[HTTPAuthorizationCredentials] = Security(_bearer_scheme),
    api_key: Optional[str] = Security(_api_key_header),
) -> Dict[str, Any]:
    """
    FastAPI dependency — resolves the caller identity from either:
      1. Bearer JWT token  (Authorization: Bearer <token>)
      2. API key header    (X-API-Key: <key>)

    Returns a user context dict with: sub, role, permissions.

    TODO (Lab): Replace the JWT_SECRET validation with Cognito JWKS
    endpoint validation so tokens are issued by your Cognito User Pool.
    See: https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-using-tokens-verifying-a-jwt.html
    """
    # --- API key path (service-to-service) ---
    if api_key:
        if api_key not in VALID_API_KEYS:
            logger.warning("Rejected invalid API key")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )
        return {"sub": "service-account", "role": "agent", "auth_method": "api_key"}

    # --- JWT path (user-facing) ---
    if bearer:
        payload = decode_token(bearer.credentials)
        role = payload.get("role", "readonly")
        return {
            "sub": payload["sub"],
            "role": role,
            "auth_method": "jwt",
            "permissions": ROLE_PERMISSIONS.get(role, set()),
        }

    # --- Development fallback (REMOVE IN PRODUCTION) ---
    if os.getenv("ENVIRONMENT", "development") == "development":
        logger.debug("No auth credentials — using dev fallback (agent role)")
        return {"sub": "dev-user", "role": "agent", "auth_method": "dev_fallback"}

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_auth(required_role: str = "readonly"):
    """
    Decorator factory that enforces a minimum role level.

    Usage:
        @router.post("/cancel")
        @require_auth("agent")
        async def cancel(user = Depends(get_current_user)): ...
    """
    role_levels = {"readonly": 0, "agent": 1, "supervisor": 2, "admin": 3}

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, user: Dict = None, **kwargs):
            if user is None:
                raise HTTPException(status_code=401, detail="Not authenticated")
            user_level = role_levels.get(user.get("role", "readonly"), 0)
            required_level = role_levels.get(required_role, 0)
            if user_level < required_level:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role '{user['role']}' cannot perform this action. Required: {required_role}",
                )
            return await func(*args, user=user, **kwargs)
        return wrapper
    return decorator


def can_use_tool(user: Dict[str, Any], tool_name: str) -> bool:
    """
    Check whether the authenticated user's role allows calling a specific tool.

    Args:
        user: User context from get_current_user()
        tool_name: Name of the tool being invoked

    Returns:
        True if allowed, False otherwise
    """
    role = user.get("role", "readonly")
    allowed = ROLE_PERMISSIONS.get(role, set())
    return "*" in allowed or tool_name in allowed
