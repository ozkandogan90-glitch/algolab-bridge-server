"""
Bridge Server API Routes
Implements all proxy endpoints for Algolab API
"""

from typing import Dict, Any, Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Header, status, Query, Response
from pydantic import BaseModel, Field
import structlog

from .config import settings
from .session_manager import SessionManager, AlgolabSession
from .algolab_client import AlgolabClient
from .market_data_provider import AlgolabMarketDataProvider
from .auth import verify_railway_token


logger = structlog.get_logger()


# ===== Helper Function for Mock Mode Headers =====

def add_mock_mode_header(response: Response) -> None:
    """Add X-Mock-Mode header if mock mode is enabled"""
    if settings.algolab_use_mock:
        response.headers["X-Mock-Mode"] = "true"
        logger.debug("🎭 Mock mode active - added X-Mock-Mode header")



# ===== Request/Response Models =====

class LoginRequest(BaseModel):
    """Login request (Step 1 - SMS request)"""
    api_key: str = Field(..., description="Algolab API key")
    username: str = Field(..., description="TC kimlik no or username (plain text)")
    password: str = Field(..., description="Internet banking password (plain text)")


class LoginResponse(BaseModel):
    """Login response"""
    success: bool
    temp_token: str
    message: str = "SMS kodu telefon numaranıza gönderildi"


class VerifySMSRequest(BaseModel):
    """SMS verification request (Step 2)"""
    api_key: str
    temp_token: str
    sms_code: str = Field(..., description="SMS code from phone")


class VerifySMSResponse(BaseModel):
    """SMS verification response"""
    success: bool
    session_id: str
    hash: str
    expires_at: datetime
    message: str = "Algolab oturumu başarıyla oluşturuldu"


class RefreshSessionRequest(BaseModel):
    """Session refresh request"""
    session_id: str


class SendOrderRequest(BaseModel):
    """Send order request"""
    session_id: str
    symbol: str
    direction: str = Field(..., description="BUY or SELL")
    pricetype: str = Field(..., description="limit or market")
    price: str = Field(..., description="Price as string")
    lot: str = Field(..., description="Quantity as string")
    sms: bool = False
    email: bool = False
    subaccount: str = ""


class DeleteOrderRequest(BaseModel):
    """Delete order request"""
    session_id: str
    order_id: str
    subaccount: str = ""


class ModifyOrderRequest(BaseModel):
    """Modify order request"""
    session_id: str
    order_id: str
    price: str
    lot: str
    viop: bool = False
    subaccount: str = ""


class PortfolioRequest(BaseModel):
    """Portfolio request"""
    session_id: str
    subaccount: str = ""


class CashFlowRequest(BaseModel):
    """Cash flow request"""
    session_id: str
    subaccount: str = ""


class EquityInfoRequest(BaseModel):
    """Equity info request"""
    session_id: str
    symbol: str


# ===== Dependency Injection =====

async def get_session_manager() -> SessionManager:
    """Get session manager from app state"""
    from .main import session_manager
    if not session_manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session manager not available"
        )
    return session_manager


async def get_algolab_session(
    session_id: str,
    session_manager: SessionManager = Depends(get_session_manager)
) -> AlgolabSession:
    """Get and validate Algolab session"""
    session = await session_manager.get_session(session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session invalid or expired"
        )

    # Check expiration
    if datetime.utcnow() > session.expires_at:
        await session_manager.delete_session(session_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired"
        )

    return session


# ===== Routers =====

auth_router = APIRouter()
trading_router = APIRouter()
portfolio_router = APIRouter()
market_router = APIRouter()


# ===== Authentication Endpoints =====

