"""
Secure API Key Management Module for StopSale Automation System

This module provides secure storage and management of API keys and sensitive credentials
using environment variables, encrypted storage, and secure access methods.
"""

import os
import base64
import json
import logging
import getpass
from typing import Dict, Any, Optional, List
from datetime import datetime

# Set up logging
logger = logging.getLogger(__name__)

# Try to import cryptography
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning("cryptography not installed. Secure storage will be limited.")


class ApiKeyManager:
    """Class for securely managing API keys and credentials"""
    
    def __init__(self, app_name: str = 'stopsale', 
                 storage_path: Optional[str] = None,
                 use_env_vars: bool = True):
        """
        Initialize the API key manager
        
        Args:
            app_name: Application name for namespacing
            storage_path: Path to store encrypted keys (if None, uses ~/.{app_name}/keys.enc)
            use_env_vars: Whether to check environment variables first
        """
        self.app_name = app_name
        self.use_env_vars = use_env_vars
        
        # Set up storage path
        if storage_path is None:
            home_dir = os.path.expanduser("~")
            app_dir = os.path.join(home_dir, f".{app_name}")
            os.makedirs(app_dir, exist_ok=True)
            self.storage_path = os.path.join(app_dir, "keys.enc")
        else:
            self.storage_path = storage_path
        
        # Initialize encryption if available
        self.encryption_key = None
        if CRYPTO_AVAILABLE:
            self._init_encryption()
    
    def _init_encryption(self):
        """Initialize encryption with a master password"""
        # Check for existing key file
        key_file = os.path.join(os.path.dirname(self.storage_path), ".key")
        
        if os.path.exists(key_file):
            # Load existing key
            try:
                with open(key_file, 'rb') as f:
                    self.encryption_key = f.read()
            except Exception as e:
                logger.error(f"Error loading encryption key: {str(e)}")
                self.encryption_key = None
        
        # If no key exists or loading failed, generate a new one
        if self.encryption_key is None:
            try:
                # Generate a key from password
                password = os.environ.get(f"{self.app_name.upper()}_MASTER_PASSWORD")
                
                if password is None:
                    # If running interactively, prompt for password
                    if os.isatty(0):
                        password = getpass.getpass("Enter master password for API key encryption: ")
                    else:
                        # Default password for non-interactive environments
                        # This is not secure and should be changed in production
                        password = f"default_{self.app_name}_password"
                        logger.warning("Using default master password. This is not secure!")
                
                # Generate a key from the password
                salt = b'stopsale_salt'  # In production, this should be randomly generated and stored
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=salt,
                    iterations=100000,
                )
                self.encryption_key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
                
                # Save the key
                try:
                    with open(key_file, 'wb') as f:
                        f.write(self.encryption_key)
                    os.chmod(key_file, 0o600)  # Restrict permissions
                except Exception as e:
                    logger.error(f"Error saving encryption key: {str(e)}")
            
            except Exception as e:
                logger.error(f"Error generating encryption key: {str(e)}")
                self.encryption_key = None
    
    def _encrypt(self, data: str) -> bytes:
        """
        Encrypt data
        
        Args:
            data: Data to encrypt
            
        Returns:
            bytes: Encrypted data
        """
        if not CRYPTO_AVAILABLE or self.encryption_key is None:
            logger.warning("Encryption not available. Storing data in base64 encoding only.")
            return base64.b64encode(data.encode())
        
        try:
            f = Fernet(self.encryption_key)
            return f.encrypt(data.encode())
        except Exception as e:
            logger.error(f"Encryption error: {str(e)}")
            return base64.b64encode(data.encode())
    
    def _decrypt(self, data: bytes) -> str:
        """
        Decrypt data
        
        Args:
            data: Data to decrypt
            
        Returns:
            str: Decrypted data
        """
        if not CRYPTO_AVAILABLE or self.encryption_key is None:
            logger.warning("Decryption not available. Assuming base64 encoding.")
            return base64.b64decode(data).decode()
        
        try:
            f = Fernet(self.encryption_key)
            return f.decrypt(data).decode()
        except Exception as e:
            logger.error(f"Decryption error: {str(e)}")
            try:
                # Fallback to base64 if decryption fails
                return base64.b64decode(data).decode()
            except:
                return ""
    
    def _load_keys(self) -> Dict[str, str]:
        """
        Load keys from storage
        
        Returns:
            dict: Dictionary of keys
        """
        if not os.path.exists(self.storage_path):
            return {}
        
        try:
            with open(self.storage_path, 'rb') as f:
                encrypted_data = f.read()
            
            if not encrypted_data:
                return {}
            
            decrypted_data = self._decrypt(encrypted_data)
            return json.loads(decrypted_data)
        
        except Exception as e:
            logger.error(f"Error loading keys: {str(e)}")
            return {}
    
    def _save_keys(self, keys: Dict[str, str]) -> bool:
        """
        Save keys to storage
        
        Args:
            keys: Dictionary of keys
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            encrypted_data = self._encrypt(json.dumps(keys))
            
            with open(self.storage_path, 'wb') as f:
                f.write(encrypted_data)
            
            # Set secure permissions
            os.chmod(self.storage_path, 0o600)
            
            return True
        
        except Exception as e:
            logger.error(f"Error saving keys: {str(e)}")
            return False
    
    def get_key(self, key_name: str) -> Optional[str]:
        """
        Get an API key or credential
        
        Args:
            key_name: Name of the key
            
        Returns:
            str: The key value or None if not found
        """
        # Check environment variables first if enabled
        if self.use_env_vars:
            env_var_name = f"{self.app_name.upper()}_{key_name.upper()}"
            env_value = os.environ.get(env_var_name)
            if env_value:
                return env_value
        
        # Check stored keys
        keys = self._load_keys()
        return keys.get(key_name)
    
    def set_key(self, key_name: str, key_value: str) -> bool:
        """
        Set an API key or credential
        
        Args:
            key_name: Name of the key
            key_value: Value of the key
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Load existing keys
        keys = self._load_keys()
        
        # Update the key
        keys[key_name] = key_value
        
        # Save keys
        return self._save_keys(keys)
    
    def delete_key(self, key_name: str) -> bool:
        """
        Delete an API key or credential
        
        Args:
            key_name: Name of the key
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Load existing keys
        keys = self._load_keys()
        
        # Remove the key if it exists
        if key_name in keys:
            del keys[key_name]
            
            # Save keys
            return self._save_keys(keys)
        
        return True  # Key doesn't exist, so deletion is "successful"
    
    def list_keys(self) -> List[str]:
        """
        List all stored key names
        
        Returns:
            list: List of key names
        """
        keys = self._load_keys()
        return list(keys.keys())
    
    def rotate_key(self, key_name: str, new_value: Optional[str] = None) -> bool:
        """
        Rotate an API key (update its value)
        
        Args:
            key_name: Name of the key
            new_value: New value for the key (if None, prompts user)
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Get the current value
        current_value = self.get_key(key_name)
        
        if current_value is None:
            logger.warning(f"Key {key_name} not found for rotation")
            return False
        
        # If no new value provided and running interactively, prompt user
        if new_value is None and os.isatty(0):
            new_value = getpass.getpass(f"Enter new value for {key_name}: ")
        
        if new_value is None:
            logger.error(f"No new value provided for key {key_name}")
            return False
        
        # Update the key
        return self.set_key(key_name, new_value)


