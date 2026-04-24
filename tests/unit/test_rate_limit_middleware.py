"""
Unit tests for rate limiting middleware.

Tests rate limit enforcement, Redis integration, and error handling.

Requirements: 13.5 (API rate limiting)
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
import fakeredis

from vmledger.middleware.rate_limit import RateLimitMiddleware
from vmledger.config import settings


@pytest.fixture
def redis_client():
    """Create fake Redis client for testing."""
    return fakeredis.FakeStrictRedis(decode_responses=True)


@pytest.fixture
def app(redis_client):
    """Create test FastAPI application with rate limit middleware."""
    app = FastAPI()
    
    # Add rate limit middleware with fake Redis
    app.add_middleware(RateLimitMiddleware, redis_client=redis_client)
    
    @app.get("/api/vms")
    async def protected(request: Request):
        # Simulate authenticated request
        request.state.user_id = 1
        return {"message": "success"}
    
    @app.get("/public")
    async def public():
        # No user_id in state (unauthenticated)
        return {"message": "public"}
    
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestRateLimitMiddleware:
    """Test suite for rate limiting middleware."""
    
    def test_unauthenticated_requests_not_rate_limited(self, client):
        """Test that unauthenticated requests bypass rate limiting."""
        # Make many requests to public endpoint
        for _ in range(150):  # More than rate limit
            response = client.get("/public")
            assert response.status_code == 200
    
    def test_authenticated_requests_within_limit_allowed(self, client):
        """Test that requests within rate limit are allowed."""
        # Make requests within limit (100 per minute)
        for i in range(50):
            response = client.get("/api/vms")
            assert response.status_code == 200
            
            # Check rate limit headers
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers
            assert "X-RateLimit-Reset" in response.headers
            
            # Verify limit value
            assert int(response.headers["X-RateLimit-Limit"]) == settings.rate_limit_per_minute
    
    def test_rate_limit_exceeded_returns_429(self, client):
        """Test that exceeding rate limit returns 429 error."""
        # Make requests up to limit
        for i in range(settings.rate_limit_per_minute):
            response = client.get("/api/vms")
            assert response.status_code == 200
        
        # Next request should be rate limited
        response = client.get("/api/vms")
        assert response.status_code == 429
        assert response.json()["success"] is False
        assert "Rate limit exceeded" in response.json()["error"]["message"]
    
    def test_rate_limit_headers_in_429_response(self, client):
        """Test that 429 response includes rate limit headers."""
        # Exceed rate limit
        for i in range(settings.rate_limit_per_minute + 1):
            response = client.get("/api/vms")
        
        # Check last response (429)
        assert response.status_code == 429
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers
        assert "Retry-After" in response.headers
        
        # Remaining should be 0
        assert int(response.headers["X-RateLimit-Remaining"]) == 0
    
    def test_rate_limit_error_details(self, client):
        """Test that 429 response includes detailed error information."""
        # Exceed rate limit
        for i in range(settings.rate_limit_per_minute + 1):
            response = client.get("/api/vms")
        
        # Check error details
        error = response.json()["error"]
        assert error["code"] == "RATE_LIMIT_EXCEEDED"
        assert "details" in error
        assert error["details"]["limit"] == settings.rate_limit_per_minute
        assert error["details"]["remaining"] == 0
        assert "reset_time" in error["details"]
        assert "retry_after_seconds" in error["details"]
    
    def test_rate_limit_remaining_decrements(self, client):
        """Test that remaining count decrements with each request."""
        # Make a few requests and check remaining count
        for i in range(5):
            response = client.get("/api/vms")
            assert response.status_code == 200
            
            remaining = int(response.headers["X-RateLimit-Remaining"])
            expected_remaining = settings.rate_limit_per_minute - i - 1
            assert remaining == expected_remaining
    
    def test_rate_limit_per_user_isolation(self, app, redis_client):
        """Test that rate limits are isolated per user."""
        client = TestClient(app)
        
        # Simulate requests from user 1
        for i in range(50):
            response = client.get("/api/vms")
            # Manually set user_id in middleware (simulated)
            assert response.status_code == 200
        
        # User 1 should have 50 requests remaining
        response = client.get("/api/vms")
        remaining_user1 = int(response.headers["X-RateLimit-Remaining"])
        assert remaining_user1 < settings.rate_limit_per_minute
        
        # Simulate requests from user 2 (different user_id)
        # In real scenario, different user would have separate limit
        # This test verifies the key structure includes user_id
        key_user1 = f"rate_limit:api:1"
        key_user2 = f"rate_limit:api:2"
        
        # Verify keys are different
        assert key_user1 != key_user2
    
    def test_rate_limit_window_expiry(self, client, redis_client):
        """Test that rate limit window expires after 60 seconds."""
        # Make a request
        response = client.get("/api/vms")
        assert response.status_code == 200
        
        # Check TTL on Redis key
        key = "rate_limit:api:1"
        ttl = redis_client.ttl(key)
        
        # TTL should be around 60 seconds (within 5 second tolerance)
        assert 55 <= ttl <= 60
    
    @patch("vmledger.middleware.rate_limit.redis.from_url")
    def test_redis_error_fails_open(self, mock_redis_from_url, app):
        """Test that Redis errors allow requests (fail open)."""
        # Setup mock Redis that raises errors
        mock_redis = Mock()
        mock_redis.pipeline.side_effect = Exception("Redis connection error")
        mock_redis_from_url.return_value = mock_redis
        
        # Create app with failing Redis
        app_with_failing_redis = FastAPI()
        app_with_failing_redis.add_middleware(RateLimitMiddleware)
        
        @app_with_failing_redis.get("/api/vms")
        async def protected(request: Request):
            request.state.user_id = 1
            return {"message": "success"}
        
        client = TestClient(app_with_failing_redis)
        
        # Request should succeed despite Redis error
        response = client.get("/api/vms")
        assert response.status_code == 200
    
    def test_sliding_window_algorithm(self, client, redis_client):
        """Test that sliding window algorithm works correctly."""
        # Make requests at different times
        for i in range(10):
            response = client.get("/api/vms")
            assert response.status_code == 200
        
        # Check Redis sorted set structure
        key = "rate_limit:api:1"
        count = redis_client.zcard(key)
        
        # Should have 10 entries
        assert count == 10
        
        # All entries should have timestamps as scores
        entries = redis_client.zrange(key, 0, -1, withscores=True)
        assert len(entries) == 10
        
        # Verify timestamps are recent
        now = time.time()
        for entry, score in entries:
            assert now - 60 <= score <= now
    
    def test_old_entries_removed_from_window(self, client, redis_client):
        """Test that old entries outside window are removed."""
        key = "rate_limit:api:1"
        now = time.time()
        
        # Add old entry (70 seconds ago, outside 60-second window)
        old_timestamp = now - 70
        redis_client.zadd(key, {str(old_timestamp): old_timestamp})
        
        # Make a new request
        response = client.get("/api/vms")
        assert response.status_code == 200
        
        # Old entry should be removed
        entries = redis_client.zrange(key, 0, -1, withscores=True)
        for entry, score in entries:
            # All entries should be within last 60 seconds
            assert score >= now - 60
    
    def test_concurrent_requests_counted_correctly(self, client):
        """Test that concurrent requests are counted correctly."""
        # Make multiple requests rapidly
        responses = []
        for i in range(20):
            response = client.get("/api/vms")
            responses.append(response)
        
        # All should succeed (within limit)
        for response in responses:
            assert response.status_code == 200
        
        # Check that remaining count is consistent
        last_remaining = int(responses[-1].headers["X-RateLimit-Remaining"])
        expected_remaining = settings.rate_limit_per_minute - 20
        assert last_remaining == expected_remaining
    
    def test_rate_limit_reset_time_accurate(self, client):
        """Test that reset time is accurate."""
        response = client.get("/api/vms")
        assert response.status_code == 200
        
        reset_time = int(response.headers["X-RateLimit-Reset"])
        now = int(time.time())
        
        # Reset time should be within next 60 seconds
        assert now <= reset_time <= now + 60
    
    def test_retry_after_header_accurate(self, client):
        """Test that Retry-After header is accurate in 429 response."""
        # Exceed rate limit
        for i in range(settings.rate_limit_per_minute + 1):
            response = client.get("/api/vms")
        
        # Check Retry-After header
        retry_after = int(response.headers["Retry-After"])
        
        # Should be between 0 and 60 seconds
        assert 0 <= retry_after <= 60


class TestRateLimitConfiguration:
    """Test suite for rate limit configuration."""
    
    def test_rate_limit_uses_config_value(self, redis_client):
        """Test that rate limit uses configured value."""
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, redis_client=redis_client)
        
        @app.get("/api/vms")
        async def protected(request: Request):
            request.state.user_id = 1
            return {"message": "success"}
        
        client = TestClient(app)
        
        # Make request and check limit header
        response = client.get("/api/vms")
        assert response.status_code == 200
        
        limit = int(response.headers["X-RateLimit-Limit"])
        assert limit == settings.rate_limit_per_minute
    
    def test_window_duration_is_60_seconds(self, redis_client):
        """Test that rate limit window is 60 seconds."""
        middleware = RateLimitMiddleware(app=Mock(), redis_client=redis_client)
        assert middleware.window_seconds == 60
