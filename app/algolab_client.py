"""
Algolab API Client
Handles direct communication with Algolab API including rate limiting
"""

import time
import asyncio
import random
import uuid
from typing import Dict, Any, Optional
from datetime import datetime

import httpx
from pydantic import BaseModel

from .crypto_utils import AlgolabCrypto
from .config import settings
from .mock_data import MOCK_STOCK_DATA, MOCK_POSITIONS, MOCK_CASH_FLOW, MOCK_SUBACCOUNTS, get_mock_stock_detail


class RateLimiter:
    """
    Rate limiter for Algolab API requests
    Enforces minimum 5-second interval between requests
    """

    def __init__(self, min_interval: float = 5.0):
        self.min_interval = min_interval
        self.last_request_time = 0.0
        self._lock = asyncio.Lock()

    async def wait_if_needed(self):
        """Wait if minimum interval hasn't passed since last request"""
        async with self._lock:
            current_time = time.time()
            elapsed = current_time - self.last_request_time

            if self.last_request_time > 0.0 and elapsed < self.min_interval:
                wait_time = self.min_interval - elapsed + 0.1
                await asyncio.sleep(wait_time)

            self.last_request_time = time.time()


class AlgolabResponse(BaseModel):
    """Standard Algolab API response format"""
    success: bool
    message: str = ""
    content: Any = None


class MockAlgolabClient:
    """
    Mock client for Algolab API
    Simulates API responses without actual network calls
    """
    
    def __init__(self):
        self.token = "mock-temp-token-" + str(uuid.uuid4())
        self.hash = "mock-hash-" + str(uuid.uuid4())
        self.success_rate = settings.mock_success_rate
        
    async def _simulate_delay(self):
        """Simulate network latency"""
        await asyncio.sleep(random.uniform(0.1, 0.5))
        
    def _should_fail(self) -> bool:
        """Randomly fail based on success rate"""
        return random.random() > self.success_rate

    async def login_user(self, username: str, password: str) -> Dict[str, Any]:
        await self._simulate_delay()
        if self._should_fail():
            return {"success": False, "message": "Mock login failed"}
        return {
            "success": True, 
            "content": {"token": self.token},
            "message": "Mock login successful (SMS sent)"
        }

    async def login_user_control(self, temp_token: str, sms_code: str) -> Dict[str, Any]:
        await self._simulate_delay()
        if self._should_fail() or sms_code == "000000":
            return {"success": False, "message": "Invalid SMS code"}
        return {
            "success": True, 
            "content": {"hash": self.hash, "token": self.token},
            "message": "Mock authentication successful"
        }

    async def session_refresh(self) -> Dict[str, Any]:
        await self._simulate_delay()
        return {"success": True, "message": "Session refreshed"}

    async def send_order(self, symbol: str, direction: str, pricetype: str, price: str, lot: str, **kwargs) -> Dict[str, Any]:
        await self._simulate_delay()
        ref_id = f"REF-{random.randint(10000, 99999)}"
        return {
            "success": True,
            "content": f"Referans Numaranız: {ref_id}; İşleminiz Gerçekleşti",
            "message": "Order sent successfully"
        }

    async def delete_order(self, order_id: str, subaccount: str = "") -> Dict[str, Any]:
        await self._simulate_delay()
        return {"success": True, "message": "Order canceled"}

    async def modify_order(self, order_id: str, price: str, lot: str, **kwargs) -> Dict[str, Any]:
        await self._simulate_delay()
        return {"success": True, "message": "Order modified"}

    async def instant_position(self, subaccount: str = "") -> Dict[str, Any]:
        await self._simulate_delay()
        return {"success": True, "content": MOCK_POSITIONS}

    async def cash_flow(self, subaccount: str = "") -> Dict[str, Any]:
        await self._simulate_delay()
        return {"success": True, "content": MOCK_CASH_FLOW}

    async def get_equity_info(self, symbol: str) -> Dict[str, Any]:
        await self._simulate_delay()
        data = get_mock_stock_detail(symbol)
        return {"success": True, "content": data}

    async def get_subaccounts(self) -> Dict[str, Any]:
        await self._simulate_delay()
        return {"success": True, "content": MOCK_SUBACCOUNTS}
        
    async def close(self):
        pass


