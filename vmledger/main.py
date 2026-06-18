"""
Main FastAPI application entry point.
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import time
import uuid

from vmledger.config import settings, validate_required_settings
from vmledger.logging_config import setup_logging
from vmledger.database import check_db_connection, get_pool_status
from vmledger.middleware import AuthMiddleware, RateLimitMiddleware
from vmledger.error_handlers import register_exception_handlers

# Setup logging first
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown events.
    """
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    
    try:
        # Validate configuration
        validate_required_settings()
        logger.info("Configuration validation passed")
    except ValueError as e:
        logger.critical(f"Configuration validation failed: {e}")
        raise
    
    # Check database connection
    if not check_db_connection():
        logger.critical("Database connection failed")
        raise RuntimeError("Cannot connect to database")
    
    logger.info("Database connection established")
    logger.info(f"Connection pool status: {get_pool_status()}")
    
    logger.info(f"{settings.app_name} started successfully")
    
    yield
    
    # Shutdown
    logger.info(f"Shutting down {settings.app_name}")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Lightweight CMDB and Monitoring System for Personal VM Infrastructure",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.debug else None,
    redoc_url="/api/redoc" if settings.debug else None,
)


# CORS Middleware - Must be added first to handle preflight requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Rate Limiting Middleware - Applied after authentication
app.add_middleware(RateLimitMiddleware)


# Authentication Middleware - Validates JWT tokens
app.add_middleware(AuthMiddleware)


# Register exception handlers
register_exception_handlers(app)


# Request ID Middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add unique request ID to each request for tracing."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    # Add request ID to response headers
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    
    return response


# Logging Middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests and responses."""
    start_time = time.time()
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.info(
        f"Request started: {request.method} {request.url.path}",
        extra={
            "context": {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client_ip": request.client.host if request.client else "unknown"
            }
        }
    )
    
    response = await call_next(request)
    
    duration = time.time() - start_time
    logger.info(
        f"Request completed: {request.method} {request.url.path} - {response.status_code}",
        extra={
            "context": {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2)
            }
        }
    )
    
    return response


# Health Check Endpoints
@app.get("/health", tags=["Health"])
async def health_check():
    """Basic health check endpoint."""
    return {
        "success": True,
        "data": {
            "status": "healthy",
            "version": settings.app_version
        }
    }


@app.get("/health/detailed", tags=["Health"])
async def detailed_health_check():
    """Detailed health check with database and pool status."""
    db_healthy = check_db_connection()
    pool_status = get_pool_status()
    
    return {
        "success": True,
        "data": {
            "status": "healthy" if db_healthy else "unhealthy",
            "version": settings.app_version,
            "database": {
                "connected": db_healthy
            },
            "connection_pool": pool_status
        }
    }


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "success": True,
        "data": {
            "name": settings.app_name,
            "version": settings.app_version,
            "description": "Lightweight CMDB and Monitoring System",
            "docs_url": "/api/docs" if settings.debug else None
        }
    }


# Import and include API routers
from vmledger.api import auth, vms, ssh, services, lxc

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(vms.router, prefix="/api/vms", tags=["VMs"])
app.include_router(services.router, prefix="/api/vms", tags=["Services"])
app.include_router(lxc.router, prefix="/api/vms", tags=["LXC"])
app.include_router(ssh.router, tags=["SSH Terminal"])

# Standalone routes for endpoints that conflict with /{vm_id} in the VMs router
# These must be registered at /api/* to avoid the path parameter conflict
app.add_api_route(
    "/api/dashboard",
    vms.get_dashboard,
    methods=["GET"],
    tags=["VMs"],
    summary="Get dashboard data",
)
app.add_api_route(
    "/api/search",
    vms.search_vms,
    methods=["GET"],
    tags=["VMs"],
    summary="Search VMs",
)

# TODO: Import and include remaining API routers
# from vmledger.api import metrics, alerts
# app.include_router(metrics.router, prefix="/api/metrics", tags=["Metrics"])
# app.include_router(alerts.router, prefix="/api/alerts", tags=["Alerts"])
