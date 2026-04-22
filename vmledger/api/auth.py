"""
Authentication API endpoints.

This module provides REST API endpoints for user authentication including
registration, login, logout, and token refresh.

Requirements: 10.1-10.6
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy.orm import Session

from vmledger.database import get_db
from vmledger.services.auth_service import (
    AuthService,
    PasswordComplexityError,
    AuthenticationError,
    AccountLockedError,
    TokenExpiredError,
    TokenInvalidError,
    RateLimitExceededError,
    AuthServiceError
)


logger = logging.getLogger(__name__)


# Pydantic Schemas for Request/Response

class RegisterRequest(BaseModel):
    """
    Schema for user registration request.
    
    Requirements: 10.2, 10.5
    """
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., min_length=12, description="Password (min 12 characters)")


class LoginRequest(BaseModel):
    """
    Schema for user login request.
    
    Requirements: 10.2
    """
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")


class TokenResponse(BaseModel):
    """
    Schema for authentication token response.
    
    Requirements: 10.3
    """
    token: str = Field(..., description="JWT access token")
    user_id: int = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")


class MessageResponse(BaseModel):
    """
    Schema for simple message response.
    """
    message: str = Field(..., description="Response message")


# Helper function to extract token from request
def get_token_from_request(request: Request) -> str:
    """
    Extract JWT token from Authorization header.
    
    Args:
        request: HTTP request
        
    Returns:
        JWT token string
        
    Raises:
        ValueError: If token is missing or invalid format
    """
    auth_header = request.headers.get("Authorization")
    
    if not auth_header:
        raise ValueError("Missing Authorization header")
    
    parts = auth_header.split()
    
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise ValueError("Invalid Authorization header format")
    
    return parts[1]


# Create router
router = APIRouter()


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Register a new user account with password complexity validation"
)
async def register(
    request_data: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Register a new user account.
    
    Password requirements:
    - Minimum 12 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number
    - At least one special character
    
    Args:
        request_data: Registration data (username, email, password)
        request: HTTP request
        db: Database session
        
    Returns:
        JSON response with token and user info
        
    Raises:
        400: Password complexity error or user already exists
        500: Internal server error
        
    Requirements: 10.2, 10.5
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    try:
        auth_service = AuthService(db)
        
        # Register user
        user = auth_service.register_user(
            username=request_data.username,
            email=request_data.email,
            password=request_data.password
        )
        
        # Authenticate immediately after registration
        auth_result = auth_service.authenticate(
            username=request_data.username,
            password=request_data.password
        )
        
        logger.info(
            f"User registered and authenticated: {user.username}",
            extra={
                "context": {
                    "user_id": user.id,
                    "username": user.username,
                    "request_id": request_id
                }
            }
        )
        
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "success": True,
                "data": {
                    "token": auth_result["token"],
                    "user_id": auth_result["user_id"],
                    "username": auth_result["username"],
                    "email": auth_result["email"]
                },
                "request_id": request_id
            }
        )
        
    except PasswordComplexityError as e:
        logger.warning(
            f"Registration failed: Password complexity error - {str(e)}",
            extra={"context": {"request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error": {
                    "code": "PASSWORD_COMPLEXITY_ERROR",
                    "message": str(e)
                },
                "request_id": request_id
            }
        )
        
    except AuthServiceError as e:
        logger.warning(
            f"Registration failed: {str(e)}",
            extra={"context": {"request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error": {
                    "code": "REGISTRATION_ERROR",
                    "message": str(e)
                },
                "request_id": request_id
            }
        )
        
    except Exception as e:
        logger.error(
            f"Registration error: {str(e)}",
            exc_info=True,
            extra={"context": {"request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Registration failed. Please try again."
                },
                "request_id": request_id
            }
        )


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Login user",
    description="Authenticate user and receive session token"
)
async def login(
    request_data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Authenticate user and generate session token.
    
    Rate limiting: 5 failed attempts within 15 minutes will lock the account for 30 minutes.
    
    Args:
        request_data: Login credentials (username, password)
        request: HTTP request
        db: Database session
        
    Returns:
        JSON response with token and user info
        
    Raises:
        401: Invalid credentials or account inactive
        429: Rate limit exceeded or account locked
        500: Internal server error
        
    Requirements: 10.1, 10.2, 10.3, 10.6
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    try:
        auth_service = AuthService(db)
        
        # Authenticate user
        auth_result = auth_service.authenticate(
            username=request_data.username,
            password=request_data.password
        )
        
        logger.info(
            f"User authenticated: {request_data.username}",
            extra={
                "context": {
                    "user_id": auth_result["user_id"],
                    "username": auth_result["username"],
                    "request_id": request_id
                }
            }
        )
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "data": {
                    "token": auth_result["token"],
                    "user_id": auth_result["user_id"],
                    "username": auth_result["username"],
                    "email": auth_result["email"]
                },
                "request_id": request_id
            }
        )
        
    except RateLimitExceededError as e:
        logger.warning(
            f"Login failed: Rate limit exceeded for {request_data.username}",
            extra={"context": {"request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "success": False,
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": str(e)
                },
                "request_id": request_id
            }
        )
        
    except AccountLockedError as e:
        logger.warning(
            f"Login failed: Account locked for {request_data.username}",
            extra={"context": {"request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "success": False,
                "error": {
                    "code": "ACCOUNT_LOCKED",
                    "message": str(e)
                },
                "request_id": request_id
            }
        )
        
    except AuthenticationError as e:
        logger.warning(
            f"Login failed: Authentication error for {request_data.username}",
            extra={"context": {"request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "success": False,
                "error": {
                    "code": "AUTHENTICATION_FAILED",
                    "message": str(e)
                },
                "request_id": request_id
            }
        )
        
    except Exception as e:
        logger.error(
            f"Login error: {str(e)}",
            exc_info=True,
            extra={"context": {"request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Login failed. Please try again."
                },
                "request_id": request_id
            }
        )


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Logout user",
    description="Invalidate session token"
)
async def logout(
    request: Request,
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Logout user by invalidating session token.
    
    Requires valid authentication token in Authorization header.
    
    Args:
        request: HTTP request with Authorization header
        db: Database session
        
    Returns:
        JSON response with success message
        
    Raises:
        401: Missing or invalid token
        500: Internal server error
        
    Requirements: 10.1
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    try:
        # Extract token from Authorization header
        token = get_token_from_request(request)
        
        auth_service = AuthService(db)
        
        # Logout (invalidate token)
        auth_service.logout(token)
        
        logger.info(
            "User logged out",
            extra={"context": {"request_id": request_id}}
        )
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "data": {
                    "message": "Logged out successfully"
                },
                "request_id": request_id
            }
        )
        
    except ValueError as e:
        logger.warning(
            f"Logout failed: {str(e)}",
            extra={"context": {"request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "success": False,
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": str(e)
                },
                "request_id": request_id
            }
        )
        
    except (TokenExpiredError, TokenInvalidError):
        # Token already invalid or expired - consider logout successful
        logger.info(
            "Logout with expired/invalid token",
            extra={"context": {"request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "data": {
                    "message": "Logged out successfully"
                },
                "request_id": request_id
            }
        )
        
    except Exception as e:
        logger.error(
            f"Logout error: {str(e)}",
            exc_info=True,
            extra={"context": {"request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Logout failed. Please try again."
                },
                "request_id": request_id
            }
        )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh token",
    description="Refresh session token before expiration"
)
async def refresh_token(
    request: Request,
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Refresh session token.
    
    Validates the current token and issues a new one with extended expiration.
    The old token is invalidated.
    
    Requires valid authentication token in Authorization header.
    
    Args:
        request: HTTP request with Authorization header
        db: Database session
        
    Returns:
        JSON response with new token and user info
        
    Raises:
        401: Missing, expired, or invalid token
        500: Internal server error
        
    Requirements: 10.3, 10.4
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    try:
        # Extract token from Authorization header
        token = get_token_from_request(request)
        
        auth_service = AuthService(db)
        
        # Refresh token
        auth_result = auth_service.refresh_token(token)
        
        logger.info(
            f"Token refreshed for user: {auth_result['username']}",
            extra={
                "context": {
                    "user_id": auth_result["user_id"],
                    "username": auth_result["username"],
                    "request_id": request_id
                }
            }
        )
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "data": {
                    "token": auth_result["token"],
                    "user_id": auth_result["user_id"],
                    "username": auth_result["username"],
                    "email": auth_result["email"]
                },
                "request_id": request_id
            }
        )
        
    except ValueError as e:
        logger.warning(
            f"Token refresh failed: {str(e)}",
            extra={"context": {"request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "success": False,
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": str(e)
                },
                "request_id": request_id
            }
        )
        
    except TokenExpiredError as e:
        logger.warning(
            f"Token refresh failed: Token expired",
            extra={"context": {"request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "success": False,
                "error": {
                    "code": "TOKEN_EXPIRED",
                    "message": "Session token has expired. Please login again."
                },
                "request_id": request_id
            }
        )
        
    except TokenInvalidError as e:
        logger.warning(
            f"Token refresh failed: Invalid token",
            extra={"context": {"request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "success": False,
                "error": {
                    "code": "TOKEN_INVALID",
                    "message": "Invalid authentication token"
                },
                "request_id": request_id
            }
        )
        
    except Exception as e:
        logger.error(
            f"Token refresh error: {str(e)}",
            exc_info=True,
            extra={"context": {"request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Token refresh failed. Please try again."
                },
                "request_id": request_id
            }
        )