class AlgolabClient:
    """
    Client for Algolab API communication

    Handles:
    - Request signing (Checker)
    - AES encryption
    - Rate limiting
    - Session management
    - Mock mode switching
    """

    def __init__(
        self,
        api_key: str,
        api_url: Optional[str] = None,
        api_hostname: Optional[str] = None,
        min_request_interval: Optional[float] = None
    ):
        """
        Initialize Algolab API client

        Args:
            api_key: Full API key (APIKEY-{base64_key})
            api_url: API base URL (default from settings)
            api_hostname: Full hostname with https:// (default from settings)
            min_request_interval: Minimum seconds between requests (default 5.0)
        """
        self.api_key = api_key
        self.api_url = api_url or settings.algolab_api_url
        self.api_hostname = api_hostname or f"https://{settings.algolab_hostname}"
        
        # Check for Mock Mode
        self.use_mock = settings.algolab_use_mock
        if self.use_mock:
            self.mock_client = MockAlgolabClient()

        # Initialize crypto utilities
        self.crypto = AlgolabCrypto(api_key, self.api_hostname)

        # Rate limiter
        interval = min_request_interval or settings.min_request_interval_seconds
        self.rate_limiter = RateLimiter(min_interval=interval)

        # HTTP client
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )

        # Session state
        self.hash: Optional[str] = None
        self.token: Optional[str] = None

    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose()

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        payload: Dict[str, Any],
        authenticated: bool = False
    ) -> httpx.Response:
        """
        Make HTTP request to Algolab API

        Args:
            method: HTTP method (GET, POST)
            endpoint: API endpoint path
            payload: Request body
            authenticated: Whether to include Authorization and Checker headers

        Returns:
            HTTP response
        """
        # Wait for rate limit
        await self.rate_limiter.wait_if_needed()

        # Build headers
        headers = {
            "APIKEY": self.api_key,
            "Content-Type": "application/json"
        }

        if authenticated:
            if not self.hash:
                raise ValueError("Not authenticated: hash is missing")

            # Generate checker signature
            checker = self.crypto.make_checker(endpoint, payload)
            headers["Authorization"] = self.hash
            headers["Checker"] = checker

        # Make request
        url = f"{self.api_url}{endpoint}"

        if method.upper() == "POST":
            response = await self.http_client.post(url, json=payload, headers=headers)
        elif method.upper() == "GET":
            response = await self.http_client.get(url, params=payload, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        return response

    def _check_response(self, response: httpx.Response) -> Dict[str, Any]:
        """
        Check and parse Algolab API response

        Args:
            response: HTTP response

        Returns:
            Parsed JSON response

        Raises:
            HTTPError: If response status is not 200
        """
        if response.status_code == 429:
            raise httpx.HTTPStatusError(
                "Rate limit exceeded",
                request=response.request,
                response=response
            )

        if response.status_code != 200:
            raise httpx.HTTPStatusError(
                f"Algolab API error: {response.status_code}",
                request=response.request,
                response=response
            )

        return response.json()

    # ===== Authentication Methods =====

    async def login_user(self, username: str, password: str) -> Dict[str, Any]:
        """
        Step 1: Request SMS code

        Args:
            username: User's TC kimlik no or username (plain text)
            password: User's internet banking password (plain text)

        Returns:
            {"success": True, "content": {"token": "temp_token"}}
        """
        if self.use_mock:
            return await self.mock_client.login_user(username, password)

        # Encrypt credentials
        encrypted_username = self.crypto.encrypt(username)
        encrypted_password = self.crypto.encrypt(password)

        payload = {
            "username": encrypted_username,
            "password": encrypted_password
        }

        response = await self._make_request(
            "POST",
            "/api/LoginUser",
            payload,
            authenticated=False
        )

        result = self._check_response(response)

        # Store temp token
        if result.get("success"):
            self.token = result.get("content", {}).get("token")

        return result

    async def login_user_control(self, temp_token: str, sms_code: str) -> Dict[str, Any]:
        """
        Step 2: Verify SMS code and get authentication hash

        Args:
            temp_token: Temporary token from login_user
            sms_code: SMS code sent to user's phone (plain text)

        Returns:
            {"success": True, "content": {"hash": "JWT_TOKEN", "token": "..."}}
        """
        if self.use_mock:
            return await self.mock_client.login_user_control(temp_token, sms_code)

        # Encrypt token and SMS code
        encrypted_token = self.crypto.encrypt(temp_token)
        encrypted_sms = self.crypto.encrypt(sms_code)

        payload = {
            "token": encrypted_token,
            "password": encrypted_sms
        }

        response = await self._make_request(
            "POST",
            "/api/LoginUserControl",
            payload,
            authenticated=False
        )

        result = self._check_response(response)

        # Store authentication hash
        if result.get("success"):
            content = result.get("content", {})
            self.hash = content.get("hash")
            self.token = content.get("token")

        return result

    async def session_refresh(self) -> Dict[str, Any]:
        """
        Refresh active session to extend expiration

        Returns:
            {"success": True}
        """
        if self.use_mock:
            return await self.mock_client.session_refresh()

        response = await self._make_request(
            "POST",
            "/api/SessionRefresh",
            {},
            authenticated=True
        )

        return self._check_response(response)

    # ===== Trading Methods =====

    async def send_order(
        self,
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
        Send trading order

        Args:
            symbol: Stock symbol (e.g., "ASELS")
            direction: "BUY" or "SELL"
            pricetype: "limit" or "market"
            price: Price as string (e.g., "45.50")
            lot: Quantity as string (e.g., "100")
            sms: Send SMS notification
            email: Send email notification
            subaccount: Subaccount number (empty for active account)

        Returns:
            {"success": True, "content": "Referans Numaranız: 001VEV;..."}
        """
        if self.use_mock:
            return await self.mock_client.send_order(symbol, direction, pricetype, price, lot, sms, email, subaccount)

        payload = {
            "symbol": symbol,
            "direction": direction,
            "pricetype": pricetype,
            "price": price,
            "lot": lot,
            "sms": sms,
            "email": email,
            "Subaccount": subaccount
        }

        response = await self._make_request(
            "POST",
            "/api/SendOrder",
            payload,
            authenticated=True
        )

        return self._check_response(response)

    async def delete_order(self, order_id: str, subaccount: str = "") -> Dict[str, Any]:
        """
        Cancel order

        Args:
            order_id: Order reference number
            subaccount: Subaccount number (empty for active account)

        Returns:
            {"success": True, "message": "Canceled"}
        """
        if self.use_mock:
            return await self.mock_client.delete_order(order_id, subaccount)

        payload = {
            "id": order_id,
            "Subaccount": subaccount
        }

        response = await self._make_request(
            "POST",
            "/api/DeleteOrder",
            payload,
            authenticated=True
        )

        return self._check_response(response)

    async def modify_order(
        self,
        order_id: str,
        price: str,
        lot: str,
        viop: bool = False,
        subaccount: str = ""
    ) -> Dict[str, Any]:
        """
        Modify existing order

        Args:
            order_id: Order reference number
            price: New price as string
            lot: New quantity as string
            viop: Is VIOP order
            subaccount: Subaccount number

        Returns:
            {"success": True}
        """
        if self.use_mock:
            return await self.mock_client.modify_order(order_id, price, lot, viop, subaccount)

        payload = {
            "id": order_id,
            "price": price,
            "lot": lot,
            "viop": viop,
            "Subaccount": subaccount
        }

        response = await self._make_request(
            "POST",
            "/api/ModifyOrder",
            payload,
            authenticated=True
        )

        return self._check_response(response)

    # ===== Portfolio Methods =====

    async def instant_position(self, subaccount: str = "") -> Dict[str, Any]:
        """
        Get portfolio positions

        Args:
            subaccount: Subaccount number (empty for active account)

        Returns:
            {"success": True, "content": [...]}
        """
        if self.use_mock:
            return await self.mock_client.instant_position(subaccount)

        payload = {"Subaccount": subaccount}

        response = await self._make_request(
            "POST",
            "/api/InstantPosition",
            payload,
            authenticated=True
        )

        return self._check_response(response)

    async def cash_flow(self, subaccount: str = "") -> Dict[str, Any]:
        """
        Get cash balances (T+0, T+1, T+2)

        Args:
            subaccount: Subaccount number (empty for active account)

        Returns:
            {"success": True, "content": {"t0": "...", "t1": "...", "t2": "..."}}
        """
        if self.use_mock:
            return await self.mock_client.cash_flow(subaccount)

        payload = {"Subaccount": subaccount}

        response = await self._make_request(
            "POST",
            "/api/CashFlow",
            payload,
            authenticated=True
        )

        return self._check_response(response)

    async def get_equity_info(self, symbol: str) -> Dict[str, Any]:
        """
        Get stock information

        Args:
            symbol: Stock symbol (e.g., "ASELS")

        Returns:
            {"success": True, "content": {...}}
        """
        if self.use_mock:
            return await self.mock_client.get_equity_info(symbol)

        payload = {"symbol": symbol}

        response = await self._make_request(
            "POST",
            "/api/GetEquityInfo",
            payload,
            authenticated=True
        )

        return self._check_response(response)

    async def get_subaccounts(self) -> Dict[str, Any]:
        """
        Get user's subaccounts

        Returns:
            {"success": True, "content": [{"number": "100", "tradeLimit": "1000.00"}, ...]}
        """
        if self.use_mock:
            return await self.mock_client.get_subaccounts()

        response = await self._make_request(
            "POST",
            "/api/GetSubAccounts",
            {},
            authenticated=True
        )

        return self._check_response(response)


# Example usage
if __name__ == "__main__":
    import asyncio

    async def test_client():
        """Test Algolab client"""
        # Use a dummy key for testing
        api_key = "APIKEY-04YW0b9Cb8S0MrgBw/Y4iPYi2hjIidW7qj4hrhBhwZg="
        client = AlgolabClient(api_key)
        
        print(f"Client initialized. Mock Mode: {client.use_mock}")

        try:
            if client.use_mock:
                print("\n--- Testing Mock Mode ---")
                
                # Test Login
                print("\n1. Testing Login...")
                login_res = await client.login_user("test", "test")
                print(f"Login Result: {login_res}")
                
                if login_res.get("success"):
                    token = login_res["content"]["token"]
                    print("\n2. Testing Login Control...")
                    auth_res = await client.login_user_control(token, "123456")
                    print(f"Auth Result: {auth_res}")
                
                # Test Market Data
                print("\n3. Testing Market Data (ASELS)...")
                market_res = await client.get_equity_info("ASELS")
                print(f"Market Data: {market_res}")
                
                # Test Portfolio
                print("\n4. Testing Portfolio...")
                portfolio_res = await client.instant_position()
                print(f"Portfolio: {portfolio_res}")
                
            else:
                # Test encryption
                print("Testing encryption...")
                encrypted = client.crypto.encrypt("test")
                print(f"Encrypted: {encrypted}")

                # Test checker
                print("\nTesting checker...")
                checker = client.crypto.make_checker("/api/Portfolio", {"Subaccount": ""})
                print(f"Checker: {checker}")

        finally:
            await client.close()

    asyncio.run(test_client())
