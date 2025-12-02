"""
Phase 1 Mock Mode Test Suite
Tests for Algolab Bridge Server in Mock Mode

Test Scenarios:
- TS1.3: Health Check
- TS1.5: Market Data (ASELS)
- TS1.7: Mock Mode Header
"""

import pytest
import httpx
from typing import Dict, Any


# Bridge Server URL (adjust if needed)
BRIDGE_URL = "http://localhost:8001"


class TestPhase1MockMode:
    """Test suite for Phase 1 Mock Mode functionality"""

    @pytest.mark.asyncio
    async def test_ts1_3_health_check(self):
        """
        TS1.3: Health Check
        Verify Bridge Server /health endpoint returns 200 OK
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BRIDGE_URL}/health")
            
            # Assert status code
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            
            # Assert response structure
            data = response.json()
            assert "status" in data, "Response missing 'status' field"
            assert data["status"] == "healthy", f"Expected 'healthy', got {data['status']}"
            
            print("✅ TS1.3 PASSED: Health check successful")

    @pytest.mark.asyncio
    async def test_ts1_5_market_data_asels(self):
        """
        TS1.5: Market Data Test
        Request ASELS data and verify it matches mock_data.py
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BRIDGE_URL}/bridge/market-data/ASELS")
            
            # Assert status code
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            
            # Get response data
            data = response.json()
            
            # Verify expected mock data structure
            assert "symbol" in data, "Response missing 'symbol' field"
            assert data["symbol"] == "ASELS", f"Expected 'ASELS', got {data['symbol']}"
            
            # Verify price data exists
            assert "price" in data, "Response missing 'price' field"
            assert data["price"] == 45.50, f"Expected price 45.50, got {data['price']}"
            
            # Verify other key fields from mock_data.py
            assert data["desc"] == "ASELSAN ELEKTRONIK SANAYI"
            assert data["bid"] == 45.45
            assert data["ask"] == 45.55
            assert data["volume"] == 1250000
            
            print("✅ TS1.5 PASSED: Market data matches mock_data.py")

    @pytest.mark.asyncio
    async def test_ts1_7_mock_mode_header(self):
        """
        TS1.7: Mock Mode Header Check
        Verify responses include X-Mock-Mode: true header
        """
        async with httpx.AsyncClient() as client:
            # Test health endpoint
            response = await client.get(f"{BRIDGE_URL}/health")
            
            # Check for X-Mock-Mode header
            assert "x-mock-mode" in response.headers, "Missing X-Mock-Mode header"
            assert response.headers["x-mock-mode"] == "true", \
                f"Expected 'true', got {response.headers['x-mock-mode']}"
            
            print("✅ TS1.7 PASSED: X-Mock-Mode header present")

    @pytest.mark.asyncio
    async def test_all_scenarios_combined(self):
        """
        Combined test: Run all scenarios in sequence
        """
        print("\n" + "="*60)
        print("🎭 PHASE 1 MOCK MODE TEST SUITE")
        print("="*60)
        
        async with httpx.AsyncClient() as client:
            # TS1.3: Health Check
            print("\n[TS1.3] Testing Health Check...")
            health_response = await client.get(f"{BRIDGE_URL}/health")
            assert health_response.status_code == 200
            print("✅ Health check passed")
            
            # TS1.5: Market Data
            print("\n[TS1.5] Testing Market Data (ASELS)...")
            market_response = await client.get(f"{BRIDGE_URL}/bridge/market-data/ASELS")
            assert market_response.status_code == 200
            market_data = market_response.json()
            assert market_data["symbol"] == "ASELS"
            assert market_data["price"] == 45.50
            print(f"✅ Market data received: {market_data['desc']} @ {market_data['price']} TL")
            
            # TS1.7: Mock Mode Header
            print("\n[TS1.7] Testing Mock Mode Header...")
            assert "x-mock-mode" in health_response.headers
            assert health_response.headers["x-mock-mode"] == "true"
            print("✅ X-Mock-Mode header confirmed")
            
            print("\n" + "="*60)
            print("🎉 ALL TESTS PASSED!")
            print("="*60)


# Synchronous test runner for manual execution
def run_tests_sync():
    """
    Run tests synchronously (for manual testing without pytest)
    """
    import asyncio
    
    async def run_all():
        test_suite = TestPhase1MockMode()
        
        print("\n🧪 Running Phase 1 Mock Mode Tests...\n")
        
        try:
            await test_suite.test_ts1_3_health_check()
        except Exception as e:
            print(f"❌ TS1.3 FAILED: {e}")
        
        try:
            await test_suite.test_ts1_5_market_data_asels()
        except Exception as e:
            print(f"❌ TS1.5 FAILED: {e}")
        
        try:
            await test_suite.test_ts1_7_mock_mode_header()
        except Exception as e:
            print(f"❌ TS1.7 FAILED: {e}")
        
        print("\n✅ Test suite completed!")
    
    asyncio.run(run_all())


if __name__ == "__main__":
    # Run tests directly
    run_tests_sync()
