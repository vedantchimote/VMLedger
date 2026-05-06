# Caching Strategy

## Overview

VMLedger implements a Redis-based caching strategy to optimize API performance and reduce database load. The caching strategy focuses on frequently accessed endpoints with relatively stable data.

## Cached Endpoints

### 1. Dashboard Endpoint (`GET /api/dashboard`)

**Cache Key Pattern:** `dashboard:user:{user_id}`

**TTL:** 30 seconds

**Purpose:** The dashboard endpoint returns all VMs with their latest metrics and ping results. This is the most frequently accessed endpoint and benefits significantly from caching.

**Cache Key Components:**
- `user_id`: Ensures user isolation - each user has their own cached dashboard data

**Invalidation Triggers:**
- VM created
- VM updated
- VM deleted

**Implementation Details:**
- Uses optimized database query with LEFT JOINs to fetch all data in a single query
- Caches the complete JSON response
- Returns `"cached": true` in response when serving from cache
- Falls back to database query if Redis is unavailable

### 2. VM List Endpoint (`GET /api/vms`)

**Cache Key Pattern:** `vmlist:user:{user_id}:page:{page}:per_page:{per_page}[:tags:{tags}][:reachable:{is_reachable}]`

**TTL:** 30 seconds

**Purpose:** The VM list endpoint supports pagination and filtering. Caching reduces database load for repeated queries with the same parameters.

**Cache Key Components:**
- `user_id`: Ensures user isolation
- `page`: Page number for pagination
- `per_page`: Items per page
- `tags`: Optional comma-separated tags filter
- `is_reachable`: Optional reachability status filter

**Invalidation Triggers:**
- VM created
- VM updated
- VM deleted

**Implementation Details:**
- Cache key includes all query parameters to ensure correct results
- Pattern-based invalidation using `vmlist:user:{user_id}:*` to clear all cached variations
- Returns `"cached": true` in response when serving from cache
- Falls back to database query if Redis is unavailable

## Cache Invalidation Strategy

### Invalidation Functions

#### `invalidate_dashboard_cache(user_id: int)`
Deletes the dashboard cache entry for a specific user.

#### `invalidate_vmlist_cache(user_id: int)`
Deletes all VM list cache entries for a specific user using pattern matching (`vmlist:user:{user_id}:*`). This ensures that all paginated and filtered views are invalidated.

### When Invalidation Occurs

Cache invalidation is triggered by the following operations:

1. **VM Creation** (`POST /api/vms`)
   - Invalidates dashboard cache
   - Invalidates VM list cache
   - Reason: New VM should appear in both dashboard and list views

2. **VM Update** (`PUT /api/vms/{vm_id}`)
   - Invalidates dashboard cache
   - Invalidates VM list cache
   - Reason: Updated VM data should be reflected in both views

3. **VM Deletion** (`DELETE /api/vms/{vm_id}`)
   - Invalidates dashboard cache
   - Invalidates VM list cache
   - Reason: Deleted VM should be removed from both views

### Cache Invalidation Flow

```
User Action (Create/Update/Delete VM)
    ↓
API Endpoint Handler
    ↓
Database Operation
    ↓
invalidate_dashboard_cache(user_id)
    ↓
invalidate_vmlist_cache(user_id)
    ↓
Redis: DELETE dashboard:user:{user_id}
Redis: DELETE vmlist:user:{user_id}:*
    ↓
Next Request: Cache Miss → Fresh Data from Database
```

## Cache Key Design Principles

### 1. User Isolation
All cache keys include `user_id` to ensure complete data isolation between users. This prevents:
- Data leakage between users
- Cache poisoning attacks
- Authorization bypass attempts

### 2. Query Parameter Inclusion
VM list cache keys include all query parameters (page, per_page, tags, is_reachable) to ensure:
- Correct results for different filter combinations
- Proper pagination behavior
- No stale data from different query parameters

### 3. Pattern-Based Invalidation
VM list cache uses pattern matching for invalidation (`vmlist:user:{user_id}:*`) to:
- Invalidate all cached variations efficiently
- Avoid complex tracking of all possible query combinations
- Ensure consistency across all filtered views

## Performance Characteristics

