"""
Railway Backend - Algolab Bridge Client Example
Bu dosya Railway backend'de kullanılmak üzere örnek bir bridge client'tır.
backend/trader_eidos_suite/services/ altına kopyalanabilir.
"""

import httpx
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from jose import jwt
import structlog

logger = structlog.get_logger()


class AlgolabBridgeClient:
    """Client for communicating with Algolab Bridge Server"""

    def __init__(
        self,
        bridge_url: str,
        jwt_secret: str,
        shared_secret: Optional[str] = None,
        timeout: float = 30.0
    ):
        """
        Initialize bridge client

        Args:
            bridge_url: Bridge server URL (e.g., http://37.148.209.5:8000)
            jwt_secret: JWT secret for authentication
            shared_secret: Optional shared secret (alternative auth)
            timeout: Request timeout in seconds
        """
        self.bridge_url = bridge_url.rstrip("/")
        self.jwt_secret = jwt_secret
        self.shared_secret = shared_secret
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(max_connections=10)
        )

    def create_jwt_token(self, user_id: str) -> str:
        """Create JWT token for bridge authentication"""
        payload = {
            "user_id": user_id,
            "exp": datetime.utcnow() + timedelta(hours=1),
            "iat": datetime.utcnow(),
            "iss": "railway_backend"
        }
        return jwt.encode(payload, self.jwt_secret, algorithm="HS256")

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        user_id: str,
        payload: Dict[str, Any],
        use_shared_secret: bool = False
    ) -> Dict[str, Any]:
        """
        Make authenticated request to bridge

        Args:
            method: HTTP method (GET, POST)
            endpoint: Bridge endpoint (e.g., /bridge/send-order)
            user_id: Railway user ID
            payload: Request body
            use_shared_secret: Use shared secret instead of JWT

        Returns:
            Response JSON

        Raises:
            httpx.HTTPError: If request fails
        """
        url = f"{self.bridge_url}{endpoint}"

        # Build headers
        headers = {"Content-Type": "application/json"}

        if use_shared_secret and self.shared_secret:
            headers["X-Bridge-Secret"] = self.shared_secret
        else:
            # Use JWT authentication
            token = self.create_jwt_token(user_id)
            headers["Authorization"] = f"Bearer {token}"

        # Make request with retries
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if method.upper() == "POST":
                    response = await self.client.post(url, json=payload, headers=headers)
                elif method.upper() == "GET":
                    response = await self.client.get(url, params=payload, headers=headers)
                else:
                    raise ValueError(f"Unsupported method: {method}")

                response.raise_for_status()
                return response.json()

            except httpx.TimeoutException as e:
                logger.error(
                    "bridge_request_timeout",
                    endpoint=endpoint,
                    attempt=attempt + 1,
                    error=str(e)
                )
                if attempt == max_retries - 1:
                    raise

            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                logger.error(
                    "bridge_request_failed",
                    endpoint=endpoint,
                    status_code=status_code,
                    response=e.response.text
                )

                # Don't retry on client errors (4xx)
                if 400 <= status_code < 500:
                    raise

                # Retry on server errors (5xx)
                if attempt == max_retries - 1:
                    raise

            except httpx.RequestError as e:
                logger.error(
                    "bridge_connection_error",
                    endpoint=endpoint,
                    attempt=attempt + 1,
                    error=str(e)
                )
                if attempt == max_retries - 1:
                    raise

        # Should never reach here
        raise RuntimeError("Request failed after all retries")

    async def close(self):
        """Close HTTP client"""
        await self.client.close()

    # ===== Algolab Operations =====

    async def login(
        self,
        user_id: str,
        api_key: str,
        username: str,
        password: str
    ) -> Dict[str, Any]:
        """
        Step 1: Request SMS code from Algolab

        Args:
            user_id: Railway user ID
            api_key: User's Algolab API key
            username: Algolab username (TC kimlik)
            password: Algolab password

        Returns:
            {"success": True, "temp_token": "..."}
        """
        payload = {
            "api_key": api_key,
            "username": username,
            "password": password
        }

        result = await self._make_request(
            "POST",
            "/bridge/login",
            user_id,
            payload
        )

        logger.info("algolab_login_requested", user_id=user_id)
        return result

    async def verify_sms(
        self,
        user_id: str,
        api_key: str,
        temp_token: str,
        sms_code: str
    ) -> Dict[str, Any]:
        """
        Step 2: Verify SMS code and get session

        Args:
            user_id: Railway user ID
            api_key: User's Algolab API key
            temp_token: Temp token from login step
            sms_code: SMS code from user's phone

        Returns:
            {"success": True, "session_id": "...", "hash": "...", "expires_at": "..."}
        """
        payload = {
            "api_key": api_key,
            "temp_token": temp_token,
            "sms_code": sms_code
        }

        result = await self._make_request(
            "POST",
            "/bridge/verify-sms",
            user_id,
            payload
        )

        logger.info("algolab_session_created", user_id=user_id)
        return result

    async def send_order(
        self,
        user_id: str,
        session_id: str,
        symbol: str,
        direction: str,
        pricetype: str,
        price: str,
        lot: str,
        sms: bool = False,
        email: bool = False,
        subaccount: str = ""
    ) -> Dict[str, Any]:
        """
        Send order to Algolab via bridge

        Args:
            user_id: Railway user ID
            session_id: Bridge session ID
            symbol: Stock symbol (e.g., "ASELS")
            direction: "BUY" or "SELL"
            pricetype: "limit" or "market"
            price: Price as string
            lot: Quantity as string
            sms: SMS notification
            email: Email notification
            subaccount: Subaccount number

        Returns:
            {"success": True, "content": "Order reference..."}
        """
        payload = {
            "session_id": session_id,
            "symbol": symbol,
            "direction": direction,
            "pricetype": pricetype,
            "price": price,
            "lot": lot,
            "sms": sms,
            "email": email,
            "subaccount": subaccount
        }

        result = await self._make_request(
            "POST",
            "/bridge/send-order",
            user_id,
            payload
        )

        logger.info(
            "algolab_order_sent",
            user_id=user_id,
            symbol=symbol,
            direction=direction
        )
        return result

    async def delete_order(
        self,
        user_id: str,
        session_id: str,
        order_id: str,
        subaccount: str = ""
    ) -> Dict[str, Any]:
        """Delete/cancel order"""
        payload = {
            "session_id": session_id,
            "order_id": order_id,
            "subaccount": subaccount
        }

        return await self._make_request(
            "POST",
            "/bridge/delete-order",
            user_id,
            payload
        )

    async def modify_order(
        self,
        user_id: str,
        session_id: str,
        order_id: str,
        price: str,
        lot: str,
        viop: bool = False,
        subaccount: str = ""
    ) -> Dict[str, Any]:
        """Modify existing order"""
        payload = {
            "session_id": session_id,
            "order_id": order_id,
            "price": price,
            "lot": lot,
            "viop": viop,
            "subaccount": subaccount
        }

        return await self._make_request(
            "POST",
            "/bridge/modify-order",
            user_id,
            payload
        )

    async def get_portfolio(
        self,
        user_id: str,
        session_id: str,
        subaccount: str = ""
    ) -> Dict[str, Any]:
        """Get portfolio from Algolab"""
        payload = {
            "session_id": session_id,
            "subaccount": subaccount
        }

        return await self._make_request(
            "POST",
            "/bridge/portfolio",
            user_id,
            payload
        )

    async def get_cash_flow(
        self,
        user_id: str,
        session_id: str,
        subaccount: str = ""
    ) -> Dict[str, Any]:
        """Get cash balances"""
        payload = {
            "session_id": session_id,
            "subaccount": subaccount
        }

        return await self._make_request(
            "POST",
            "/bridge/cash-flow",
            user_id,
            payload
        )

    async def get_equity_info(
        self,
        user_id: str,
        session_id: str,
        symbol: str
    ) -> Dict[str, Any]:
        """Get stock/equity information"""
        payload = {
            "session_id": session_id,
            "symbol": symbol
        }

        return await self._make_request(
            "POST",
            "/bridge/equity-info",
            user_id,
            payload
        )

    async def refresh_session(
        self,
        user_id: str,
        session_id: str
    ) -> Dict[str, Any]:
        """Refresh Algolab session"""
        payload = {"session_id": session_id}

        return await self._make_request(
            "POST",
            "/bridge/refresh-session",
            user_id,
            payload
        )