class SecureConfigManager:
    """Class for managing secure configuration settings"""
    
    def __init__(self, app_name: str = 'stopsale', 
                 config_path: Optional[str] = None):
        """
        Initialize the secure config manager
        
        Args:
            app_name: Application name for namespacing
            config_path: Path to store config (if None, uses ~/.{app_name}/config.json)
        """
        self.app_name = app_name
        
        # Set up config path
        if config_path is None:
            home_dir = os.path.expanduser("~")
            app_dir = os.path.join(home_dir, f".{app_name}")
            os.makedirs(app_dir, exist_ok=True)
            self.config_path = os.path.join(app_dir, "config.json")
        else:
            self.config_path = config_path
        
        # Initialize API key manager for sensitive values
        self.key_manager = ApiKeyManager(app_name)
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from file
        
        Returns:
            dict: Configuration dictionary
        """
        if not os.path.exists(self.config_path):
            return {}
        
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading config: {str(e)}")
            return {}
    
    def _save_config(self, config: Dict[str, Any]) -> bool:
        """
        Save configuration to file
        
        Args:
            config: Configuration dictionary
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            # Set secure permissions
            os.chmod(self.config_path, 0o600)
            
            return True
        except Exception as e:
            logger.error(f"Error saving config: {str(e)}")
            return False
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Any: Configuration value
        """
        config = self._load_config()
        
        # Check if this is a sensitive value
        if key.startswith("sensitive."):
            # Get from key manager
            actual_key = key[len("sensitive."):]
            value = self.key_manager.get_key(actual_key)
            return value if value is not None else default
        
        # Regular config value
        return config.get(key, default)
    
    def set_config(self, key: str, value: Any) -> bool:
        """
        Set a configuration value
        
        Args:
            key: Configuration key
            value: Configuration value
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Check if this is a sensitive value
        if key.startswith("sensitive."):
            # Store in key manager
            actual_key = key[len("sensitive."):]
            return self.key_manager.set_key(actual_key, str(value))
        
        # Regular config value
        config = self._load_config()
        config[key] = value
        return self._save_config(config)
    
    def delete_config(self, key: str) -> bool:
        """
        Delete a configuration value
        
        Args:
            key: Configuration key
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Check if this is a sensitive value
        if key.startswith("sensitive."):
            # Delete from key manager
            actual_key = key[len("sensitive."):]
            return self.key_manager.delete_key(actual_key)
        
        # Regular config value
        config = self._load_config()
        if key in config:
            del config[key]
            return self._save_config(config)
        
        return True  # Key doesn't exist, so deletion is "successful"
    
    def list_config_keys(self) -> List[str]:
        """
        List all configuration keys
        
        Returns:
            list: List of configuration keys
        """
        config = self._load_config()
        keys = list(config.keys())
        
        # Add sensitive keys
        sensitive_keys = self.key_manager.list_keys()
        for key in sensitive_keys:
            keys.append(f"sensitive.{key}")
        
        return keys


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
def setup_django_secure_settings():
    """
    Set up secure settings for Django
    
    Returns:
        str: Setup instructions
    """
    instructions = """
    # Add the following to your Django settings.py:
    
    import os
    from secure_api_key_manager import ApiKeyManager
    
    # Initialize API key manager
    key_manager = ApiKeyManager(app_name='stopsale')
    
    # Get sensitive settings from secure storage
    SECRET_KEY = key_manager.get_key('django_secret_key')
    if not SECRET_KEY:
        # Generate a new secret key if not found
        from django.core.management.utils import get_random_secret_key
        SECRET_KEY = get_random_secret_key()
        key_manager.set_key('django_secret_key', SECRET_KEY)
    
    # Database credentials
    DB_PASSWORD = key_manager.get_key('db_password')
    
    # API keys
    CLAUDE_API_KEY = key_manager.get_key('claude_api_key')
    
    # Database settings
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'stopsale',
            'USER': 'stopsale_user',
            'PASSWORD': DB_PASSWORD,
            'HOST': 'localhost',
            'PORT': '5432',
        }
    }
    """
    return instructions


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    print("Secure API Key Management Module")
    print("-------------------------------")
    print("This module provides secure storage and management of API keys and credentials.")
    
    # Check if cryptography is installed
    if not CRYPTO_AVAILABLE:
        print("\ncryptography not installed.")
        install = input("Do you want to install it? (y/n): ")
        if install.lower() == 'y':
            install_dependencies()
    
    # Example usage
    print("\nExample usage:")
    key_manager = ApiKeyManager()
    
    # Set a key
    key_name = input("Enter a key name to store (e.g., 'claude_api_key'): ")
    key_value = getpass.getpass(f"Enter value for {key_name}: ")
    
    if key_manager.set_key(key_name, key_value):
        print(f"Successfully stored {key_name}")
    else:
        print(f"Failed to store {key_name}")
    
    # Get the key
    retrieved_value = key_manager.get_key(key_name)
    if retrieved_value:
        print(f"Successfully retrieved {key_name}")
        show_value = input("Show the value? (y/n): ")
        if show_value.lower() == 'y':
            print(f"Value: {retrieved_value}")
    else:
        print(f"Failed to retrieve {key_name}")
    
    # Django integration
    print("\nDjango integration:")
    print(setup_django_secure_settings())
