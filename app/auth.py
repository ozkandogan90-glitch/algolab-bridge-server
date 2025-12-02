"""
Authentication module for Railway requests
Verifies JWT tokens from Railway backend
"""

from typing import Dict, Optional
from datetime import datetime, timedelta

from fastapi import Security, HTTPException, status, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import structlog

from .config import settings


logger = structlog.get_logger()

security = HTTPBearer()


def create_jwt_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT token for Railway authentication

    Args:
        user_id: Railway user ID
        expires_delta: Token expiration time (default 1 hour)

    Returns:
        JWT token string

    Example (Railway backend usage):
        >>> token = create_jwt_token("user_123")
        >>> headers = {"Authorization": f"Bearer {token}"}
    """
    if expires_delta is None:
        expires_delta = timedelta(hours=1)

    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + expires_delta,
        "iat": datetime.utcnow(),
        "iss": "railway_backend"
    }

    token = jwt.encode(
        payload,
        settings.bridge_jwt_secret,
        algorithm="HS256"
    )

    return token


def verify_jwt_token(token: str) -> Dict[str, str]:
    """
    Verify JWT token from Railway

    Args:
        token: JWT token string

    Returns:
        Decoded payload

    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.bridge_jwt_secret,
            algorithms=["HS256"]
        )

        # Validate issuer
        if payload.get("iss") != "railway_backend":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token issuer"
            )

        return payload

    except JWTError as e:
        logger.warning("jwt_validation_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {str(e)}"
        )


def check_ip_whitelist(request: Request) -> bool:
    """
    Check if request IP is in whitelist

    Args:
        request: FastAPI request object

    Returns:
        True if IP is whitelisted or whitelist is disabled

    Raises:
        HTTPException: If IP is not whitelisted
    """
    # If no whitelist configured, allow all
    if not settings.allowed_railway_ips:
        return True

    # Get client IP
    client_ip = request.client.host if request.client else None

    # Check X-Forwarded-For header (if behind proxy/nginx)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take first IP in chain
        client_ip = forwarded_for.split(",")[0].strip()

    # Check whitelist
    if client_ip not in settings.allowed_railway_ips:
        logger.warning(
            "ip_not_whitelisted",
            client_ip=client_ip,
            whitelisted_ips=settings.allowed_railway_ips
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"IP {client_ip} not whitelisted"
        )

    return True


async def verify_railway_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> Dict[str, str]:
    """
    FastAPI dependency to verify Railway JWT token and IP

    Usage in routes:
        @router.post("/endpoint")
        async def endpoint(user: Dict = Depends(verify_railway_token)):
            user_id = user["user_id"]
            ...

    Returns:
        Decoded token payload

    Raises:
        HTTPException: If authentication fails
    """
    # Check IP whitelist first
    check_ip_whitelist(request)

    # Verify JWT token
    token = credentials.credentials
    payload = verify_jwt_token(token)

    logger.info(
        "railway_request_authenticated",
        user_id=payload.get("user_id"),
        client_ip=request.client.host if request.client else None
    )

    return payload


async def verify_shared_secret(
    request: Request,
    x_bridge_secret: str = Header(..., description="Shared secret key")
) -> bool:
    """
    Alternative authentication using shared secret

    Usage in routes:
        @router.post("/endpoint")
        async def endpoint(auth: bool = Depends(verify_shared_secret)):
            ...

    Returns:
        True if authenticated

    Raises:
        HTTPException: If secret is invalid
    """
    # Check IP whitelist first
    check_ip_whitelist(request)

    if not settings.bridge_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Shared secret authentication not configured"
        )

    if x_bridge_secret != settings.bridge_secret_key:
        logger.warning("shared_secret_authentication_failed")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid bridge secret"
        )

    logger.info("shared_secret_authenticated")
    return True


# Example usage
if __name__ == "__main__":
    # Test JWT creation and verification
    test_secret = "test-secret-key-123"

    # Temporarily override settings for test
    import sys
    sys.modules[__name__].settings.bridge_jwt_secret = test_secret

    # Create token
    token = create_jwt_token("test_user_123")
    print(f"Generated token: {token[:50]}...")

    # Verify token
    try:
        payload = verify_jwt_token(token)
        print(f"Token valid! User ID: {payload['user_id']}")
    except HTTPException as e:
        print(f"Token invalid: {e.detail}")

    # Test expired token
    expired_token = create_jwt_token("test_user", timedelta(seconds=-10))
    try:
        verify_jwt_token(expired_token)
    except HTTPException as e:
        print(f"Expired token rejected: {e.detail}")
