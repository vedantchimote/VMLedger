"""
Authentication middleware for JWT token validation.

This middleware extracts and validates JWT tokens from Authorization headers,
enforcing authentication on protected endpoints.

Requirements: 10.1, 10.3, 10.4, 14.4
"""

import logging
from typing import Optional, Callable
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session

from vmledger.database import get_db
from vmledger.services.auth_service import (
    AuthService,
    TokenExpiredError,
    TokenInvalidError
)
from vmledger.models.user import User


logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware for JWT token validation and user authentication.
    
    Extracts JWT tokens from Authorization headers and validates them.
    Attaches authenticated user to request state for downstream handlers.
    
    Public endpoints (no authentication required):
    - /health
    - /health/detailed
    - /
    - /api/auth/register
    - /api/auth/login
    - /api/docs (if debug mode)
    - /api/redoc (if debug mode)
    - /openapi.json (if debug mode)
    """
    
    # Endpoints that don't require authentication
    PUBLIC_PATHS = {
        "/",
        "/health",
        "/health/detailed",
        "/api/auth/register",
        "/api/auth/login",
        "/api/docs",
        "/api/redoc",
        "/openapi.json",
    }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and validate authentication.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain
            
        Returns:
            HTTP response
        """
        # Check if path is public (no authentication required)
        if self._is_public_path(request.url.path):
            return await call_next(request)
        
        # Extract token from Authorization header
        token = self._extract_token(request)
        
        if not token:
            return self._unauthorized_response(
                "Missing authentication token",
                request
            )
        
        # Validate token and get user
        db: Session = None
        try:
            db = next(get_db())
            auth_service = AuthService(db)
            
            user = auth_service.validate_token(token)
            
            # Attach user to request state for downstream handlers
            request.state.user = user
            request.state.user_id = user.id
            
            # Log successful authentication
            logger.debug(
                f"Authentication successful for user {user.username}",
                extra={
                    "context": {
                        "user_id": user.id,
                        "username": user.username,
                        "path": request.url.path,
                        "method": request.method,
                        "request_id": getattr(request.state, "request_id", "unknown")
                    }
                }
            )
            
            # Continue to next middleware/handler
            response = await call_next(request)
            
            return response
            
        except TokenExpiredError:
            logger.warning(
                "Authentication failed: Token expired",
                extra={
                    "context": {
                        "path": request.url.path,
                        "method": request.method,
                        "request_id": getattr(request.state, "request_id", "unknown")
                    }
                }
            )
            return self._unauthorized_response(
                "Session token has expired. Please login again.",
                request
            )
            
        except TokenInvalidError as e:
            logger.warning(
                f"Authentication failed: {str(e)}",
                extra={
                    "context": {
                        "path": request.url.path,
                        "method": request.method,
                        "request_id": getattr(request.state, "request_id", "unknown")
                    }
                }
            )
            return self._unauthorized_response(
                "Invalid authentication token",
                request
            )
            
        except Exception as e:
            logger.error(
                f"Authentication error: {str(e)}",
                exc_info=True,
                extra={
                    "context": {
                        "path": request.url.path,
                        "method": request.method,
                        "request_id": getattr(request.state, "request_id", "unknown")
                    }
                }
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False,
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "Authentication service error",
                        "request_id": getattr(request.state, "request_id", "unknown")
                    }
                }
            )
        finally:
            if db:
                db.close()
    
    def _is_public_path(self, path: str) -> bool:
        """
        Check if path is public (no authentication required).
        
        Args:
            path: Request path
            
        Returns:
            True if path is public, False otherwise
        """
        # Exact match for public paths
        if path in self.PUBLIC_PATHS:
            return True
        
        # Check if path starts with public prefix followed by query params or trailing slash
        # (for OpenAPI docs with query parameters like /api/docs?param=value)
        for public_path in self.PUBLIC_PATHS:
            if path.startswith(public_path + "?") or path.startswith(public_path + "/"):
                return True
        
        return False
    
    def _extract_token(self, request: Request) -> Optional[str]:
        """
        Extract JWT token from Authorization header.
        
        Supports format: "Bearer <token>"
        
        Args:
            request: HTTP request
            
        Returns:
            JWT token string or None if not found
        """
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            return None
        
        # Check for Bearer token format
        parts = auth_header.split()
        
        if len(parts) != 2 or parts[0].lower() != "bearer":
            logger.warning(
                "Invalid Authorization header format",
                extra={
                    "context": {
                        "path": request.url.path,
                        "request_id": getattr(request.state, "request_id", "unknown")
                    }
                }
            )
            return None
        
        return parts[1]
    
    def _unauthorized_response(
        self,
        message: str,
        request: Request
    ) -> JSONResponse:
        """
        Create unauthorized response.
        
        Args:
            message: Error message
            request: HTTP request
            
        Returns:
            JSON response with 401 status
        """
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "success": False,
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": message,
                    "request_id": getattr(request.state, "request_id", "unknown")
                }
            },
            headers={"WWW-Authenticate": "Bearer"}
        )