@auth_router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    response: Response,
    railway_user: Dict = Depends(verify_railway_token),
    session_manager: SessionManager = Depends(get_session_manager)
):
    """
    Step 1: Request SMS code

    This endpoint:
    1. Validates API key
    2. Encrypts username and password
    3. Calls Algolab LoginUser API
    4. Returns temp token for SMS verification

    Returns:
        LoginResponse with temp_token
    """
    logger.info(
        "login_request",
        username=request.username[:3] + "***",  # Partially masked
        railway_user=railway_user.get("user_id"),
        mock_mode=settings.algolab_use_mock
    )

    try:
        # Create Algolab client
        client = AlgolabClient(request.api_key)

        # Call Algolab login
        result = await client.login_user(request.username, request.password)

        await client.close()

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("message", "Login failed")
            )

        temp_token = result.get("content", {}).get("token")
        if not temp_token:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No temp token received from Algolab"
            )

        logger.info("login_success", username=request.username[:3] + "***")

        # Add mock mode header if enabled
        add_mock_mode_header(response)

        return LoginResponse(
            success=True,
            temp_token=temp_token
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("login_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )



@auth_router.post("/verify-sms", response_model=VerifySMSResponse)
async def verify_sms(
    request: VerifySMSRequest,
    railway_user: Dict = Depends(verify_railway_token),
    session_manager: SessionManager = Depends(get_session_manager)
):
    """
    Step 2: Verify SMS code and create session

    This endpoint:
    1. Encrypts temp token and SMS code
    2. Calls Algolab LoginUserControl API
    3. Creates Bridge session with auth hash
    4. Stores session in Redis

    Returns:
        VerifySMSResponse with session_id and hash
    """
    logger.info(
        "verify_sms_request",
        sms_code="***",
        railway_user=railway_user.get("user_id")
    )

    try:
        # Create Algolab client
        client = AlgolabClient(request.api_key)

        # Verify SMS
        result = await client.login_user_control(request.temp_token, request.sms_code)

        if not result.get("success"):
            await client.close()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=result.get("message", "SMS verification failed")
            )

        # Extract hash
        content = result.get("content", {})
        auth_hash = content.get("hash")
        token = content.get("token")

        if not auth_hash:
            await client.close()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No auth hash received from Algolab"
            )

        await client.close()

        # Create session
        session = await session_manager.create_session(
            api_key=request.api_key,
            hash=auth_hash,
            token=token
        )

        logger.info(
            "session_created",
            session_id=session.session_id,
            railway_user=railway_user.get("user_id")
        )

        return VerifySMSResponse(
            success=True,
            session_id=session.session_id,
            hash=auth_hash,
            expires_at=session.expires_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("verify_sms_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SMS verification failed: {str(e)}"
        )


@auth_router.post("/refresh-session")
async def refresh_session(
    request: RefreshSessionRequest,
    railway_user: Dict = Depends(verify_railway_token),
    session_manager: SessionManager = Depends(get_session_manager)
):
    """
    Refresh session to extend expiration

    Calls Algolab SessionRefresh API and updates session TTL
    """
    logger.info(
        "refresh_session_request",
        session_id=request.session_id,
        railway_user=railway_user.get("user_id")
    )

    try:
        # Get session
        session = await get_algolab_session(request.session_id, session_manager)

        # Create Algolab client with existing session
        client = AlgolabClient(session.api_key)
        client.hash = session.hash
        client.token = session.token

        # Call SessionRefresh
        result = await client.session_refresh()

        await client.close()

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session refresh failed"
            )

        # Update session TTL
        updated_session = await session_manager.update_session(
            request.session_id,
            extend_ttl=True
        )

        logger.info("session_refreshed", session_id=request.session_id)

        return {
            "success": True,
            "expires_at": updated_session.expires_at,
            "message": "Session refreshed successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("refresh_session_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Session refresh failed: {str(e)}"
        )


# ===== Trading Endpoints =====

@trading_router.post("/send-order")
async def send_order(
    request: SendOrderRequest,
    railway_user: Dict = Depends(verify_railway_token),
    session_manager: SessionManager = Depends(get_session_manager)
):
    """
    Send trading order to Algolab

    Proxies order to Algolab SendOrder API with rate limiting
    """
    logger.info(
        "send_order_request",
        symbol=request.symbol,
        direction=request.direction,
        railway_user=railway_user.get("user_id")
    )

    try:
        # Get session
        session = await get_algolab_session(request.session_id, session_manager)

        # Create Algolab client
        client = AlgolabClient(session.api_key)
        client.hash = session.hash
        client.token = session.token

        # Send order
        result = await client.send_order(
            symbol=request.symbol,
            direction=request.direction,
            pricetype=request.pricetype,
            price=request.price,
            lot=request.lot,
            sms=request.sms,
            email=request.email,
            subaccount=request.subaccount
        )

        await client.close()

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("message", "Order failed")
            )

        logger.info(
            "send_order_success",
            symbol=request.symbol,
            order_ref=result.get("content", "")[:20]
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("send_order_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Send order failed: {str(e)}"
        )


@trading_router.post("/delete-order")
async def delete_order(
    request: DeleteOrderRequest,
    railway_user: Dict = Depends(verify_railway_token),
    session_manager: SessionManager = Depends(get_session_manager)
):
    """Cancel order"""
    logger.info("delete_order_request", order_id=request.order_id)

    try:
        session = await get_algolab_session(request.session_id, session_manager)

        client = AlgolabClient(session.api_key)
        client.hash = session.hash
        client.token = session.token

        result = await client.delete_order(request.order_id, request.subaccount)
        await client.close()

        logger.info("delete_order_success", order_id=request.order_id)
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_order_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Delete order failed: {str(e)}"
        )


