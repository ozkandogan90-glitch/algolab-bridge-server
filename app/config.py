"""
Configuration management for Bridge Server
Uses pydantic-settings for environment variable validation
"""

from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import List, Optional


class Settings(BaseSettings):
    """Bridge Server Configuration"""

    # Algolab API
    algolab_api_url: str = Field(
        default="https://www.algolab.com.tr/api",
        description="Algolab REST API base URL"
    )
    algolab_ws_url: str = Field(
        default="wss://www.algolab.com.tr/api/ws",
        description="Algolab WebSocket URL"
    )
    algolab_hostname: str = Field(
        default="www.algolab.com.tr",
        description="Algolab hostname for checker signature"
    )

    # Mock Mode
    algolab_use_mock: bool = Field(
        default=True,
        description="Enable mock mode for testing without live API"
    )
    mock_success_rate: float = Field(
        default=0.95,
        description="Success rate for mock responses (0.0 to 1.0)"
    )

    # Bridge Public URL
    bridge_public_url: str = Field(
        default="https://algolab-bridge-server-production.up.railway.app",
        description="Bridge server public URL for Railway to connect"
    )

    # Backend Server URL
    backend_url: str = Field(
        default="https://trader-eidos-suite-backend-production.up.railway.app",
        description="Backend server URL for Bridge Server to register with. In production on Railway, this should be the public Railway domain."
    )

    # Security (Optional - for future authentication)
    bridge_jwt_secret: str = Field(
        default="dummy-secret-for-testing-only",
        description="JWT secret for Railway authentication (optional for now)"
    )
    bridge_secret_key: Optional[str] = Field(
        default=None,
        description="Shared secret key for Railway authentication (optional)"
    )

    # IP Whitelisting (optional)
    allowed_railway_ips: List[str] = Field(
        default_factory=list,
        description="Whitelisted Railway IPs (comma-separated in env)"
    )

    @validator("allowed_railway_ips", pre=True)
    def parse_ips(cls, v):
        if isinstance(v, str):
            return [ip.strip() for ip in v.split(",") if ip.strip()]
        return v

    # Session Storage
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for session storage"
    )
    session_ttl_seconds: int = Field(
        default=3600,
        description="Session TTL in seconds (default 1 hour)"
    )

    # Rate Limiting
    min_request_interval_seconds: float = Field(
        default=5.0,
        description="Minimum interval between Algolab API requests"
    )

    # Server
    host: str = Field(default="0.0.0.0", description="Server bind host")
    port: int = Field(default=8000, description="Server bind port")
    workers: int = Field(default=4, description="Number of worker processes")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(
        default="json",
        description="Log format: json or text"
    )

    # Environment
    environment: str = Field(
        default="development",
        description="Environment: development, staging, production"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()
