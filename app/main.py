"""
Algolab Bridge Server - Main Application
FastAPI application for proxying requests between Railway and Algolab API
"""

from contextlib import asynccontextmanager
from typing import Dict, Any
import httpx
from datetime import datetime

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import structlog

from .config import settings
from .session_manager import SessionManager


# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer() if settings.log_format == "json" else structlog.dev.ConsoleRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


# Global session manager instance
session_manager: SessionManager = None

# Global health check task
health_check_task = None


# ════════════════════════════════════════════════════════════════════════════════
# Helper Functions
# ════════════════════════════════════════════════════════════════════════════════

async def register_with_backend() -> bool:
    """
    Register Bridge Server with Backend on startup

    This function is called when the Bridge Server starts to notify the Backend
    that it's online and ready to accept requests.

    Returns:
        True if registration successful, False otherwise
    """
    try:
        # Prepare registration data
        registration_data = {
            "bridge_url": settings.bridge_public_url,
            "bridge_name": "Algolab Bridge Server",
            "environment": settings.environment,
            "version": "1.0.0",
            "status": "connected"
        }

        # Send registration to Backend
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{settings.backend_url}/api/admin/bridge/register",
                json=registration_data
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(
                    "🌉 Bridge Server Registered with Backend",
                    backend_url=settings.backend_url,
                    bridge_url=settings.bridge_public_url,
                    timestamp=datetime.utcnow().isoformat(),
                    response=result
                )
                return True
            else:
                logger.warning(
                    "⚠️  Backend returned non-200 status",
                    status_code=response.status_code,
                    response=response.text
                )
                return False

    except Exception as e:
        logger.warning(
            "⚠️  Failed to register with Backend (will continue anyway)",
            backend_url=settings.backend_url,
            error=str(e),
            error_type=type(e).__name__
        )
        return False


async def start_health_check_loop():
    """
    Start periodic health check to Backend

    This function sends periodic pings to the Backend to keep the connection
    alive and confirm the Bridge Server is still running.
    """
    import asyncio

    while True:
        try:
            await asyncio.sleep(60)  # Ping every 60 seconds

            ping_data = {
                "status": "alive",
                "timestamp": datetime.utcnow().isoformat()
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{settings.backend_url}/api/admin/bridge/ping",
                    json=ping_data
                )

                if response.status_code == 200:
                    logger.debug(
                        "💓 Health check ping sent",
                        backend_url=settings.backend_url
                    )
                else:
                    logger.warning(
                        "⚠️  Health check ping failed",
                        status_code=response.status_code
                    )

        except Exception as e:
            logger.warning(
                "⚠️  Error in health check loop",
                error=str(e)
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager
    Handles startup and shutdown events
    """
    # Startup
    logger.info("🚀 Bridge Server Starting", environment=settings.environment, port=settings.port)

    global session_manager
    session_manager = SessionManager(
        redis_url=settings.redis_url,
        ttl_seconds=settings.session_ttl_seconds
    )

    # Redis is OPTIONAL - don't fail startup if Redis is unavailable
    try:
        await session_manager.connect()
        logger.info("✅ Redis Connected", redis_url=settings.redis_url)

        # Health check (optional - don't fail on Redis issues)
        healthy = await session_manager.health_check()
        if healthy:
            logger.info("✅ Redis Health Check Passed")
        else:
            logger.warning("⚠️  Redis Health Check Failed (will continue)")
    except Exception as e:
        logger.warning("⚠️  Redis Connection Failed (will continue)", error=str(e))
        # Don't raise - server will continue without Redis

    # ═══════════════════════════════════════════════════════════════════════════
    # Register with Backend
    # ═══════════════════════════════════════════════════════════════════════════
    logger.info("📝 Attempting to register with Backend", backend_url=settings.backend_url)
    registration_success = await register_with_backend()

    if registration_success:
        logger.info("✅ Bridge Server Successfully Registered with Backend")
    else:
        logger.warning(
            "⚠️  Bridge Server Registration with Backend Failed (will continue operating)"
        )

    # Start health check loop (background task)
    import asyncio
    global health_check_task
    health_check_task = asyncio.create_task(start_health_check_loop())

    logger.info("✅ Bridge Server Started and Ready",
               bridge_url=settings.bridge_public_url,
               backend_url=settings.backend_url)

    yield

    # Shutdown
    logger.info("🛑 Bridge Server Shutting Down")

    # Cancel health check task
    if health_check_task and not health_check_task.done():
        health_check_task.cancel()
        logger.info("🛑 Health check task cancelled")

    # Notify Backend of disconnection
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{settings.backend_url}/api/admin/bridge/disconnect"
            )
            logger.info("✅ Disconnection notification sent to Backend")
    except Exception as e:
        logger.warning("⚠️  Failed to notify Backend of disconnection", error=str(e))

    # Close Redis connection
    if session_manager:
        await session_manager.close()
        logger.info("🔌 Redis Disconnected")

    logger.info("✅ Bridge Server Stopped")


# Create FastAPI app
app = FastAPI(
    title="Algolab Bridge Server",
    description="Proxy server for Algolab API (TR IP requirement bypass)",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
)


# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests"""
    logger.info(
        "http_request",
        method=request.method,
        url=str(request.url),
        client=request.client.host if request.client else None
    )

    try:
        response = await call_next(request)
        logger.info(
            "http_response",
            method=request.method,
            url=str(request.url),
            status_code=response.status_code
        )
        return response
    except Exception as e:
        logger.error(
            "http_request_failed",
            method=request.method,
            url=str(request.url),
            error=str(e)
        )
        raise


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(
        "unhandled_exception",
        url=str(request.url),
        error=str(exc),
        exc_info=True
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "Internal server error",
            "message": str(exc) if settings.environment != "production" else "An error occurred"
        }
    )


