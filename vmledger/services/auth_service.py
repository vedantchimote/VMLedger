"""
Authentication Service for user authentication and authorization.

This service implements secure user authentication with bcrypt password hashing,
JWT token generation, rate limiting, and account lockout mechanisms.

Requirements: 10.1-10.6, 14.4
"""

import logging
import re
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
import redis

from vmledger.config import settings
from vmledger.models.user import User
from vmledger.exceptions import (
    AuthServiceError,
    PasswordComplexityError,
    AuthenticationError,
    InvalidCredentialsError,
    AccountLockedError,
    TokenExpiredError,
    TokenInvalidError,
    RateLimitExceededError,
    UserNotFoundError
)


logger = logging.getLogger(__name__)


class AuthService:
    """
    Manages user authentication, authorization, and session management.
    
    Features:
    - Password hashing with bcrypt (cost factor 12)
    - JWT token generation and validation
    - Rate limiting using Redis
    - Account lockout after failed attempts
    - Session token invalidation
    """
    
    def __init__(self, db: Session, redis_client: Optional[redis.Redis] = None):
        """
        Initialize the authentication service.
        
        Args:
            db: SQLAlchemy database session
            redis_client: Redis client for rate limiting and token storage
        """
        self.db = db
        
        # Initialize Redis client
        if redis_client is None:
            self.redis_client = redis.from_url(
                settings.redis_url,
                password=settings.redis_password if settings.redis_password else None,
                decode_responses=True
            )
        else:
            self.redis_client = redis_client
        
        # Initialize password context with bcrypt
        self.pwd_context = CryptContext(
            schemes=["bcrypt"],
            deprecated="auto",
            bcrypt__rounds=12  # Cost factor 12 for bcrypt
        )
    
    def _validate_password_complexity(self, password: str) -> None:
        """
        Validate password meets complexity requirements.
        
        Requirements:
        - Minimum 12 characters
        - Maximum 72 bytes (bcrypt limitation)
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one number
        - At least one special character
        
        Args:
            password: Password to validate
            
        Raises:
            PasswordComplexityError: If password does not meet requirements
            
        Requirements: 10.5 - Enforce password complexity requirements
        """
        if len(password) < settings.password_min_length:
            raise PasswordComplexityError(
                f"Password must be at least {settings.password_min_length} characters long"
            )
        
        # Check bcrypt byte limit (72 bytes)
        password_bytes = len(password.encode('utf-8'))
        if password_bytes > 72:
            raise PasswordComplexityError(
                f"Password is too long ({password_bytes} bytes). Maximum is 72 bytes."
            )
        
        if not re.search(r'[A-Z]', password):
            raise PasswordComplexityError(
                "Password must contain at least one uppercase letter"
            )
        
        if not re.search(r'[a-z]', password):
            raise PasswordComplexityError(
                "Password must contain at least one lowercase letter"
            )
        
        if not re.search(r'\d', password):
            raise PasswordComplexityError(
                "Password must contain at least one number"
            )
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise PasswordComplexityError(
                "Password must contain at least one special character"
            )
    
    def _hash_password(self, password: str) -> str:
        """
        Hash password using bcrypt.
        
        Args:
            password: Plain text password
            
        Returns:
            Bcrypt hashed password
            
        Raises:
            PasswordComplexityError: If password exceeds bcrypt's 72-byte limit
        """
        # Check byte length before hashing (bcrypt limit is 72 bytes)
        password_bytes = len(password.encode('utf-8'))
        logger.info(f"Hashing password - length: {len(password)} chars, {password_bytes} bytes")
        
        if password_bytes > 72:
            raise PasswordComplexityError(
                f"Password is too long ({password_bytes} bytes). Maximum is 72 bytes."
            )
        
        try:
            return self.pwd_context.hash(password)
        except ValueError as e:
            logger.error(f"Bcrypt error: {e}")
            if "72 bytes" in str(e):
                raise PasswordComplexityError(
                    f"Password is too long. Maximum is 72 bytes."
                )
            raise
    
    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify password against hash.
        
        Args:
            plain_password: Plain text password
            hashed_password: Bcrypt hashed password
            
        Returns:
            True if password matches, False otherwise
        """
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def _generate_encryption_salt(self) -> str:
        """
        Generate a random encryption salt for user-specific credential encryption.
        
        Returns:
            64-character hex string
        """
        return secrets.token_hex(32)  # 32 bytes = 64 hex characters
    
    def _check_rate_limit(self, username: str) -> None:
        """
        Check if user has exceeded rate limit for login attempts.
        
        Uses Redis to track login attempts per username.
        Limit: 5 attempts per 15 minutes (configurable via max_login_attempts).
        
        Args:
            username: Username to check
            
        Raises:
            RateLimitExceededError: If rate limit exceeded
        """
        key = f"rate_limit:login:{username}"
        
        try:
            attempts = self.redis_client.get(key)
            
            if attempts and int(attempts) >= settings.max_login_attempts:
                ttl = self.redis_client.ttl(key)
                raise RateLimitExceededError(
                    f"Too many login attempts. Please try again in {ttl} seconds."
                )
        except redis.RedisError as e:
            logger.warning(f"Redis error during rate limit check: {e}")
            # Continue without rate limiting if Redis is unavailable
    
    def _increment_rate_limit(self, username: str) -> None:
        """
        Increment rate limit counter for username.
        
        Args:
            username: Username to increment counter for
        """
        key = f"rate_limit:login:{username}"
        window_seconds = 15 * 60  # 15 minutes
        
        try:
            current = self.redis_client.get(key)
            
            if current is None:
                # First attempt in window
                self.redis_client.setex(key, window_seconds, 1)
            else:
                # Increment existing counter
                self.redis_client.incr(key)
        except redis.RedisError as e:
            logger.warning(f"Redis error during rate limit increment: {e}")
    
    def _reset_rate_limit(self, username: str) -> None:
        """
        Reset rate limit counter for username after successful login.
        
        Args:
            username: Username to reset counter for
        """
        key = f"rate_limit:login:{username}"
        
        try:
            self.redis_client.delete(key)
        except redis.RedisError as e:
            logger.warning(f"Redis error during rate limit reset: {e}")
    
    def _check_account_lockout(self, user: User) -> None:
        """
        Check if user account is locked due to failed login attempts.
        
        Args:
            user: User to check
            
        Raises:
            AccountLockedError: If account is locked
            
        Requirements: 10.6 - Lock account after 5 failed attempts for 30 minutes
        """
        if user.locked_until and user.locked_until > datetime.utcnow():
            remaining = (user.locked_until - datetime.utcnow()).total_seconds()
            minutes = int(remaining / 60)
            raise AccountLockedError(
                f"Account is locked. Please try again in {minutes} minutes."
            )
        
        # If lock period has expired, reset the lock
        if user.locked_until and user.locked_until <= datetime.utcnow():
            user.locked_until = None
            user.failed_login_attempts = 0
            self.db.commit()
    
    def _increment_failed_attempts(self, user: User) -> None:
        """
        Increment failed login attempts counter and lock account if threshold reached.
        
        Args:
            user: User to increment counter for
            
        Requirements: 10.6 - Lock account after 5 failed attempts for 30 minutes
        """
        user.failed_login_attempts += 1
        
        if user.failed_login_attempts >= settings.max_login_attempts:
            # Lock account for configured duration
            lockout_duration = timedelta(minutes=settings.account_lockout_minutes)
            user.locked_until = datetime.utcnow() + lockout_duration
            logger.warning(
                f"Account locked for user {user.username} after "
                f"{user.failed_login_attempts} failed attempts"
            )
        
        self.db.commit()
    
    def _reset_failed_attempts(self, user: User) -> None:
        """
        Reset failed login attempts counter after successful login.
        
        Args:
            user: User to reset counter for
        """
        user.failed_login_attempts = 0
        user.locked_until = None
        self.db.commit()
    
    def _create_access_token(self, data: Dict[str, Any]) -> str:
        """
        Create JWT access token.
        
        Args:
            data: Data to encode in token (must include 'sub' for user ID)
            
        Returns:
            JWT token string
            
        Requirements: 10.3 - Create session token valid for 24 hours
        """
        to_encode = data.copy()
        
        # Add expiration time
        expire = datetime.utcnow() + timedelta(hours=settings.jwt_expiration_hours)
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })
        
        # Encode JWT
        encoded_jwt = jwt.encode(
            to_encode,
            settings.secret_key,
            algorithm=settings.jwt_algorithm
        )
        
        return encoded_jwt
    
    def _store_token(self, user_id: int, token: str) -> None:
        """
        Store token in Redis for validation and invalidation.
        
        Args:
            user_id: User ID
            token: JWT token
        """
        key = f"token:{user_id}:{token}"
        expiry_seconds = settings.jwt_expiration_hours * 3600
        
        try:
            self.redis_client.setex(key, expiry_seconds, "valid")
        except redis.RedisError as e:
            logger.warning(f"Redis error during token storage: {e}")
    
    def _is_token_valid(self, user_id: int, token: str) -> bool:
        """
        Check if token is valid (not invalidated/logged out).
        
        Args:
            user_id: User ID
            token: JWT token
            
        Returns:
            True if token is valid, False if invalidated
        """
        key = f"token:{user_id}:{token}"
        
        try:
            return self.redis_client.exists(key) > 0
        except redis.RedisError as e:
            logger.warning(f"Redis error during token validation: {e}")
            # If Redis is unavailable, allow the token (fail open)
            return True
    
    def _invalidate_token(self, user_id: int, token: str) -> None:
        """
        Invalidate token (logout).
        
        Args:
            user_id: User ID
            token: JWT token
        """
        key = f"token:{user_id}:{token}"
        
        try:
            self.redis_client.delete(key)
        except redis.RedisError as e:
            logger.warning(f"Redis error during token invalidation: {e}")
    
    def _log_authentication_attempt(
        self,
        username: str,
        success: bool,
        reason: Optional[str] = None
    ) -> None:
        """
        Log authentication attempt.
        
        Args:
            username: Username attempting authentication
            success: Whether authentication succeeded
            reason: Reason for failure (if applicable)
            
        Requirements: 14.4 - Log all authentication attempts with timestamps and outcomes
        """
        if success:
            logger.info(
                f"Authentication successful",
                extra={
                    "username": username,
                    "timestamp": datetime.utcnow().isoformat(),
                    "outcome": "success"
                }
            )
        else:
            logger.warning(
                f"Authentication failed",
                extra={
                    "username": username,
                    "timestamp": datetime.utcnow().isoformat(),
                    "outcome": "failure",
                    "reason": reason or "unknown"
                }
            )
    
    def register_user(
        self,
        username: str,
        email: str,
        password: str
    ) -> User:
        """
        Register a new user with password complexity validation.
        
        Args:
            username: Unique username
            email: Unique email address
            password: Plain text password
            
        Returns:
            Created user object
            
        Raises:
            PasswordComplexityError: If password does not meet requirements
            AuthServiceError: If user already exists or registration fails
            
        Requirements: 10.2 - Support password-based authentication with bcrypt hashing
        Requirements: 10.5 - Enforce password complexity requirements
        """
        # Log password length for debugging
        password_bytes = len(password.encode('utf-8'))
        logger.debug(f"Registration attempt - password length: {len(password)} chars, {password_bytes} bytes")
        
        # Validate password complexity
        self._validate_password_complexity(password)
        
        # Check if username already exists
        existing_user = self.db.query(User).filter(
            User.username == username
        ).first()
        
        if existing_user:
            raise AuthServiceError(f"Username '{username}' already exists")
        
        # Check if email already exists
        existing_email = self.db.query(User).filter(
            User.email == email
        ).first()
        
        if existing_email:
            raise AuthServiceError(f"Email '{email}' already registered")
        
        try:
            # Hash password
            password_hash = self._hash_password(password)
            
            # Generate encryption salt for credential encryption
            encryption_salt = self._generate_encryption_salt()
            
            # Create user
            user = User(
                username=username,
                email=email,
                password_hash=password_hash,
                encryption_salt=encryption_salt,
                is_active=True,
                failed_login_attempts=0
            )
            
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
            
            logger.info(f"User registered successfully: {username}")
            
            return user
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to register user {username}: {e}")
            raise AuthServiceError(f"Registration failed: {e}")
    
    def authenticate(self, username: str, password: str) -> Dict[str, Any]:
        """
        Authenticate user and generate session token.
        
        Args:
            username: Username
            password: Plain text password
            
        Returns:
            Dictionary containing:
                - token: JWT access token
                - user_id: User ID
                - username: Username
                - email: Email address
            
        Raises:
            RateLimitExceededError: If rate limit exceeded
            AccountLockedError: If account is locked
            AuthenticationError: If authentication fails
            
        Requirements: 10.1 - Require authentication before allowing access
        Requirements: 10.2 - Support password-based authentication with bcrypt
        Requirements: 10.3 - Create session token valid for 24 hours
        Requirements: 10.6 - Lock account after 5 failed attempts for 30 minutes
        Requirements: 14.4 - Log all authentication attempts
        """
        # Check rate limit
        self._check_rate_limit(username)
        
        # Get user from database
        user = self.db.query(User).filter(User.username == username).first()
        
        if not user:
            # Increment rate limit even for non-existent users
            self._increment_rate_limit(username)
            self._log_authentication_attempt(username, False, "user_not_found")
            raise AuthenticationError("Invalid username or password")
        
        # Check if account is locked
        try:
            self._check_account_lockout(user)
        except AccountLockedError as e:
            self._log_authentication_attempt(username, False, "account_locked")
            raise
        
        # Verify password
        if not self._verify_password(password, user.password_hash):
            # Increment failed attempts
            self._increment_failed_attempts(user)
            self._increment_rate_limit(username)
            self._log_authentication_attempt(username, False, "invalid_password")
            raise AuthenticationError("Invalid username or password")
        
        # Check if account is active
        if not user.is_active:
            self._log_authentication_attempt(username, False, "account_inactive")
            raise AuthenticationError("Account is inactive")
        
        # Authentication successful
        self._reset_failed_attempts(user)
        self._reset_rate_limit(username)
        
        # Generate JWT token
        token_data = {
            "sub": str(user.id),
            "username": user.username,
            "email": user.email
        }
        
        access_token = self._create_access_token(token_data)
        
        # Store token in Redis
        self._store_token(user.id, access_token)
        
        self._log_authentication_attempt(username, True)
        
        return {
            "token": access_token,
            "user_id": user.id,
            "username": user.username,
            "email": user.email
        }
    
    def validate_token(self, token: str) -> User:
        """
        Validate JWT token and return user.
        
        Args:
            token: JWT token
            
        Returns:
            User object if token is valid
            
        Raises:
            TokenExpiredError: If token has expired
            TokenInvalidError: If token is invalid or invalidated
            
        Requirements: 10.4 - Require re-authentication when token expires
        """
        try:
            # Decode JWT
            payload = jwt.decode(
                token,
                settings.secret_key,
                algorithms=[settings.jwt_algorithm]
            )
            
            # Extract user ID
            user_id_str: str = payload.get("sub")
            if user_id_str is None:
                raise TokenInvalidError("Token missing user ID")
            
            user_id = int(user_id_str)
            
            # Check if token is invalidated (logged out)
            if not self._is_token_valid(user_id, token):
                raise TokenInvalidError("Token has been invalidated")
            
            # Get user from database
            user = self.db.query(User).filter(User.id == user_id).first()
            
            if user is None:
                raise TokenInvalidError("User not found")
            
            if not user.is_active:
                raise TokenInvalidError("User account is inactive")
            
            return user
            
        except JWTError as e:
            if "expired" in str(e).lower():
                raise TokenExpiredError("Token has expired")
            else:
                raise TokenInvalidError(f"Invalid token: {e}")
    
    def refresh_token(self, token: str) -> Dict[str, Any]:
        """
        Refresh JWT token.
        
        Validates the current token and issues a new one if valid.
        
        Args:
            token: Current JWT token
            
        Returns:
            Dictionary containing new token and user info
            
        Raises:
            TokenExpiredError: If token has expired
            TokenInvalidError: If token is invalid
        """
        # Validate current token
        user = self.validate_token(token)
        
        # Invalidate old token
        self._invalidate_token(user.id, token)
        
        # Generate new token
        token_data = {
            "sub": str(user.id),
            "username": user.username,
            "email": user.email
        }
        
        new_token = self._create_access_token(token_data)
        
        # Store new token
        self._store_token(user.id, new_token)
        
        logger.info(f"Token refreshed for user {user.username}")
        
        return {
            "token": new_token,
            "user_id": user.id,
            "username": user.username,
            "email": user.email
        }
    
    def logout(self, token: str) -> bool:
        """
        Logout user by invalidating token.
        
        Args:
            token: JWT token to invalidate
            
        Returns:
            True if logout successful
            
        Raises:
            TokenInvalidError: If token is invalid
        """
        try:
            # Validate token first
            user = self.validate_token(token)
            
            # Invalidate token
            self._invalidate_token(user.id, token)
            
            logger.info(f"User logged out: {user.username}")
            
            return True
            
        except (TokenExpiredError, TokenInvalidError):
            # Token already invalid or expired
            return True
