"""
Rate limiting middleware using Redis counters.

This middleware enforces rate limits per user (100 requests/minute)
to prevent abuse and ensure fair resource allocation.

Requirements: 13.5 (API rate limiting)
"""

import logging
import time
from typing import Callable
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import redis

from vmledger.config import settings


logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware for rate limiting API requests per user.
    
    Uses Redis to track request counts with sliding window algorithm.
    Limit: 100 requests per minute per user (configurable).
    
    Rate limiting is applied after authentication, so only authenticated
    requests count toward the limit.
    """
    
    def __init__(self, app, redis_client: redis.Redis = None):
        """
        Initialize rate limit middleware.
        
        Args:
            app: FastAPI application
            redis_client: Redis client for rate limiting (optional)
        """
        super().__init__(app)
        
        # Initialize Redis client
        if redis_client is None:
            self.redis_client = redis.from_url(
                settings.redis_url,
                password=settings.redis_password if settings.redis_password else None,
                decode_responses=True
            )
        else:
            self.redis_client = redis_client
        
        # Rate limit configuration
        self.rate_limit = settings.rate_limit_per_minute
        self.window_seconds = 60  # 1 minute window
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and enforce rate limiting.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain
            
        Returns:
            HTTP response (429 if rate limit exceeded)
        """
        # Skip rate limiting for public endpoints
        if not hasattr(request.state, "user_id"):
            # No authenticated user, skip rate limiting
            return await call_next(request)
        
        user_id = request.state.user_id
        
        # Check rate limit
        try:
            allowed, remaining, reset_time = self._check_rate_limit(user_id)
            
            if not allowed:
                # Rate limit exceeded
                logger.warning(
                    f"Rate limit exceeded for user {user_id}",
                    extra={
                        "context": {
                            "user_id": user_id,
                            "path": request.url.path,
                            "method": request.method,
                            "request_id": getattr(request.state, "request_id", "unknown"),
                            "reset_time": reset_time
                        }
                    }
                )
                
                return self._rate_limit_response(
                    request,
                    remaining,
                    reset_time
                )
            
            # Continue to next middleware/handler
            response = await call_next(request)
            
            # Add rate limit headers to response
            response.headers["X-RateLimit-Limit"] = str(self.rate_limit)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(reset_time)
            
            return response
            
        except redis.RedisError as e:
            # Redis error - log and allow request (fail open)
            logger.error(
                f"Redis error during rate limiting: {e}",
                exc_info=True,
                extra={
                    "context": {
                        "user_id": user_id,
                        "path": request.url.path,
                        "request_id": getattr(request.state, "request_id", "unknown")
                    }
                }
            )
            
            # Allow request to proceed if Redis is unavailable
            return await call_next(request)
    
    def _check_rate_limit(self, user_id: int) -> tuple[bool, int, int]:
        """
        Check if user has exceeded rate limit.
        
        Uses sliding window algorithm with Redis sorted sets.
        
        Args:
            user_id: User ID to check
            
        Returns:
            Tuple of (allowed, remaining_requests, reset_timestamp)
        """
        key = f"rate_limit:api:{user_id}"
        now = time.time()
        window_start = now - self.window_seconds
        
        # Use Redis pipeline for atomic operations
        pipe = self.redis_client.pipeline()
        
        # Remove old entries outside the window
        pipe.zremrangebyscore(key, 0, window_start)
        
        # Count requests in current window
        pipe.zcard(key)
        
        # Add current request
        pipe.zadd(key, {str(now): now})
        
        # Set expiry on key (cleanup)
        pipe.expire(key, self.window_seconds)
        
        # Execute pipeline
        results = pipe.execute()
        
        # Get count of requests in window (before adding current request)
        request_count = results[1]
        
        # Calculate remaining requests
        remaining = max(0, self.rate_limit - request_count - 1)
        
        # Calculate reset time (end of current window)
        reset_time = int(now + self.window_seconds)
        
        # Check if limit exceeded
        allowed = request_count < self.rate_limit
        
        return allowed, remaining, reset_time
    
    def _rate_limit_response(
        self,
        request: Request,
        remaining: int,
        reset_time: int
    ) -> JSONResponse:
        """
        Create rate limit exceeded response.
        
        Args:
            request: HTTP request
            remaining: Remaining requests (0)
            reset_time: Unix timestamp when limit resets
            
        Returns:
            JSON response with 429 status
        """
        retry_after = reset_time - int(time.time())
        
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "success": False,
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": f"Rate limit exceeded. Maximum {self.rate_limit} requests per minute.",
                    "details": {
                        "limit": self.rate_limit,
                        "remaining": remaining,
                        "reset_time": reset_time,
                        "retry_after_seconds": retry_after
                    },
                    "request_id": getattr(request.state, "request_id", "unknown")
                }
            },
            headers={
                "X-RateLimit-Limit": str(self.rate_limit),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(reset_time),
                "Retry-After": str(retry_after)
            }
        )