# ===== Usage Example in Railway Backend =====

async def example_usage():
    """Example: How to use bridge client in Railway backend"""
    import os

    # Initialize bridge client
    bridge = AlgolabBridgeClient(
        bridge_url=os.getenv("ALGOLAB_BRIDGE_URL", "http://37.148.209.5:8000"),
        jwt_secret=os.getenv("BRIDGE_JWT_SECRET"),
        shared_secret=os.getenv("BRIDGE_SECRET_KEY")  # Optional
    )

    try:
        user_id = "railway_user_123"
        api_key = "APIKEY-xyz=="  # User's Algolab API key (from database)

        # Step 1: Request SMS
        print("Step 1: Requesting SMS...")
        login_result = await bridge.login(
            user_id=user_id,
            api_key=api_key,
            username="12345678901",  # TC kimlik no
            password="user_password"
        )

        temp_token = login_result["temp_token"]
        print(f"✅ SMS sent. Temp token: {temp_token[:20]}...")

        # (User enters SMS code from phone)
        sms_code = input("Enter SMS code: ")

        # Step 2: Verify SMS
        print("\nStep 2: Verifying SMS...")
        session_result = await bridge.verify_sms(
            user_id=user_id,
            api_key=api_key,
            temp_token=temp_token,
            sms_code=sms_code
        )

        session_id = session_result["session_id"]
        print(f"✅ Session created: {session_id}")

        # Step 3: Send order
        print("\nStep 3: Sending order...")
        order_result = await bridge.send_order(
            user_id=user_id,
            session_id=session_id,
            symbol="ASELS",
            direction="BUY",
            pricetype="limit",
            price="45.50",
            lot="100"
        )

        print(f"✅ Order sent: {order_result}")

        # Get portfolio
        print("\nGetting portfolio...")
        portfolio = await bridge.get_portfolio(
            user_id=user_id,
            session_id=session_id
        )
        print(f"✅ Portfolio: {portfolio}")

    except httpx.TimeoutException:
        print("❌ Request timeout - Bridge server might be down")
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP error {e.response.status_code}: {e.response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await bridge.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())
