"""
Centralized error handlers for FastAPI application.

This module provides exception handlers that convert exceptions into
structured JSON responses with appropriate HTTP status codes and request IDs.

Requirements: 14.1-14.6
"""

import logging
from typing import Union
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from pydantic import ValidationError as PydanticValidationError

from vmledger.exceptions import VMLedgerError


logger = logging.getLogger(__name__)


def get_request_id(request: Request) -> str:
    """
    Extract request ID from request state.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Request ID string
    """
    return getattr(request.state, "request_id", "unknown")


async def vmledger_exception_handler(request: Request, exc: VMLedgerError) -> JSONResponse:
    """
    Handle VMLedger custom exceptions.
    
    Converts VMLedgerError instances into structured JSON responses with
    appropriate HTTP status codes.
    
    Args:
        request: FastAPI request object
        exc: VMLedgerError instance
        
    Returns:
        JSONResponse with error details
        
    Requirements: 14.1-14.6
    """
    request_id = get_request_id(request)
    
    # Log based on HTTP status code
    if exc.http_status >= 500:
        logger.error(
            f"{exc.__class__.__name__}: {exc.message}",
            extra={
                "context": {
                    "request_id": request_id,
                    "path": request.url.path,
                    "method": request.method,
                    "error_code": exc.code,
                    "details": exc.details
                }
            },
            exc_info=True
        )
    elif exc.http_status >= 400:
        logger.warning(
            f"{exc.__class__.__name__}: {exc.message}",
            extra={
                "context": {
                    "request_id": request_id,
                    "path": request.url.path,
                    "method": request.method,
                    "error_code": exc.code,
                    "details": exc.details
                }
            }
        )
    
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "success": False,
            "error": exc.to_dict(),
            "request_id": request_id
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Handle FastAPI/Pydantic validation errors.
    
    Converts RequestValidationError into structured JSON response with
    detailed field-level error information.
    
    Args:
        request: FastAPI request object
        exc: RequestValidationError instance
        
    Returns:
        JSONResponse with validation error details
        
    Requirements: 14.3
    """
    request_id = get_request_id(request)
    
    # Extract field-level errors
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field,
            "message": error["msg"],
            "type": error["type"]
        })
    
    logger.warning(
        "Request validation failed",
        extra={
            "context": {
                "request_id": request_id,
                "path": request.url.path,
                "method": request.method,
                "errors": errors
            }
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": errors
            },
            "request_id": request_id
        }
    )


async def database_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """
    Handle SQLAlchemy database errors.
    
    Converts database exceptions into user-friendly error responses while
    logging full error details for debugging.
    
    Args:
        request: FastAPI request object
        exc: SQLAlchemyError instance
        
    Returns:
        JSONResponse with generic error message
        
    Requirements: 14.3
    """
    request_id = get_request_id(request)
    
    # Log full error details
    logger.error(
        f"Database error: {str(exc)}",
        extra={
            "context": {
                "request_id": request_id,
                "path": request.url.path,
                "method": request.method,
                "error_type": exc.__class__.__name__
            }
        },
        exc_info=True
    )
    
    # Determine if it's a constraint violation
    if isinstance(exc, IntegrityError):
        error_message = "Operation violates data integrity constraints"
        error_code = "INTEGRITY_ERROR"
    else:
        error_message = "Database operation failed. Please try again."
        error_code = "DATABASE_ERROR"
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "code": error_code,
                "message": error_message
            },
            "request_id": request_id
        }
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle all unhandled exceptions.
    
    Catches any exception not handled by specific handlers and returns
    a generic error response while logging full details.
    
    Args:
        request: FastAPI request object
        exc: Exception instance
        
    Returns:
        JSONResponse with generic error message
        
    Requirements: 14.1, 14.3
    """
    request_id = get_request_id(request)
    
    logger.error(
        f"Unhandled exception: {exc.__class__.__name__}: {str(exc)}",
        extra={
            "context": {
                "request_id": request_id,
                "path": request.url.path,
                "method": request.method,
                "exception_type": exc.__class__.__name__
            }
        },
        exc_info=True
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred. Please try again."
            },
            "request_id": request_id
        }
    )


def register_exception_handlers(app) -> None:
    """
    Register all exception handlers with FastAPI application.
    
    This function should be called during application initialization to
    register all custom exception handlers.
    
    Args:
        app: FastAPI application instance
        
    Requirements: 14.1-14.6
    """
    # VMLedger custom exceptions
    app.add_exception_handler(VMLedgerError, vmledger_exception_handler)
    
    # FastAPI/Pydantic validation errors
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    
    # Database errors
    app.add_exception_handler(SQLAlchemyError, database_exception_handler)
    
    # Catch-all for unhandled exceptions
    app.add_exception_handler(Exception, general_exception_handler)
    
    logger.info("Exception handlers registered successfully")
