"""JWK Set management for OAuth client authentication

This module handles generation, storage, and retrieval of RSA keys
for private_key_jwt client authentication method.
"""
import os
import json
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from jose import jwk
from flask import current_app


class JWKManager:
    """Manages RSA keys for OAuth client authentication"""

    def __init__(self, key_dir=None):
        """Initialize JWK manager

        Args:
            key_dir: Directory to store keys. If None, uses config or default.
        """
        self.key_dir = key_dir or self._get_key_dir()
        self._ensure_key_dir()
        self._private_key = None
        self._public_key = None
        self._jwk_dict = None

    def _get_key_dir(self):
        """Get key directory from config or use default"""
        if current_app:
            return current_app.config.get('JWK_KEY_DIR', '/tmp/jwks')
        return os.getenv('JWK_KEY_DIR', '/tmp/jwks')

    def _ensure_key_dir(self):
        """Ensure key directory exists"""
        Path(self.key_dir).mkdir(parents=True, exist_ok=True)

    def _get_key_paths(self):
        """Get paths for private and public key files"""
        return {
            'private': os.path.join(self.key_dir, 'private_key.pem'),
            'public': os.path.join(self.key_dir, 'public_key.pem'),
        }

    def generate_keys(self, key_size=2048):
        """Generate new RSA key pair

        Args:
            key_size: Size of RSA key in bits (default: 2048)
        """
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
        )

        key_paths = self._get_key_paths()

        # Save private key
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        with open(key_paths['private'], 'wb') as f:
            f.write(private_pem)

        # Save public key
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        with open(key_paths['public'], 'wb') as f:
            f.write(public_pem)

        self._private_key = private_key
        self._public_key = public_key
        self._jwk_dict = None  # Invalidate cached JWK

    def load_keys(self):
        """Load existing keys from disk"""
        key_paths = self._get_key_paths()

        if not os.path.exists(key_paths['private']):
            raise FileNotFoundError(f"Private key not found at {key_paths['private']}")

        # Load private key
        with open(key_paths['private'], 'rb') as f:
            self._private_key = serialization.load_pem_private_key(
                f.read(),
                password=None,
            )

        # Load public key
        if os.path.exists(key_paths['public']):
            with open(key_paths['public'], 'rb') as f:
                self._public_key = serialization.load_pem_public_key(f.read())
        else:
            # Derive public key from private key
            self._public_key = self._private_key.public_key()

        self._jwk_dict = None  # Invalidate cached JWK

    def get_or_create_keys(self):
        """Get existing keys or generate new ones if they don't exist"""
        key_paths = self._get_key_paths()

        if os.path.exists(key_paths['private']):
            self.load_keys()
        else:
            self.generate_keys()

    def get_private_key(self):
        """Get the private key object"""
        if self._private_key is None:
            self.get_or_create_keys()
        return self._private_key

    def get_private_key_pem(self):
        """Get private key as PEM string"""
        private_key = self.get_private_key()
        return private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')

    def get_public_key(self):
        """Get the public key object"""
        if self._public_key is None:
            self.get_or_create_keys()
        return self._public_key

    def get_jwk_dict(self):
        """Get public key as JWK dictionary"""
        if self._jwk_dict is None:
            public_key = self.get_public_key()
            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            # Convert to JWK using jose library
            self._jwk_dict = jwk.RSAKey(
                algorithm='RS256',
                key=public_pem.decode('utf-8')
            ).to_dict()
        return self._jwk_dict

    def get_jwks(self):
        """Get JWK Set (JSON Web Key Set) for public key advertisement"""
        jwk_dict = self.get_jwk_dict()
        # Add kid (key ID) if not present - use thumbprint or simple ID
        if 'kid' not in jwk_dict:
            # Use a simple key ID based on key material
            import hashlib
            key_str = json.dumps(jwk_dict, sort_keys=True)
            jwk_dict['kid'] = hashlib.sha256(key_str.encode()).hexdigest()[:16]
        return {
            'keys': [jwk_dict]
        }