# Health check endpoint
@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint

    Returns:
        Health status including Redis connectivity
    """
    redis_healthy = await session_manager.health_check() if session_manager else False

    # Bridge server is always healthy - Redis is optional
    return {
        "status": "healthy",  # Always healthy even if Redis is down
        "environment": settings.environment,
        "redis": "connected" if redis_healthy else "not_configured",
        "algolab_api_url": settings.algolab_api_url
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Algolab Bridge Server",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs" if settings.environment != "production" else None
    }


@app.get("/bridge/broker-status")
async def broker_status() -> Dict[str, Any]:
    """
    Get Algolab broker connection status

    Returns detailed information about Algolab broker availability and configuration
    """
    return {
        "success": True,
        "broker": "algolab",
        "broker_name": "Algolab / Denizbank",
        "type": "trading_broker",
        "status": "available",
        "api_url": settings.algolab_api_url,
        "api_status": "operational",
        "websocket_url": settings.algolab_ws_url,
        "features": {
            "trading": True,
            "real_time_data": True,
            "market_data": True,
            "portfolio_tracking": True,
            "multi_timeframe": True,
            "order_execution": True,
            "session_management": True
        },
        "market": {
            "name": "BIST (Istanbul Stock Exchange)",
            "country": "Turkey",
            "timezone": "Europe/Istanbul",
            "currency": "TRY"
        },
        "connection": {
            "method": "https_api",
            "encryption": "aes256",
            "authentication": "credentials_based",
            "rate_limit": "5 seconds minimum",
            "session_ttl": f"{settings.session_ttl_seconds} seconds"
        },
        "redis": {
            "status": "connected" if session_manager else "not_configured",
            "url": settings.redis_url if settings.redis_url else "not_configured"
        },
        "environment": settings.environment
    }


@app.post("/bridge/broker-test")
async def test_broker_connection(
    credentials: Dict[str, str]
) -> Dict[str, Any]:
    """
    Test Algolab broker connection with given credentials

    Attempts to connect to Algolab API with provided credentials

    Args:
        credentials: Dictionary with 'username' and 'password' (encrypted)

    Returns:
        Test result with connection status and details
    """
    from .algolab_client import AlgolabClient

    try:
        api_key = credentials.get("api_key")
        username = credentials.get("username")
        password = credentials.get("password")

        if not all([api_key, username, password]):
            return {
                "success": False,
                "broker": "algolab",
                "test_status": "failed",
                "error": "Missing required credentials (api_key, username, password)"
            }

        # Create client and test connection
        client = AlgolabClient(api_key)

        # Test Algolab API connectivity
        result = await client.login_user(username, password)
        await client.close()

        if result.get("success"):
            return {
                "success": True,
                "broker": "algolab",
                "test_status": "success",
                "message": "Successfully connected to Algolab API",
                "details": {
                    "api_url": settings.algolab_api_url,
                    "response_time_ms": 0,  # Could measure actual time
                    "sms_required": True,
                    "next_step": "verify_sms_code"
                }
            }
        else:
            return {
                "success": False,
                "broker": "algolab",
                "test_status": "failed",
                "error": result.get("message", "Authentication failed"),
                "details": {
                    "api_url": settings.algolab_api_url,
                    "error_type": "authentication_failed"
                }
            }

    except Exception as e:
        return {
            "success": False,
            "broker": "algolab",
            "test_status": "failed",
            "error": str(e),
            "details": {
                "api_url": settings.algolab_api_url,
                "error_type": "connection_error"
            }
        }


# Import and include routers
from .routes import auth_router, trading_router, portfolio_router, market_router

app.include_router(auth_router, prefix="/bridge", tags=["Authentication"])
app.include_router(trading_router, prefix="/bridge", tags=["Trading"])
app.include_router(portfolio_router, prefix="/bridge", tags=["Portfolio"])
app.include_router(market_router, prefix="/bridge", tags=["Market Data"])


# Helper function to get session manager
def get_session_manager() -> SessionManager:
    """Dependency to get session manager"""
    return session_manager


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower()
    )