@trading_router.post("/modify-order")
async def modify_order(
    request: ModifyOrderRequest,
    railway_user: Dict = Depends(verify_railway_token),
    session_manager: SessionManager = Depends(get_session_manager)
):
    """Modify order"""
    logger.info("modify_order_request", order_id=request.order_id)

    try:
        session = await get_algolab_session(request.session_id, session_manager)

        client = AlgolabClient(session.api_key)
        client.hash = session.hash
        client.token = session.token

        result = await client.modify_order(
            request.order_id,
            request.price,
            request.lot,
            request.viop,
            request.subaccount
        )
        await client.close()

        logger.info("modify_order_success", order_id=request.order_id)
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("modify_order_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Modify order failed: {str(e)}"
        )


# ===== Portfolio Endpoints =====

@portfolio_router.post("/portfolio")
async def get_portfolio(
    request: PortfolioRequest,
    railway_user: Dict = Depends(verify_railway_token),
    session_manager: SessionManager = Depends(get_session_manager)
):
    """Get portfolio positions"""
    logger.info("portfolio_request", session_id=request.session_id)

    try:
        session = await get_algolab_session(request.session_id, session_manager)

        client = AlgolabClient(session.api_key)
        client.hash = session.hash
        client.token = session.token

        result = await client.instant_position(request.subaccount)
        await client.close()

        logger.info("portfolio_success")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("portfolio_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Portfolio request failed: {str(e)}"
        )


@portfolio_router.post("/cash-flow")
async def get_cash_flow(
    request: CashFlowRequest,
    railway_user: Dict = Depends(verify_railway_token),
    session_manager: SessionManager = Depends(get_session_manager)
):
    """Get cash balances"""
    logger.info("cash_flow_request", session_id=request.session_id)

    try:
        session = await get_algolab_session(request.session_id, session_manager)

        client = AlgolabClient(session.api_key)
        client.hash = session.hash
        client.token = session.token

        result = await client.cash_flow(request.subaccount)
        await client.close()

        logger.info("cash_flow_success")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("cash_flow_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cash flow request failed: {str(e)}"
        )


@portfolio_router.post("/equity-info")
async def get_equity_info(
    request: EquityInfoRequest,
    railway_user: Dict = Depends(verify_railway_token),
    session_manager: SessionManager = Depends(get_session_manager)
):
    """Get stock information"""
    logger.info("equity_info_request", symbol=request.symbol)

    try:
        session = await get_algolab_session(request.session_id, session_manager)

        client = AlgolabClient(session.api_key)
        client.hash = session.hash
        client.token = session.token

        result = await client.get_equity_info(request.symbol)
        await client.close()

        logger.info("equity_info_success", symbol=request.symbol)
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("equity_info_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Equity info request failed: {str(e)}"
        )


# ===== Market Data Endpoints (BIST Data Provider) =====

class StockInfoRequest(BaseModel):
    """Request for stock information"""
    session_id: str
    symbol: str = Field(..., description="Stock symbol (e.g., ASELS)")


class MultipleStocksRequest(BaseModel):
    """Request for multiple stocks"""
    session_id: str
    symbols: List[str] = Field(..., description="List of stock symbols")


@market_router.post("/stock-info")
async def get_stock_info(
    request: StockInfoRequest,
    railway_user: Dict = Depends(verify_railway_token),
    session_manager: SessionManager = Depends(get_session_manager)
):
    """
    Get real-time stock information from BIST

    Provides current price, bid/ask, OHLC data, volume, and market metrics
    for Turkish stocks. Acts as yfinance alternative for BIST data.

    Args:
        request: Stock symbol and session ID
        railway_user: Authenticated Railway user
        session_manager: Session manager dependency

    Returns:
        Stock information with price, bid/ask, OHLC, volume, etc.

    Example:
        POST /bridge/stock-info
        {
            "session_id": "xyz123",
            "symbol": "ASELS"
        }

        Response:
        {
            "success": true,
            "data": {
                "symbol": "ASELS",
                "company_name": "Aselsan",
                "price": 45.50,
                "bid": 45.45,
                "ask": 45.55,
                "volume": 1000000,
                ...
            }
        }
    """
    logger.info("stock_info_request", symbol=request.symbol, user=railway_user.get("user_id"))

    try:
        session = await get_algolab_session(request.session_id, session_manager)

        # Create market data provider
        client = AlgolabClient(session.api_key)
        client.hash = session.hash
        client.token = session.token

        provider = AlgolabMarketDataProvider(client)

        # Check cache first
        cached = provider.get_cached_data(request.symbol)
        if cached:
            logger.info("stock_info_from_cache", symbol=request.symbol)
            await client.close()
            return {
                "success": True,
                "data": cached,
                "source": "cache"
            }

        # Fetch from Algolab API
        result = await provider.get_stock_info(request.symbol)
        await client.close()

        logger.info("stock_info_success", symbol=request.symbol)
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("stock_info_failed", symbol=request.symbol, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stock info: {str(e)}"
        )


