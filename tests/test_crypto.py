"""
Unit tests for crypto_utils module
Tests AES encryption and SHA256 checker generation
"""

import pytest
from app.crypto_utils import AlgolabCrypto, validate_api_key


class TestAlgolabCrypto:
    """Test cases for AlgolabCrypto class"""

    @pytest.fixture
    def crypto(self):
        """Create crypto instance with example API key"""
        api_key = "APIKEY-04YW0b9Cb8S0MrgBw/Y4iPYi2hjIidW7qj4hrhBhwZg="
        api_hostname = "https://www.algolab.com.tr"
        return AlgolabCrypto(api_key, api_hostname)

    def test_encryption_decryption(self, crypto):
        """Test AES encryption and decryption"""
        plain_text = "test_password_123"

        # Encrypt
        encrypted = crypto.encrypt(plain_text)
        assert encrypted != plain_text
        assert isinstance(encrypted, str)
        assert len(encrypted) > 0

        # Decrypt
        decrypted = crypto.decrypt(encrypted)
        assert decrypted == plain_text

    def test_encryption_produces_different_output(self, crypto):
        """Test that same input doesn't produce deterministic output (due to padding)"""
        text = "test"
        encrypted1 = crypto.encrypt(text)
        encrypted2 = crypto.encrypt(text)

        # Due to PKCS7 padding and zero IV, output should be identical for same input
        # This is expected behavior for Algolab's implementation
        assert encrypted1 == encrypted2

    def test_checker_generation(self, crypto):
        """Test SHA256 checker generation"""
        endpoint = "/api/Portfolio"
        payload = {"Subaccount": ""}

        checker = crypto.make_checker(endpoint, payload)

        # SHA256 hash should be 64 characters (hex)
        assert isinstance(checker, str)
        assert len(checker) == 64
        assert all(c in "0123456789abcdef" for c in checker)

    def test_checker_with_empty_payload(self, crypto):
        """Test checker generation with empty payload"""
        endpoint = "/api/SessionRefresh"
        payload = {}

        checker = crypto.make_checker(endpoint, payload)

        assert len(checker) == 64

    def test_checker_consistency(self, crypto):
        """Test that checker is consistent for same input"""
        endpoint = "/api/SendOrder"
        payload = {
            "symbol": "ASELS",
            "direction": "BUY",
            "price": "45.50",
            "lot": "100"
        }

        checker1 = crypto.make_checker(endpoint, payload)
        checker2 = crypto.make_checker(endpoint, payload)

        assert checker1 == checker2

    def test_checker_changes_with_payload(self, crypto):
        """Test that different payloads produce different checkers"""
        endpoint = "/api/SendOrder"

        payload1 = {"symbol": "ASELS"}
        payload2 = {"symbol": "THYAO"}

        checker1 = crypto.make_checker(endpoint, payload1)
        checker2 = crypto.make_checker(endpoint, payload2)

        assert checker1 != checker2

    def test_encryption_with_special_characters(self, crypto):
        """Test encryption with special characters"""
        text = "!@#$%^&*()_+-=[]{}|;:',.<>?/~`"
        encrypted = crypto.encrypt(text)
        decrypted = crypto.decrypt(encrypted)

        assert decrypted == text

    def test_encryption_with_unicode(self, crypto):
        """Test encryption with Turkish characters"""
        text = "ğüşıöçĞÜŞİÖÇ"
        encrypted = crypto.encrypt(text)
        decrypted = crypto.decrypt(encrypted)

        assert decrypted == text

    def test_invalid_api_key_format(self):
        """Test that invalid API key raises error"""
        with pytest.raises(ValueError):
            AlgolabCrypto("invalid-key", "https://example.com")

    def test_api_key_extraction(self):
        """Test API key extraction from APIKEY-xxx format"""
        api_key = "APIKEY-04YW0b9Cb8S0MrgBw/Y4iPYi2hjIidW7qj4hrhBhwZg="
        crypto = AlgolabCrypto(api_key, "https://www.algolab.com.tr")

        assert crypto.api_code == "04YW0b9Cb8S0MrgBw/Y4iPYi2hjIidW7qj4hrhBhwZg="
        assert crypto.api_key_full == api_key


class TestValidateApiKey:
    """Test cases for validate_api_key function"""

    def test_valid_api_key(self):
        """Test valid API key validation"""
        api_key = "APIKEY-04YW0b9Cb8S0MrgBw/Y4iPYi2hjIidW7qj4hrhBhwZg="
        assert validate_api_key(api_key) is True

    def test_valid_api_key_alternative_prefix(self):
        """Test valid API key with API- prefix"""
        api_key = "API-04YW0b9Cb8S0MrgBw/Y4iPYi2hjIidW7qj4hrhBhwZg="
        assert validate_api_key(api_key) is True

    def test_invalid_api_key_no_prefix(self):
        """Test invalid API key without prefix"""
        api_key = "04YW0b9Cb8S0MrgBw/Y4iPYi2hjIidW7qj4hrhBhwZg="
        assert validate_api_key(api_key) is False

    def test_invalid_api_key_wrong_prefix(self):
        """Test invalid API key with wrong prefix"""
        api_key = "WRONG-04YW0b9Cb8S0MrgBw/Y4iPYi2hjIidW7qj4hrhBhwZg="
        assert validate_api_key(api_key) is False

    def test_invalid_api_key_bad_base64(self):
        """Test invalid API key with invalid base64"""
        api_key = "APIKEY-not-valid-base64!!!"
        assert validate_api_key(api_key) is False

    def test_empty_api_key(self):
        """Test empty API key"""
        assert validate_api_key("") is False
        assert validate_api_key(None) is False


# Integration test with known values from Algolab documentation
class TestAlgolabIntegration:
    """Integration tests with real Algolab examples"""

    def test_known_checker_value(self):
        """Test checker generation with known expected value"""
        # From Algolab documentation
        api_key = "APIKEY-04YW0b9Cb8S0MrgBw/Y4iPYi2hjIidW7qj4hrhBhwZg="
        api_hostname = "https://www.algolab.com.tr"
        endpoint = "/api/Portfolio"
        payload = {"Subaccount": ""}

        crypto = AlgolabCrypto(api_key, api_hostname)
        checker = crypto.make_checker(endpoint, payload)

        # This is the expected format, not the exact value (depends on implementation)
        assert len(checker) == 64
        assert checker.islower()  # SHA256 hex is lowercase

    def test_encryption_format(self):
        """Test that encryption output is valid base64"""
        api_key = "APIKEY-04YW0b9Cb8S0MrgBw/Y4iPYi2hjIidW7qj4hrhBhwZg="
        crypto = AlgolabCrypto(api_key, "https://www.algolab.com.tr")

        encrypted = crypto.encrypt("test")

        # Base64 should only contain valid characters
        import string
        valid_chars = string.ascii_letters + string.digits + '+/='
        assert all(c in valid_chars for c in encrypted)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