### Cache Hit Rates
- **Dashboard:** Expected 80-90% hit rate (30s TTL with typical 30s auto-refresh)
- **VM List:** Expected 60-70% hit rate (varies based on user navigation patterns)

### Performance Improvements
- **Dashboard (uncached):** ~100-200ms (database query with joins)
- **Dashboard (cached):** ~5-10ms (Redis GET operation)
- **VM List (uncached):** ~50-100ms (database query with pagination)
- **VM List (cached):** ~5-10ms (Redis GET operation)

### Cache Size Estimates
- **Dashboard per user:** ~5-50 KB (depends on number of VMs and metrics)
- **VM List per user:** ~2-20 KB per cached query
- **Total per user:** ~50-200 KB (assuming multiple cached VM list queries)

For 100 concurrent users: ~5-20 MB total cache size

## Error Handling

### Redis Unavailable
If Redis is unavailable or returns an error:
1. Log warning message
2. Fall back to database query
3. Continue serving requests (degraded performance)
4. Do not cache the response

### Cache Corruption
If cached data cannot be parsed (JSON decode error):
1. Log warning message
2. Fall back to database query
3. Overwrite corrupted cache entry with fresh data

### Cache Invalidation Failure
If cache invalidation fails:
1. Log warning message
2. Continue with the operation (database write succeeds)
3. Stale cache will expire after TTL (30 seconds)

## Monitoring and Debugging

### Cache Hit/Miss Logging
Cache operations are logged at DEBUG level:
- Cache hit: `"Dashboard cache hit for user {user_id}"`
- Cache miss: `"Dashboard cache miss for user {user_id}, fetching from database"`
- Cache write: `"Dashboard data cached for user {user_id}"`
- Cache invalidation: `"Invalidated dashboard cache for user {user_id}"`

### Response Metadata
API responses include a `"cached"` field:
- `"cached": true` - Response served from cache
- `"cached": false` - Response fetched from database

This allows clients to:
- Monitor cache effectiveness
- Debug stale data issues
- Understand response time variations

## Configuration

### TTL Configuration
Cache TTL is currently hardcoded to 30 seconds. This value is chosen to:
- Match the dashboard auto-refresh interval (Requirement 12.6)
- Balance freshness vs. performance
- Minimize stale data exposure

Future enhancement: Make TTL configurable via environment variable.

### Redis Configuration
Redis connection is configured via environment variables:
- `REDIS_URL`: Redis connection URL (default: `redis://localhost:6379/0`)
- `REDIS_PASSWORD`: Redis password (optional)

## Future Enhancements

### 1. Metrics Caching
Cache individual VM metrics history with longer TTL (5 minutes) since historical data doesn't change.

### 2. Search Results Caching
Cache search results with 1-minute TTL to improve search performance.

### 3. Adaptive TTL
Adjust TTL based on data volatility:
- Longer TTL for stable VMs (no recent updates)
- Shorter TTL for frequently updated VMs

### 4. Cache Warming
Pre-populate cache for active users during off-peak hours.

### 5. Cache Compression
Compress cached data for large VM lists to reduce memory usage.

### 6. Cache Statistics
Track and expose cache hit rates, miss rates, and invalidation counts via metrics endpoint.

## Requirements Mapping

This caching strategy satisfies the following requirements:

- **Requirement 12.6:** Dashboard refresh every 30 seconds (30s cache TTL matches refresh interval)
- **Requirement 13.1:** VM list response within 200ms for up to 100 VMs (cache reduces to ~5-10ms)
- **Requirement 13.2:** VM details response within 100ms (not cached, but optimized query)
- **Requirement 13.3:** VM registration response within 500ms (cache invalidation adds <5ms)
- **Requirement 13.4:** Database connection pooling (cache reduces database load)
- **Requirement 13.5:** Database indexes on frequently queried fields (cache reduces index usage)

## Testing

### Unit Tests
- Test cache hit/miss behavior
- Test cache invalidation on create/update/delete
- Test fallback when Redis is unavailable
- Test cache key generation with different parameters

### Integration Tests
- Test cache consistency across multiple requests
- Test cache invalidation timing
- Test concurrent cache access
- Test cache behavior under load

### Performance Tests
- Measure cache hit rates under realistic load
- Measure response time improvements
- Measure cache memory usage
- Measure cache invalidation latency
