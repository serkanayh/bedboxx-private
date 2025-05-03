"""
Sensitive Data Encryption Module for StopSale Automation System

This module provides encryption and secure handling of sensitive data
such as personal information, credentials, and business-critical data.
"""

import os
import base64
import json
import logging
import secrets
import hashlib
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime

# Set up logging
logger = logging.getLogger(__name__)

# Try to import cryptography
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.primitives.serialization import (
        load_pem_private_key,
        load_pem_public_key,
        Encoding,
        PrivateFormat,
        PublicFormat,
        NoEncryption,
        BestAvailableEncryption
    )
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning("cryptography not installed. Encryption will be limited.")


class EncryptionManager:
    """Class for encrypting and decrypting sensitive data"""
    
    def __init__(self, app_name: str = 'stopsale', 
                 key_path: Optional[str] = None,
                 master_password: Optional[str] = None):
        """
        Initialize the encryption manager
        
        Args:
            app_name: Application name for namespacing
            key_path: Path to store encryption keys (if None, uses ~/.{app_name}/crypto/)
            master_password: Master password for key encryption (if None, uses environment variable or prompts)
        """
        self.app_name = app_name
        
        # Set up key path
        if key_path is None:
            home_dir = os.path.expanduser("~")
            app_dir = os.path.join(home_dir, f".{app_name}")
            self.key_path = os.path.join(app_dir, "crypto")
        else:
            self.key_path = key_path
        
        os.makedirs(self.key_path, exist_ok=True)
        
        # Get master password
        if master_password is None:
            master_password = os.environ.get(f"{self.app_name.upper()}_MASTER_PASSWORD")
            
            if master_password is None:
                # If running interactively, prompt for password
                if os.isatty(0):
                    import getpass
                    master_password = getpass.getpass("Enter master password for encryption: ")
                else:
                    # Default password for non-interactive environments
                    # This is not secure and should be changed in production
                    master_password = f"default_{self.app_name}_password"
                    logger.warning("Using default master password. This is not secure!")
        
        self.master_password = master_password
        
        # Initialize encryption keys
        self.symmetric_key = self._load_or_create_symmetric_key()
        self.rsa_keys = self._load_or_create_rsa_keys()
    
    def _load_or_create_symmetric_key(self) -> Optional[bytes]:
        """
        Load or create symmetric encryption key
        
        Returns:
            bytes: Symmetric key or None if failed
        """
        if not CRYPTO_AVAILABLE:
            logger.warning("Cryptography not available. Cannot create symmetric key.")
            return None
        
        key_file = os.path.join(self.key_path, "symmetric.key")
        
        if os.path.exists(key_file):
            # Load existing key
            try:
                with open(key_file, 'rb') as f:
                    encrypted_key = f.read()
                
                # Derive key from master password to decrypt the symmetric key
                salt = self._get_salt()
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=salt,
                    iterations=100000,
                )
                key = base64.urlsafe_b64encode(kdf.derive(self.master_password.encode()))
                
                # Decrypt the symmetric key
                f = Fernet(key)
                return f.decrypt(encrypted_key)
            
            except Exception as e:
                logger.error(f"Error loading symmetric key: {str(e)}")
                return None
        
        # Create new key
        try:
            # Generate a new key
            key = Fernet.generate_key()
            
            # Derive key from master password to encrypt the symmetric key
            salt = self._get_salt()
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            encryption_key = base64.urlsafe_b64encode(kdf.derive(self.master_password.encode()))
            
            # Encrypt the symmetric key
            f = Fernet(encryption_key)
            encrypted_key = f.encrypt(key)
            
            # Save the encrypted key
            with open(key_file, 'wb') as f:
                f.write(encrypted_key)
            
            # Set secure permissions
            os.chmod(key_file, 0o600)
            
            return key
        
        except Exception as e:
            logger.error(f"Error creating symmetric key: {str(e)}")
            return None
    
    def _load_or_create_rsa_keys(self) -> Dict[str, Any]:
        """
        Load or create RSA key pair
        
        Returns:
            dict: Dictionary containing RSA keys or empty if failed
        """
        if not CRYPTO_AVAILABLE:
            logger.warning("Cryptography not available. Cannot create RSA keys.")
            return {}
        
        private_key_file = os.path.join(self.key_path, "private.pem")
        public_key_file = os.path.join(self.key_path, "public.pem")
        
        if os.path.exists(private_key_file) and os.path.exists(public_key_file):
            # Load existing keys
            try:
                with open(private_key_file, 'rb') as f:
                    private_key_data = f.read()
                
                with open(public_key_file, 'rb') as f:
                    public_key_data = f.read()
                
                # Load the private key with password
                private_key = load_pem_private_key(
                    private_key_data,
                    password=self.master_password.encode(),
                )
                
                # Load the public key
                public_key = load_pem_public_key(public_key_data)
                
                return {
                    "private_key": private_key,
                    "public_key": public_key
                }
            
            except Exception as e:
                logger.error(f"Error loading RSA keys: {str(e)}")
                return {}
        
        # Create new keys
        try:
            # Generate a new key pair
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )
            public_key = private_key.public_key()
            
            # Serialize the private key with password protection
            private_key_data = private_key.private_bytes(
                encoding=Encoding.PEM,
                format=PrivateFormat.PKCS8,
                encryption_algorithm=BestAvailableEncryption(self.master_password.encode())
            )
            
            # Serialize the public key
            public_key_data = public_key.public_bytes(
                encoding=Encoding.PEM,
                format=PublicFormat.SubjectPublicKeyInfo
            )
            
            # Save the keys
            with open(private_key_file, 'wb') as f:
                f.write(private_key_data)
            
            with open(public_key_file, 'wb') as f:
                f.write(public_key_data)
            
            # Set secure permissions
            os.chmod(private_key_file, 0o600)
            os.chmod(public_key_file, 0o644)
            
            return {
                "private_key": private_key,
                "public_key": public_key
            }
        
        except Exception as e:
            logger.error(f"Error creating RSA keys: {str(e)}")
            return {}
    
    def _get_salt(self) -> bytes:
        """
        Get salt for key derivation
        
        Returns:
            bytes: Salt value
        """
        salt_file = os.path.join(self.key_path, "salt")
        
        if os.path.exists(salt_file):
            # Load existing salt
            try:
                with open(salt_file, 'rb') as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Error loading salt: {str(e)}")
        
        # Create new salt
        try:
            salt = os.urandom(16)
            
            with open(salt_file, 'wb') as f:
                f.write(salt)
            
            # Set secure permissions
            os.chmod(salt_file, 0o600)
            
            return salt
        
        except Exception as e:
            logger.error(f"Error creating salt: {str(e)}")
            return b'stopsale_default_salt'  # Fallback salt (not secure for production)
    
    def encrypt_symmetric(self, data: Union[str, bytes]) -> Optional[bytes]:
        """
        Encrypt data using symmetric encryption
        
        Args:
            data: Data to encrypt (string or bytes)
            
        Returns:
            bytes: Encrypted data or None if encryption failed
        """
        if not CRYPTO_AVAILABLE or self.symmetric_key is None:
            logger.warning("Symmetric encryption not available. Using base64 encoding only.")
            if isinstance(data, str):
                return base64.b64encode(data.encode())
            return base64.b64encode(data)
        
        try:
            # Convert string to bytes if needed
            if isinstance(data, str):
                data = data.encode()
            
            # Encrypt the data
            f = Fernet(self.symmetric_key)
            return f.encrypt(data)
        
        except Exception as e:
            logger.error(f"Symmetric encryption error: {str(e)}")
            return None
    
    def decrypt_symmetric(self, encrypted_data: bytes) -> Optional[bytes]:
        """
        Decrypt data using symmetric encryption
        
        Args:
            encrypted_data: Encrypted data
            
        Returns:
            bytes: Decrypted data or None if decryption failed
        """
        if not CRYPTO_AVAILABLE or self.symmetric_key is None:
            logger.warning("Symmetric decryption not available. Assuming base64 encoding.")
            try:
                return base64.b64decode(encrypted_data)
            except:
                return None
        
        try:
            # Decrypt the data
            f = Fernet(self.symmetric_key)
            return f.decrypt(encrypted_data)
        
        except Exception as e:
            logger.error(f"Symmetric decryption error: {str(e)}")
            try:
                # Fallback to base64 if decryption fails
                return base64.b64decode(encrypted_data)
            except:
                return None
    
    def encrypt_asymmetric(self, data: Union[str, bytes]) -> Optional[bytes]:
        """
        Encrypt data using asymmetric encryption (RSA)
        
        Args:
            data: Data to encrypt (string or bytes)
            
        Returns:
            bytes: Encrypted data or None if encryption failed
        """
        if not CRYPTO_AVAILABLE or not self.rsa_keys:
            logger.warning("Asymmetric encryption not available. Using base64 encoding only.")
            if isinstance(data, str):
                return base64.b64encode(data.encode())
            return base64.b64encode(data)
        
        try:
            # Convert string to bytes if needed
            if isinstance(data, str):
                data = data.encode()
            
            # RSA can only encrypt small amounts of data, so we'll use a hybrid approach:
            # 1. Generate a random symmetric key
            # 2. Encrypt the data with the symmetric key
            # 3. Encrypt the symmetric key with RSA
            # 4. Combine the encrypted key and data
            
            # Generate a random symmetric key
            sym_key = Fernet.generate_key()
            f = Fernet(sym_key)
            
            # Encrypt the data with the symmetric key
            encrypted_data = f.encrypt(data)
            
            # Encrypt the symmetric key with RSA
            public_key = self.rsa_keys["public_key"]
            encrypted_key = public_key.encrypt(
                sym_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            # Combine the encrypted key and data
            # Format: [key_size (4 bytes)][encrypted_key][encrypted_data]
            key_size = len(encrypted_key).to_bytes(4, byteorder='big')
            return key_size + encrypted_key + encrypted_data
        
        except Exception as e:
            logger.error(f"Asymmetric encryption error: {str(e)}")
            return None
    
    def decrypt_asymmetric(self, encrypted_data: bytes) -> Optional[bytes]:
        """
        Decrypt data using asymmetric encryption (RSA)
        
        Args:
            encrypted_data: Encrypted data
            
        Returns:
            bytes: Decrypted data or None if decryption failed
        """
        if not CRYPTO_AVAILABLE or not self.rsa_keys:
            logger.warning("Asymmetric decryption not available. Assuming base64 encoding.")
            try:
                return base64.b64decode(encrypted_data)
            except:
                return None
        
        try:
            # Parse the encrypted data
            # Format: [key_size (4 bytes)][encrypted_key][encrypted_data]
            key_size = int.from_bytes(encrypted_data[:4], byteorder='big')
            encrypted_key = encrypted_data[4:4+key_size]
            encrypted_data = encrypted_data[4+key_size:]
            
            # Decrypt the symmetric key with RSA
            private_key = self.rsa_keys["private_key"]
            sym_key = private_key.decrypt(
                encrypted_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            # Decrypt the data with the symmetric key
            f = Fernet(sym_key)
            return f.decrypt(encrypted_data)
        
        except Exception as e:
            logger.error(f"Asymmetric decryption error: {str(e)}")
            try:
                # Fallback to base64 if decryption fails
                return base64.b64decode(encrypted_data)
            except:
                return None
    
    def hash_data(self, data: Union[str, bytes], salt: Optional[bytes] = None) -> str:
        """
        Create a secure hash of data
        
        Args:
            data: Data to hash
            salt: Optional salt (generates random salt if None)
            
        Returns:
            str: Salted hash in format 'algorithm$salt$hash'
        """
        # Convert string to bytes if needed
        if isinstance(data, str):
            data = data.encode()
        
        # Generate salt if not provided
        if salt is None:
            salt = os.urandom(16)
        
        # Hash the data with salt
        h = hashlib.sha256()
        h.update(salt)
        h.update(data)
        hash_value = h.hexdigest()
        
        # Format: algorithm$salt$hash
        return f"sha256${base64.b64encode(salt).decode()}${hash_value}"
    
    def verify_hash(self, data: Union[str, bytes], hash_string: str) -> bool:
        """
        Verify data against a hash
        
        Args:
            data: Data to verify
            hash_string: Hash string in format 'algorithm$salt$hash'
            
        Returns:
            bool: True if hash matches, False otherwise
        """
        try:
            # Parse the hash string
            parts = hash_string.split('$')
            if len(parts) != 3:
                return False
            
            algorithm, salt_b64, hash_value = parts
            
            if algorithm != 'sha256':
                logger.warning(f"Unsupported hash algorithm: {algorithm}")
                return False
            
            # Decode the salt
            salt = base64.b64decode(salt_b64)
            
            # Create a new hash with the same salt
            new_hash = self.hash_data(data, salt)
            
            # Compare the hashes
            return new_hash == hash_string
        
        except Exception as e:
            logger.error(f"Hash verification error: {str(e)}")
            return False


class SensitiveDataHandler:
    """Class for handling sensitive data with encryption"""
    
    def __init__(self, encryption_manager: Optional[EncryptionManager] = None,
                 app_name: str = 'stopsale'):
        """
        Initialize the sensitive data handler
        
        Args:
            encryption_manager: EncryptionManager instance (creates new one if None)
            app_name: Application name for namespacing
        """
        self.encryption_manager = encryption_manager or EncryptionManager(app_name=app_name)
    
    def encrypt_field(self, value: str, use_asymmetric: bool = False) -> str:
        """
        Encrypt a field value
        
        Args:
            value: Value to encrypt
            use_asymmetric: Whether to use asymmetric encryption
            
        Returns:
            str: Base64-encoded encrypted value
        """
        if not value:
            return ""
        
        try:
            if use_asymmetric:
                encrypted = self.encryption_manager.encrypt_asymmetric(value)
            else:
                encrypted = self.encryption_manager.encrypt_symmetric(value)
            
            if encrypted is None:
                logger.error("Encryption failed")
                return ""
            
            return base64.b64encode(encrypted).decode()
        
        except Exception as e:
            logger.error(f"Field encryption error: {str(e)}")
            return ""
    
    def decrypt_field(self, encrypted_value: str, use_asymmetric: bool = False) -> str:
        """
        Decrypt a field value
        
        Args:
            encrypted_value: Base64-encoded encrypted value
            use_asymmetric: Whether to use asymmetric encryption
            
        Returns:
            str: Decrypted value
        """
        if not encrypted_value:
            return ""
        
        try:
            encrypted = base64.b64decode(encrypted_value)
            
            if use_asymmetric:
                decrypted = self.encryption_manager.decrypt_asymmetric(encrypted)
            else:
                decrypted = self.encryption_manager.decrypt_symmetric(encrypted)
            
            if decrypted is None:
                logger.error("Decryption failed")
                return ""
            
            return decrypted.decode()
        
        except Exception as e:
            logger.error(f"Field decryption error: {str(e)}")
            return ""
    
    def encrypt_json(self, data: Dict[str, Any], sensitive_fields: List[str]) -> Dict[str, Any]:
        """
        Encrypt sensitive fields in a JSON object
        
        Args:
            data: JSON data
            sensitive_fields: List of field names to encrypt
            
        Returns:
            dict: JSON data with encrypted fields
        """
        if not data:
            return {}
        
        result = data.copy()
        
        for field in sensitive_fields:
            if field in result and result[field]:
                # Mark encrypted fields with a prefix
                result[f"{field}_encrypted"] = self.encrypt_field(str(result[field]))
                del result[field]
        
        return result
    
    def decrypt_json(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decrypt sensitive fields in a JSON object
        
        Args:
            data: JSON data with encrypted fields
            
        Returns:
            dict: JSON data with decrypted fields
        """
        if not data:
            return {}
        
        result = data.copy()
        
        # Find all encrypted fields
        encrypted_fields = [f for f in result.keys() if f.endswith('_encrypted')]
        
        for field in encrypted_fields:
            # Get the original field name
            original_field = field[:-10]  # Remove '_encrypted' suffix
            
            # Decrypt the field
            result[original_field] = self.decrypt_field(result[field])
            del result[field]
        
        return result
    
    def hash_password(self, password: str) -> str:
        """
        Create a secure hash of a password
        
        Args:
            password: Password to hash
            
        Returns:
            str: Salted password hash
        """
        return self.encryption_manager.hash_data(password)
    
    def verify_password(self, password: str, hash_string: str) -> bool:
        """
        Verify a password against a hash
        
        Args:
            password: Password to verify
            hash_string: Hash string
            
        Returns:
            bool: True if password matches, False otherwise
        """
        return self.encryption_manager.verify_hash(password, hash_string)


def install_dependencies():
    """Install required dependencies if not already installed"""
    try:
        import pip
        
        # Check and install dependencies
        if not CRYPTO_AVAILABLE:
            print("Installing cryptography...")
            pip.main(['install', 'cryptography'])
        
        print("Dependencies installed successfully.")
        
    except Exception as e:
        print(f"Error installing dependencies: {str(e)}")


# Django integration
def setup_django_field_encryption():
    """
    Set up Django model field encryption
    
    Returns:
        str: Setup instructions
    """
    instructions = """
    # Create a custom encrypted field for Django models:
    
    from django.db import models
    from sensitive_data_encryption import SensitiveDataHandler
    
    class EncryptedTextField(models.TextField):
        description = "TextField that encrypts values before storing them"
        
        def __init__(self, *args, **kwargs):
            self.handler = SensitiveDataHandler()
            super().__init__(*args, **kwargs)
        
        def from_db_value(self, value, expression, connection):
            if value is None:
                return value
            return self.handler.decrypt_field(value)
        
        def to_python(self, value):
            if value is None:
                return value
            # If the value is already decrypted, return it
            if not isinstance(value, str) or not value.startswith('gAAAAA'):
                return value
            return self.handler.decrypt_field(value)
        
        def get_prep_value(self, value):
            if value is None:
                return value
            return self.handler.encrypt_field(str(value))
    
    
    # Use the encrypted field in your models:
    
    class User(models.Model):
        username = models.CharField(max_length=100)
        email = EncryptedTextField()
        phone = EncryptedTextField(null=True, blank=True)
    """
    return instructions


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    print("Sensitive Data Encryption Module")
    print("-------------------------------")
    print("This module provides encryption and secure handling of sensitive data.")
    
    # Check if cryptography is installed
    if not CRYPTO_AVAILABLE:
        print("\ncryptography not installed.")
        install = input("Do you want to install it? (y/n): ")
        if install.lower() == 'y':
            install_dependencies()
    
    # Example usage
    print("\nExample usage:")
    
    # Initialize encryption manager
    encryption_manager = EncryptionManager()
    
    # Initialize sensitive data handler
    handler = SensitiveDataHandler(encryption_manager)
    
    # Example data
    sensitive_data = {
        "name": "John Doe",
        "email": "john.doe@example.com",
        "ssn": "123-45-6789",
        "credit_card": "4111-1111-1111-1111"
    }
    
    print(f"Original data: {sensitive_data}")
    
    # Encrypt sensitive fields
    encrypted_data = handler.encrypt_json(
        sensitive_data, 
        sensitive_fields=["email", "ssn", "credit_card"]
    )
    
    print(f"Encrypted data: {encrypted_data}")
    
    # Decrypt data
    decrypted_data = handler.decrypt_json(encrypted_data)
    
    print(f"Decrypted data: {decrypted_data}")
    
    # Password hashing
    password = "secure_password123"
    password_hash = handler.hash_password(password)
    
    print(f"Password hash: {password_hash}")
    
    # Verify password
    is_valid = handler.verify_password(password, password_hash)
    print(f"Password verification: {is_valid}")
    
    # Django integration
    print("\nDjango integration:")
    print(setup_django_field_encryption())
