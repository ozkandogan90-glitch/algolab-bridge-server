"""
Cryptographic utilities for Algolab API
Implements AES-CBC encryption and SHA256 signature (Checker)
"""

import base64
import hashlib
import json
from typing import Dict, Any

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad


class AlgolabCrypto:
    """
    Handles encryption and signature generation for Algolab API

    Algolab uses:
    - AES-CBC encryption for sensitive data (username, password, SMS code)
    - SHA256 for request signature (Checker header)
    """

    def __init__(self, api_key: str, api_hostname: str):
        """
        Initialize crypto utilities

        Args:
            api_key: Full API key in format "APIKEY-{base64_encoded_key}"
            api_hostname: Algolab API hostname (e.g., "https://www.algolab.com.tr")
        """
        self.api_key_full = api_key
        self.api_hostname = api_hostname

        # Extract base64 key from APIKEY-{key} format
        try:
            if "-" in api_key:
                self.api_code = api_key.split("-", 1)[1]
            else:
                # If already extracted, use as-is
                self.api_code = api_key
        except IndexError:
            raise ValueError(f"Invalid API key format: {api_key}")

        # Decode base64 key for AES encryption
        try:
            self.aes_key = base64.b64decode(self.api_code.encode('utf-8'))
        except Exception as e:
            raise ValueError(f"Failed to decode API key: {e}")

        # AES IV: 16 bytes of zeros (as per Algolab spec)
        self.iv = b'\0' * 16

    def encrypt(self, text: str) -> str:
        """
        Encrypt text using AES-CBC

        Algolab spec:
        - Mode: CBC
        - IV: 16 zero bytes
        - Padding: PKCS7 (16 byte blocks)
        - Output: Base64 encoded

        Args:
            text: Plain text to encrypt

        Returns:
            Base64 encoded encrypted text

        Example:
            >>> crypto = AlgolabCrypto("APIKEY-xyz==", "https://...")
            >>> encrypted = crypto.encrypt("12345678901")
            >>> print(encrypted)
            'YTZ1RF2Q04T/nZThi0JzUA=='
        """
        try:
            cipher = AES.new(self.aes_key, AES.MODE_CBC, self.iv)
            text_bytes = text.encode('utf-8')
            padded_bytes = pad(text_bytes, AES.block_size)
            encrypted_bytes = cipher.encrypt(padded_bytes)
            return base64.b64encode(encrypted_bytes).decode("utf-8")
        except Exception as e:
            raise RuntimeError(f"Encryption failed: {e}")

    def decrypt(self, encrypted_text: str) -> str:
        """
        Decrypt AES-CBC encrypted text

        Args:
            encrypted_text: Base64 encoded encrypted text

        Returns:
            Decrypted plain text

        Note: Typically not needed for Bridge Server, but useful for testing
        """
        try:
            cipher = AES.new(self.aes_key, AES.MODE_CBC, self.iv)
            encrypted_bytes = base64.b64decode(encrypted_text.encode('utf-8'))
            decrypted_padded = cipher.decrypt(encrypted_bytes)
            decrypted_bytes = unpad(decrypted_padded, AES.block_size)
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            raise RuntimeError(f"Decryption failed: {e}")

    def make_checker(self, endpoint: str, payload: Dict[str, Any]) -> str:
        """
        Generate SHA256 signature (Checker) for API request

        Algolab spec:
        - Checker = SHA256(APIKEY + api_hostname + endpoint + body)
        - Body: JSON string with NO SPACES
        - Empty payload: use empty string

        Args:
            endpoint: API endpoint path (e.g., "/api/SendOrder")
            payload: Request body as dictionary

        Returns:
            64-character hexadecimal SHA256 hash

        Example:
            >>> crypto = AlgolabCrypto("APIKEY-xyz==", "https://www.algolab.com.tr")
            >>> checker = crypto.make_checker("/api/Portfolio", {"Subaccount": ""})
            >>> print(len(checker))
            64
        """
        try:
            # Convert payload to JSON string without spaces
            if payload and len(payload) > 0:
                body = json.dumps(payload, separators=(',', ':')).replace(' ', '')
            else:
                body = ""

            # Build signature string: APIKEY + hostname + endpoint + body
            signature_string = f"{self.api_key_full}{self.api_hostname}{endpoint}{body}"

            # Generate SHA256 hash
            hash_object = hashlib.sha256(signature_string.encode('utf-8'))
            checker = hash_object.hexdigest()

            return checker
        except Exception as e:
            raise RuntimeError(f"Checker generation failed: {e}")


def validate_api_key(api_key: str) -> bool:
    """
    Validate API key format

    Args:
        api_key: API key to validate

    Returns:
        True if valid, False otherwise
    """
    if not api_key:
        return False

    # Check format: APIKEY-{base64_string}
    if not api_key.startswith("APIKEY-") and not api_key.startswith("API-"):
        return False

    # Try to decode base64 part
    try:
        parts = api_key.split("-", 1)
        if len(parts) != 2:
            return False
        base64.b64decode(parts[1].encode('utf-8'))
        return True
    except Exception:
        return False


# Example usage and testing
if __name__ == "__main__":
    # Example API key (from Algolab documentation)
    example_api_key = "APIKEY-04YW0b9Cb8S0MrgBw/Y4iPYi2hjIidW7qj4hrhBhwZg="
    example_hostname = "https://www.algolab.com.tr"

    crypto = AlgolabCrypto(example_api_key, example_hostname)

    # Test encryption
    print("=== AES Encryption Test ===")
    plain_text = "test_password_123"
    encrypted = crypto.encrypt(plain_text)
    print(f"Plain: {plain_text}")
    print(f"Encrypted: {encrypted}")

    decrypted = crypto.decrypt(encrypted)
    print(f"Decrypted: {decrypted}")
    print(f"Match: {plain_text == decrypted}")

    # Test checker
    print("\n=== SHA256 Checker Test ===")
    endpoint = "/api/Portfolio"
    payload = {"Subaccount": ""}
    checker = crypto.make_checker(endpoint, payload)
    print(f"Endpoint: {endpoint}")
    print(f"Payload: {payload}")
    print(f"Checker: {checker}")
    print(f"Length: {len(checker)}")
