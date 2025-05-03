"""
Authentication and Authorization Module for StopSale Automation System

This module provides enhanced authentication and authorization capabilities
with role-based access control, secure session management, and audit logging.
"""

import os
import json
import uuid
import logging
import hashlib
import secrets
import time
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime, timedelta

# Set up logging
logger = logging.getLogger(__name__)

# Import sensitive data encryption module
try:
    from sensitive_data_encryption import SensitiveDataHandler
    ENCRYPTION_AVAILABLE = True
except ImportError:
    ENCRYPTION_AVAILABLE = False
    logger.warning("Sensitive data encryption module not available. Some security features will be limited.")


class Role:
    """Class representing a user role with permissions"""
    
    def __init__(self, name: str, description: str = "", permissions: Optional[List[str]] = None):
        """
        Initialize a role
        
        Args:
            name: Role name
            description: Role description
            permissions: List of permission codes
        """
        self.name = name
        self.description = description
        self.permissions = permissions or []
    
    def has_permission(self, permission: str) -> bool:
        """
        Check if the role has a specific permission
        
        Args:
            permission: Permission code to check
            
        Returns:
            bool: True if the role has the permission, False otherwise
        """
        # Special case: admin role has all permissions
        if self.name == "admin" or "*" in self.permissions:
            return True
        
        return permission in self.permissions
    
    def add_permission(self, permission: str) -> bool:
        """
        Add a permission to the role
        
        Args:
            permission: Permission code to add
            
        Returns:
            bool: True if the permission was added, False if it already exists
        """
        if permission in self.permissions:
            return False
        
        self.permissions.append(permission)
        return True
    
    def remove_permission(self, permission: str) -> bool:
        """
        Remove a permission from the role
        
        Args:
            permission: Permission code to remove
            
        Returns:
            bool: True if the permission was removed, False if it doesn't exist
        """
        if permission not in self.permissions:
            return False
        
        self.permissions.remove(permission)
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary
        
        Returns:
            dict: Dictionary representation
        """
        return {
            "name": self.name,
            "description": self.description,
            "permissions": self.permissions
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Role':
        """
        Create from dictionary
        
        Args:
            data: Dictionary data
            
        Returns:
            Role: New instance
        """
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            permissions=data.get("permissions", [])
        )


class User:
    """Class representing a user with authentication and role information"""
    
    def __init__(self, username: str, email: str, password_hash: str = "",
                 full_name: str = "", roles: Optional[List[str]] = None,
                 is_active: bool = True, last_login: Optional[datetime] = None):
        """
        Initialize a user
        
        Args:
            username: Username
            email: Email address
            password_hash: Hashed password
            full_name: Full name
            roles: List of role names
            is_active: Whether the user is active
            last_login: Last login timestamp
        """
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.full_name = full_name
        self.roles = roles or ["user"]  # Default role
        self.is_active = is_active
        self.last_login = last_login
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.failed_login_attempts = 0
        self.locked_until = None
    
    def has_role(self, role_name: str) -> bool:
        """
        Check if the user has a specific role
        
        Args:
            role_name: Role name to check
            
        Returns:
            bool: True if the user has the role, False otherwise
        """
        return role_name in self.roles
    
    def add_role(self, role_name: str) -> bool:
        """
        Add a role to the user
        
        Args:
            role_name: Role name to add
            
        Returns:
            bool: True if the role was added, False if it already exists
        """
        if role_name in self.roles:
            return False
        
        self.roles.append(role_name)
        self.updated_at = datetime.now()
        return True
    
    def remove_role(self, role_name: str) -> bool:
        """
        Remove a role from the user
        
        Args:
            role_name: Role name to remove
            
        Returns:
            bool: True if the role was removed, False if it doesn't exist
        """
        if role_name not in self.roles:
            return False
        
        self.roles.remove(role_name)
        self.updated_at = datetime.now()
        return True
    
    def record_login(self, success: bool = True) -> None:
        """
        Record a login attempt
        
        Args:
            success: Whether the login was successful
        """
        if success:
            self.last_login = datetime.now()
            self.failed_login_attempts = 0
            self.locked_until = None
        else:
            self.failed_login_attempts += 1
            
            # Lock account after 5 failed attempts
            if self.failed_login_attempts >= 5:
                # Lock for 30 minutes
                self.locked_until = datetime.now() + timedelta(minutes=30)
        
        self.updated_at = datetime.now()
    
    def is_locked(self) -> bool:
        """
        Check if the user account is locked
        
        Returns:
            bool: True if the account is locked, False otherwise
        """
        if self.locked_until is None:
            return False
        
        return datetime.now() < self.locked_until
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary
        
        Returns:
            dict: Dictionary representation
        """
        return {
            "username": self.username,
            "email": self.email,
            "password_hash": self.password_hash,
            "full_name": self.full_name,
            "roles": self.roles,
            "is_active": self.is_active,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "failed_login_attempts": self.failed_login_attempts,
            "locked_until": self.locked_until.isoformat() if self.locked_until else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        """
        Create from dictionary
        
        Args:
            data: Dictionary data
            
        Returns:
            User: New instance
        """
        user = cls(
            username=data["username"],
            email=data["email"],
            password_hash=data["password_hash"],
            full_name=data.get("full_name", ""),
            roles=data.get("roles", ["user"]),
            is_active=data.get("is_active", True)
        )
        
        if data.get("last_login"):
            user.last_login = datetime.fromisoformat(data["last_login"])
        
        if data.get("created_at"):
            user.created_at = datetime.fromisoformat(data["created_at"])
        
        if data.get("updated_at"):
            user.updated_at = datetime.fromisoformat(data["updated_at"])
        
        user.failed_login_attempts = data.get("failed_login_attempts", 0)
        
        if data.get("locked_until"):
            user.locked_until = datetime.fromisoformat(data["locked_until"])
        
        return user


class Session:
    """Class representing a user session"""
    
    def __init__(self, user_id: str, token: Optional[str] = None,
                 expires_at: Optional[datetime] = None, ip_address: str = "",
                 user_agent: str = ""):
        """
        Initialize a session
        
        Args:
            user_id: User identifier
            token: Session token (generates new one if None)
            expires_at: Expiration timestamp (defaults to 24 hours)
            ip_address: Client IP address
            user_agent: Client user agent
        """
        self.user_id = user_id
        self.token = token or self._generate_token()
        self.created_at = datetime.now()
        self.expires_at = expires_at or (datetime.now() + timedelta(hours=24))
        self.last_activity = datetime.now()
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.data = {}  # Additional session data
    
    def _generate_token(self) -> str:
        """
        Generate a secure session token
        
        Returns:
            str: Session token
        """
        return secrets.token_urlsafe(32)
    
    def is_valid(self) -> bool:
        """
        Check if the session is valid (not expired)
        
        Returns:
            bool: True if valid, False otherwise
        """
        return datetime.now() < self.expires_at
    
    def extend(self, hours: int = 24) -> None:
        """
        Extend the session expiration
        
        Args:
            hours: Number of hours to extend
        """
        self.expires_at = datetime.now() + timedelta(hours=hours)
    
    def update_activity(self) -> None:
        """Update the last activity timestamp"""
        self.last_activity = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary
        
        Returns:
            dict: Dictionary representation
        """
        return {
            "user_id": self.user_id,
            "token": self.token,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "data": self.data
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Session':
        """
        Create from dictionary
        
        Args:
            data: Dictionary data
            
        Returns:
            Session: New instance
        """
        session = cls(
            user_id=data["user_id"],
            token=data["token"],
            ip_address=data.get("ip_address", ""),
            user_agent=data.get("user_agent", "")
        )
        
        session.created_at = datetime.fromisoformat(data["created_at"])
        session.expires_at = datetime.fromisoformat(data["expires_at"])
        session.last_activity = datetime.fromisoformat(data["last_activity"])
        session.data = data.get("data", {})
        
        return session


class AuditLog:
    """Class representing an audit log entry"""
    
    def __init__(self, action: str, user_id: str, timestamp: Optional[datetime] = None,
                 ip_address: str = "", details: Optional[Dict[str, Any]] = None,
                 status: str = "success"):
        """
        Initialize an audit log entry
        
        Args:
            action: Action performed
            user_id: User identifier
            timestamp: Timestamp (defaults to now)
            ip_address: Client IP address
            details: Additional details
            status: Action status (success, failure, etc.)
        """
        self.id = str(uuid.uuid4())
        self.action = action
        self.user_id = user_id
        self.timestamp = timestamp or datetime.now()
        self.ip_address = ip_address
        self.details = details or {}
        self.status = status
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary
        
        Returns:
            dict: Dictionary representation
        """
        return {
            "id": self.id,
            "action": self.action,
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat(),
            "ip_address": self.ip_address,
            "details": self.details,
            "status": self.status
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuditLog':
        """
        Create from dictionary
        
        Args:
            data: Dictionary data
            
        Returns:
            AuditLog: New instance
        """
        log = cls(
            action=data["action"],
            user_id=data["user_id"],
            ip_address=data.get("ip_address", ""),
            details=data.get("details", {}),
            status=data.get("status", "success")
        )
        
        log.id = data["id"]
        log.timestamp = datetime.fromisoformat(data["timestamp"])
        
        return log


class AuthManager:
    """Main authentication and authorization manager"""
    
    def __init__(self, storage_dir: Optional[str] = None, app_name: str = 'stopsale'):
        """
        Initialize the auth manager
        
        Args:
            storage_dir: Directory to store auth data (if None, uses ~/.{app_name}/auth/)
            app_name: Application name for namespacing
        """
        self.app_name = app_name
        
        # Set up storage directory
        if storage_dir is None:
            home_dir = os.path.expanduser("~")
            app_dir = os.path.join(home_dir, f".{app_name}")
            self.storage_dir = os.path.join(app_dir, "auth")
        else:
            self.storage_dir = storage_dir
        
        os.makedirs(self.storage_dir, exist_ok=True)
        
        # Set up file paths
        self.users_file = os.path.join(self.storage_dir, "users.json")
        self.roles_file = os.path.join(self.storage_dir, "roles.json")
        self.sessions_file = os.path.join(self.storage_dir, "sessions.json")
        self.audit_log_file = os.path.join(self.storage_dir, "audit_log.json")
        
        # Initialize data
        self.users = self._load_users()
        self.roles = self._load_roles()
        self.sessions = self._load_sessions()
        
        # Initialize sensitive data handler if available
        self.sensitive_data_handler = None
        if ENCRYPTION_AVAILABLE:
            try:
                self.sensitive_data_handler = SensitiveDataHandler()
                logger.info("Initialized sensitive data handler for secure password storage")
            except Exception as e:
                logger.error(f"Error initializing sensitive data handler: {str(e)}")
        
        # Create default roles if they don't exist
        self._create_default_roles()
    
    def _load_users(self) -> Dict[str, User]:
        """
        Load users from storage
        
        Returns:
            dict: Dictionary of users
        """
        if not os.path.exists(self.users_file):
            return {}
        
        try:
            with open(self.users_file, 'r') as f:
                data = json.load(f)
            
            users = {}
            for username, user_data in data.items():
                users[username] = User.from_dict(user_data)
            
            return users
        
        except Exception as e:
            logger.error(f"Error loading users: {str(e)}")
            return {}
    
    def _save_users(self) -> bool:
        """
        Save users to storage
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            data = {username: user.to_dict() for username, user in self.users.items()}
            
            with open(self.users_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Set secure permissions
            os.chmod(self.users_file, 0o600)
            
            return True
        
        except Exception as e:
            logger.error(f"Error saving users: {str(e)}")
            return False
    
    def _load_roles(self) -> Dict[str, Role]:
        """
        Load roles from storage
        
        Returns:
            dict: Dictionary of roles
        """
        if not os.path.exists(self.roles_file):
            return {}
        
        try:
            with open(self.roles_file, 'r') as f:
                data = json.load(f)
            
            roles = {}
            for role_name, role_data in data.items():
                roles[role_name] = Role.from_dict(role_data)
            
            return roles
        
        except Exception as e:
            logger.error(f"Error loading roles: {str(e)}")
            return {}
    
    def _save_roles(self) -> bool:
        """
        Save roles to storage
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            data = {role_name: role.to_dict() for role_name, role in self.roles.items()}
            
            with open(self.roles_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True
        
        except Exception as e:
            logger.error(f"Error saving roles: {str(e)}")
            return False
    
    def _load_sessions(self) -> Dict[str, Session]:
        """
        Load sessions from storage
        
        Returns:
            dict: Dictionary of sessions
        """
        if not os.path.exists(self.sessions_file):
            return {}
        
        try:
            with open(self.sessions_file, 'r') as f:
                data = json.load(f)
            
            sessions = {}
            for token, session_data in data.items():
                session = Session.from_dict(session_data)
                # Only load valid sessions
                if session.is_valid():
                    sessions[token] = session
            
            return sessions
        
        except Exception as e:
            logger.error(f"Error loading sessions: {str(e)}")
            return {}
    
    def _save_sessions(self) -> bool:
        """
        Save sessions to storage
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Only save valid sessions
            valid_sessions = {token: session for token, session in self.sessions.items() if session.is_valid()}
            data = {token: session.to_dict() for token, session in valid_sessions.items()}
            
            with open(self.sessions_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Set secure permissions
            os.chmod(self.sessions_file, 0o600)
            
            return True
        
        except Exception as e:
            logger.error(f"Error saving sessions: {str(e)}")
            return False
    
    def _create_default_roles(self) -> None:
        """Create default roles if they don't exist"""
        # Admin role
        if "admin" not in self.roles:
            admin_role = Role(
                name="admin",
                description="Administrator with full access",
                permissions=["*"]  # Wildcard for all permissions
            )
            self.roles["admin"] = admin_role
        
        # User role
        if "user" not in self.roles:
            user_role = Role(
                name="user",
                description="Regular user",
                permissions=[
                    "view_dashboard",
                    "view_hotels",
                    "view_emails",
                    "process_emails"
                ]
            )
            self.roles["user"] = user_role
        
        # Manager role
        if "manager" not in self.roles:
            manager_role = Role(
                name="manager",
                description="Hotel manager",
                permissions=[
                    "view_dashboard",
                    "view_hotels",
                    "edit_hotels",
                    "view_emails",
                    "process_emails",
                    "view_reports"
                ]
            )
            self.roles["manager"] = manager_role
        
        # Save roles
        self._save_roles()
    
    def _hash_password(self, password: str) -> str:
        """
        Hash a password
        
        Args:
            password: Password to hash
            
        Returns:
            str: Password hash
        """
        if self.sensitive_data_handler:
            return self.sensitive_data_handler.hash_password(password)
        
        # Fallback to simple hashing if sensitive data handler is not available
        salt = os.urandom(16)
        hash_obj = hashlib.sha256()
        hash_obj.update(salt)
        hash_obj.update(password.encode())
        hash_value = hash_obj.hexdigest()
        
        # Format: algorithm$salt$hash
        return f"sha256${base64.b64encode(salt).decode()}${hash_value}"
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """
        Verify a password against a hash
        
        Args:
            password: Password to verify
            password_hash: Password hash
            
        Returns:
            bool: True if password matches, False otherwise
        """
        if self.sensitive_data_handler:
            return self.sensitive_data_handler.verify_password(password, password_hash)
        
        # Fallback to simple verification if sensitive data handler is not available
        try:
            # Parse the hash string
            parts = password_hash.split('$')
            if len(parts) != 3:
                return False
            
            algorithm, salt_b64, hash_value = parts
            
            if algorithm != 'sha256':
                logger.warning(f"Unsupported hash algorithm: {algorithm}")
                return False
            
            # Decode the salt
            salt = base64.b64decode(salt_b64)
            
            # Create a new hash with the same salt
            hash_obj = hashlib.sha256()
            hash_obj.update(salt)
            hash_obj.update(password.encode())
            new_hash = hash_obj.hexdigest()
            
            # Compare the hashes
            return new_hash == hash_value
        
        except Exception as e:
            logger.error(f"Password verification error: {str(e)}")
            return False
    
    def _log_audit(self, action: str, user_id: str, ip_address: str = "",
                  details: Optional[Dict[str, Any]] = None, status: str = "success") -> None:
        """
        Log an audit event
        
        Args:
            action: Action performed
            user_id: User identifier
            ip_address: Client IP address
            details: Additional details
            status: Action status
        """
        try:
            log_entry = AuditLog(
                action=action,
                user_id=user_id,
                ip_address=ip_address,
                details=details,
                status=status
            )
            
            # Append to log file
            with open(self.audit_log_file, 'a') as f:
                f.write(json.dumps(log_entry.to_dict()) + "\n")
        
        except Exception as e:
            logger.error(f"Error logging audit event: {str(e)}")
    
    def create_user(self, username: str, email: str, password: str,
                   full_name: str = "", roles: Optional[List[str]] = None) -> bool:
        """
        Create a new user
        
        Args:
            username: Username
            email: Email address
            password: Password
            full_name: Full name
            roles: List of role names
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Check if username already exists
        if username in self.users:
            logger.warning(f"User {username} already exists")
            return False
        
        # Validate roles
        if roles:
            for role in roles:
                if role not in self.roles:
                    logger.warning(f"Role {role} does not exist")
                    return False
        
        # Hash the password
        password_hash = self._hash_password(password)
        
        # Create the user
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            roles=roles
        )
        
        # Add to users dictionary
        self.users[username] = user
        
        # Save users
        success = self._save_users()
        
        if success:
            self._log_audit(
                action="create_user",
                user_id="system",
                details={"username": username}
            )
        
        return success
    
    def update_user(self, username: str, email: Optional[str] = None,
                   full_name: Optional[str] = None, is_active: Optional[bool] = None) -> bool:
        """
        Update a user
        
        Args:
            username: Username
            email: New email address
            full_name: New full name
            is_active: New active status
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Check if user exists
        if username not in self.users:
            logger.warning(f"User {username} does not exist")
            return False
        
        user = self.users[username]
        
        # Update fields
        if email is not None:
            user.email = email
        
        if full_name is not None:
            user.full_name = full_name
        
        if is_active is not None:
            user.is_active = is_active
        
        user.updated_at = datetime.now()
        
        # Save users
        success = self._save_users()
        
        if success:
            self._log_audit(
                action="update_user",
                user_id="system",
                details={"username": username}
            )
        
        return success
    
    def delete_user(self, username: str) -> bool:
        """
        Delete a user
        
        Args:
            username: Username
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Check if user exists
        if username not in self.users:
            logger.warning(f"User {username} does not exist")
            return False
        
        # Remove from users dictionary
        del self.users[username]
        
        # Save users
        success = self._save_users()
        
        if success:
            # Remove user sessions
            self._remove_user_sessions(username)
            
            self._log_audit(
                action="delete_user",
                user_id="system",
                details={"username": username}
            )
        
        return success
    
    def _remove_user_sessions(self, username: str) -> None:
        """
        Remove all sessions for a user
        
        Args:
            username: Username
        """
        # Find sessions for the user
        tokens_to_remove = []
        for token, session in self.sessions.items():
            if session.user_id == username:
                tokens_to_remove.append(token)
        
        # Remove sessions
        for token in tokens_to_remove:
            del self.sessions[token]
        
        # Save sessions
        self._save_sessions()
    
    def change_password(self, username: str, new_password: str) -> bool:
        """
        Change a user's password
        
        Args:
            username: Username
            new_password: New password
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Check if user exists
        if username not in self.users:
            logger.warning(f"User {username} does not exist")
            return False
        
        user = self.users[username]
        
        # Hash the new password
        password_hash = self._hash_password(new_password)
        
        # Update the password hash
        user.password_hash = password_hash
        user.updated_at = datetime.now()
        
        # Save users
        success = self._save_users()
        
        if success:
            # Remove user sessions (force re-login)
            self._remove_user_sessions(username)
            
            self._log_audit(
                action="change_password",
                user_id=username,
                details={"username": username}
            )
        
        return success
    
    def authenticate(self, username: str, password: str, ip_address: str = "",
                    user_agent: str = "") -> Optional[str]:
        """
        Authenticate a user
        
        Args:
            username: Username
            password: Password
            ip_address: Client IP address
            user_agent: Client user agent
            
        Returns:
            str: Session token if successful, None otherwise
        """
        # Check if user exists
        if username not in self.users:
            logger.warning(f"Authentication failed: User {username} does not exist")
            self._log_audit(
                action="authenticate",
                user_id=username,
                ip_address=ip_address,
                status="failure",
                details={"reason": "user_not_found"}
            )
            return None
        
        user = self.users[username]
        
        # Check if user is active
        if not user.is_active:
            logger.warning(f"Authentication failed: User {username} is not active")
            self._log_audit(
                action="authenticate",
                user_id=username,
                ip_address=ip_address,
                status="failure",
                details={"reason": "user_inactive"}
            )
            return None
        
        # Check if account is locked
        if user.is_locked():
            logger.warning(f"Authentication failed: User {username} is locked")
            self._log_audit(
                action="authenticate",
                user_id=username,
                ip_address=ip_address,
                status="failure",
                details={"reason": "account_locked"}
            )
            return None
        
        # Verify password
        if not self._verify_password(password, user.password_hash):
            logger.warning(f"Authentication failed: Invalid password for user {username}")
            
            # Record failed login
            user.record_login(success=False)
            self._save_users()
            
            self._log_audit(
                action="authenticate",
                user_id=username,
                ip_address=ip_address,
                status="failure",
                details={"reason": "invalid_password"}
            )
            
            return None
        
        # Record successful login
        user.record_login(success=True)
        self._save_users()
        
        # Create session
        session = Session(
            user_id=username,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Add to sessions dictionary
        self.sessions[session.token] = session
        
        # Save sessions
        self._save_sessions()
        
        self._log_audit(
            action="authenticate",
            user_id=username,
            ip_address=ip_address,
            status="success"
        )
        
        return session.token
    
    def validate_session(self, token: str, update_activity: bool = True) -> Optional[str]:
        """
        Validate a session
        
        Args:
            token: Session token
            update_activity: Whether to update the last activity timestamp
            
        Returns:
            str: Username if session is valid, None otherwise
        """
        # Check if session exists
        if token not in self.sessions:
            return None
        
        session = self.sessions[token]
        
        # Check if session is valid
        if not session.is_valid():
            # Remove expired session
            del self.sessions[token]
            self._save_sessions()
            return None
        
        # Update activity if requested
        if update_activity:
            session.update_activity()
            self._save_sessions()
        
        return session.user_id
    
    def logout(self, token: str) -> bool:
        """
        Log out a user session
        
        Args:
            token: Session token
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Check if session exists
        if token not in self.sessions:
            return False
        
        # Get user ID before removing session
        user_id = self.sessions[token].user_id
        
        # Remove session
        del self.sessions[token]
        
        # Save sessions
        success = self._save_sessions()
        
        if success:
            self._log_audit(
                action="logout",
                user_id=user_id
            )
        
        return success
    
    def create_role(self, name: str, description: str = "",
                   permissions: Optional[List[str]] = None) -> bool:
        """
        Create a new role
        
        Args:
            name: Role name
            description: Role description
            permissions: List of permission codes
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Check if role already exists
        if name in self.roles:
            logger.warning(f"Role {name} already exists")
            return False
        
        # Create the role
        role = Role(
            name=name,
            description=description,
            permissions=permissions
        )
        
        # Add to roles dictionary
        self.roles[name] = role
        
        # Save roles
        success = self._save_roles()
        
        if success:
            self._log_audit(
                action="create_role",
                user_id="system",
                details={"role": name}
            )
        
        return success
    
    def update_role(self, name: str, description: Optional[str] = None,
                   permissions: Optional[List[str]] = None) -> bool:
        """
        Update a role
        
        Args:
            name: Role name
            description: New role description
            permissions: New list of permission codes
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Check if role exists
        if name not in self.roles:
            logger.warning(f"Role {name} does not exist")
            return False
        
        role = self.roles[name]
        
        # Update fields
        if description is not None:
            role.description = description
        
        if permissions is not None:
            role.permissions = permissions
        
        # Save roles
        success = self._save_roles()
        
        if success:
            self._log_audit(
                action="update_role",
                user_id="system",
                details={"role": name}
            )
        
        return success
    
    def delete_role(self, name: str) -> bool:
        """
        Delete a role
        
        Args:
            name: Role name
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Check if role exists
        if name not in self.roles:
            logger.warning(f"Role {name} does not exist")
            return False
        
        # Check if role is in use
        for username, user in self.users.items():
            if name in user.roles:
                logger.warning(f"Cannot delete role {name}: in use by user {username}")
                return False
        
        # Remove from roles dictionary
        del self.roles[name]
        
        # Save roles
        success = self._save_roles()
        
        if success:
            self._log_audit(
                action="delete_role",
                user_id="system",
                details={"role": name}
            )
        
        return success
    
    def has_permission(self, username: str, permission: str) -> bool:
        """
        Check if a user has a specific permission
        
        Args:
            username: Username
            permission: Permission code
            
        Returns:
            bool: True if the user has the permission, False otherwise
        """
        # Check if user exists
        if username not in self.users:
            return False
        
        user = self.users[username]
        
        # Check if user is active
        if not user.is_active:
            return False
        
        # Check user roles
        for role_name in user.roles:
            if role_name in self.roles:
                role = self.roles[role_name]
                if role.has_permission(permission):
                    return True
        
        return False
    
    def get_user_permissions(self, username: str) -> List[str]:
        """
        Get all permissions for a user
        
        Args:
            username: Username
            
        Returns:
            list: List of permission codes
        """
        # Check if user exists
        if username not in self.users:
            return []
        
        user = self.users[username]
        
        # Check if user is active
        if not user.is_active:
            return []
        
        # Collect permissions from all roles
        permissions = set()
        for role_name in user.roles:
            if role_name in self.roles:
                role = self.roles[role_name]
                
                # Special case: admin role or wildcard permission
                if role_name == "admin" or "*" in role.permissions:
                    return ["*"]  # All permissions
                
                permissions.update(role.permissions)
        
        return list(permissions)
    
    def get_audit_logs(self, start_time: Optional[datetime] = None,
                      end_time: Optional[datetime] = None,
                      user_id: Optional[str] = None,
                      action: Optional[str] = None,
                      limit: int = 100) -> List[AuditLog]:
        """
        Get audit logs with optional filtering
        
        Args:
            start_time: Start time filter
            end_time: End time filter
            user_id: User ID filter
            action: Action filter
            limit: Maximum number of logs to return
            
        Returns:
            list: List of audit log entries
        """
        logs = []
        
        try:
            if not os.path.exists(self.audit_log_file):
                return []
            
            with open(self.audit_log_file, 'r') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        log = AuditLog.from_dict(data)
                        
                        # Apply filters
                        if start_time and log.timestamp < start_time:
                            continue
                        
                        if end_time and log.timestamp > end_time:
                            continue
                        
                        if user_id and log.user_id != user_id:
                            continue
                        
                        if action and log.action != action:
                            continue
                        
                        logs.append(log)
                        
                        # Check limit
                        if len(logs) >= limit:
                            break
                    
                    except Exception as e:
                        logger.error(f"Error parsing audit log entry: {str(e)}")
            
            # Sort by timestamp (newest first)
            logs.sort(key=lambda log: log.timestamp, reverse=True)
            
            return logs
        
        except Exception as e:
            logger.error(f"Error reading audit logs: {str(e)}")
            return []


# Django integration
def setup_django_auth_integration():
    """
    Set up Django authentication integration
    
    Returns:
        str: Setup instructions
    """
    instructions = """
    # Create a custom authentication backend for Django:
    
    from django.contrib.auth.backends import BaseBackend
    from django.contrib.auth.models import User
    from auth_manager import AuthManager
    
    class SecureAuthBackend(BaseBackend):
        def authenticate(self, request, username=None, password=None):
            auth_manager = AuthManager()
            
            # Get client info
            ip_address = request.META.get('REMOTE_ADDR', '')
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            
            # Authenticate with our secure system
            token = auth_manager.authenticate(username, password, ip_address, user_agent)
            
            if token:
                # Store token in session
                request.session['auth_token'] = token
                
                # Get or create Django user
                try:
                    user = User.objects.get(username=username)
                except User.DoesNotExist:
                    # Create a Django user that mirrors our secure user
                    secure_user = auth_manager.users.get(username)
                    user = User(username=username, email=secure_user.email)
                    user.is_staff = 'admin' in secure_user.roles
                    user.is_superuser = 'admin' in secure_user.roles
                    user.save()
                
                return user
            
            return None
        
        def get_user(self, user_id):
            try:
                return User.objects.get(pk=user_id)
            except User.DoesNotExist:
                return None
    
    
    # Add the authentication backend to settings.py:
    
    AUTHENTICATION_BACKENDS = [
        'path.to.SecureAuthBackend',
        'django.contrib.auth.backends.ModelBackend',  # Keep the default backend as fallback
    ]
    
    
    # Create a middleware to validate sessions:
    
    from django.contrib.auth import logout
    from django.http import HttpResponseRedirect
    from django.urls import reverse
    
    class SecureSessionMiddleware:
        def __init__(self, get_response):
            self.get_response = get_response
            self.auth_manager = AuthManager()
        
        def __call__(self, request):
            # Check if user is authenticated
            if request.user.is_authenticated:
                # Validate token
                token = request.session.get('auth_token')
                if not token or not self.auth_manager.validate_session(token):
                    # Invalid session, log out
                    logout(request)
                    return HttpResponseRedirect(reverse('login'))
            
            response = self.get_response(request)
            return response
    
    
    # Add the middleware to settings.py:
    
    MIDDLEWARE = [
        # ... other middleware ...
        'path.to.SecureSessionMiddleware',
    ]
    """
    return instructions


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    print("Authentication and Authorization Module")
    print("-------------------------------------")
    print("This module provides enhanced authentication and authorization capabilities.")
    
    # Example usage
    print("\nExample usage:")
    auth_manager = AuthManager()
    
    # Create a user
    if not auth_manager.users:
        print("Creating admin user...")
        auth_manager.create_user(
            username="admin",
            email="admin@example.com",
            password="admin123",  # In production, use a secure password
            full_name="Admin User",
            roles=["admin"]
        )
        print("Admin user created.")
    
    # Authenticate
    username = input("Enter username to authenticate: ")
    password = input("Enter password: ")
    
    token = auth_manager.authenticate(username, password)
    if token:
        print(f"Authentication successful! Token: {token}")
        
        # Check permissions
        permissions = auth_manager.get_user_permissions(username)
        print(f"User permissions: {permissions}")
        
        # Validate session
        valid_user = auth_manager.validate_session(token)
        print(f"Session validation: {valid_user}")
        
        # Logout
        auth_manager.logout(token)
        print("Logged out.")
    else:
        print("Authentication failed.")
    
    # Django integration
    print("\nDjango integration:")
    print(setup_django_auth_integration())