@market_router.post("/multiple-stocks")
async def get_multiple_stocks(
    request: MultipleStocksRequest,
    railway_user: Dict = Depends(verify_railway_token),
    session_manager: SessionManager = Depends(get_session_manager)
):
    """
    Get information for multiple stocks at once

    Args:
        request: List of symbols and session ID
        railway_user: Authenticated Railway user
        session_manager: Session manager dependency

    Returns:
        Dictionary with data for each requested symbol

    Example:
        POST /bridge/multiple-stocks
        {
            "session_id": "xyz123",
            "symbols": ["ASELS", "GARAN", "YKBNK"]
        }
    """
    logger.info("multiple_stocks_request", count=len(request.symbols), user=railway_user.get("user_id"))

    try:
        session = await get_algolab_session(request.session_id, session_manager)

        client = AlgolabClient(session.api_key)
        client.hash = session.hash
        client.token = session.token

        provider = AlgolabMarketDataProvider(client)
        result = await provider.get_multiple_stocks(request.symbols)

        await client.close()

        logger.info("multiple_stocks_success", count=result.get("count"))
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("multiple_stocks_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get multiple stocks: {str(e)}"
        )


@market_router.post("/top-gainers")
async def get_top_gainers(
    request: PortfolioRequest,
    railway_user: Dict = Depends(verify_railway_token),
    session_manager: SessionManager = Depends(get_session_manager)
):
    """
    Get top gaining stocks

    Returns stocks with highest positive price change percentage

    Args:
        request: Session ID
        railway_user: Authenticated Railway user
        session_manager: Session manager dependency

    Returns:
        List of top 10 gainers with price and change info
    """
    logger.info("top_gainers_request", user=railway_user.get("user_id"))

    try:
        session = await get_algolab_session(request.session_id, session_manager)

        client = AlgolabClient(session.api_key)
        client.hash = session.hash
        client.token = session.token

        provider = AlgolabMarketDataProvider(client)
        result = await provider.get_top_gainers()

        await client.close()

        logger.info("top_gainers_success", count=result.get("count"))
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("top_gainers_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get top gainers: {str(e)}"
        )


@market_router.post("/top-losers")
async def get_top_losers(
    request: PortfolioRequest,
    railway_user: Dict = Depends(verify_railway_token),
    session_manager: SessionManager = Depends(get_session_manager)
):
    """
    Get top losing stocks

    Returns stocks with highest negative price change percentage

    Args:
        request: Session ID
        railway_user: Authenticated Railway user
        session_manager: Session manager dependency

    Returns:
        List of top 10 losers with price and change info
    """
    logger.info("top_losers_request", user=railway_user.get("user_id"))

    try:
        session = await get_algolab_session(request.session_id, session_manager)

        client = AlgolabClient(session.api_key)
        client.hash = session.hash
        client.token = session.token

        provider = AlgolabMarketDataProvider(client)
        result = await provider.get_top_losers()

        await client.close()

        logger.info("top_losers_success", count=result.get("count"))
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("top_losers_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get top losers: {str(e)}"
        )


@market_router.post("/most-active")
async def get_most_active(
    request: PortfolioRequest,
    railway_user: Dict = Depends(verify_railway_token),
    session_manager: SessionManager = Depends(get_session_manager),
    limit: int = Query(10, ge=1, le=50, description="Number of stocks to return")
):
    """
    Get most active stocks by volume

    Args:
        request: Session ID
        railway_user: Authenticated Railway user
        session_manager: Session manager dependency
        limit: Number of stocks to return (1-50, default 10)

    Returns:
        List of most active stocks by volume
    """
    logger.info("most_active_request", limit=limit, user=railway_user.get("user_id"))

    try:
        session = await get_algolab_session(request.session_id, session_manager)

        client = AlgolabClient(session.api_key)
        client.hash = session.hash
        client.token = session.token

        provider = AlgolabMarketDataProvider(client)
        result = await provider.get_most_active(limit)

        await client.close()

        logger.info("most_active_success", count=result.get("count"))
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("most_active_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get most active: {str(e)}"
        )
