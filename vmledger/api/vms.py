"""
VM Management API endpoints.

This module provides REST API endpoints for VM CRUD operations including
registration, retrieval, update, deletion, and search functionality.

Requirements: 1.1-1.6, 3.1-3.5, 7.1-7.6, 11.1-11.5
"""

import logging
import json
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, Request, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import redis

from vmledger.database import get_db
from vmledger.config import settings
from vmledger.schemas.vm_schemas import (
    VMCreateSchema,
    VMUpdateSchema,
    VMResponseSchema,
    VMListResponseSchema,
    VMFilters
)
from vmledger.services.vm_registry_service import (
    VMRegistryService,
    VMRegistryError,
    DuplicateVMError,
    VMNotFoundError,
    UnauthorizedAccessError
)
from vmledger.services.search_engine_service import SearchEngineService
from vmledger.services.credential_manager import InvalidSSHKeyError


logger = logging.getLogger(__name__)

# Initialize Redis client for caching
try:
    redis_client = redis.from_url(
        settings.redis_url,
        password=settings.redis_password if settings.redis_password else None,
        decode_responses=True
    )
except Exception as e:
    logger.warning(f"Failed to initialize Redis client: {e}. Caching will be disabled.")
    redis_client = None


# Helper function to get user_id from request state (set by auth middleware)
def get_user_id(request: Request) -> int:
    """
    Extract user_id from request state (set by authentication middleware).
    
    Args:
        request: HTTP request
        
    Returns:
        User ID
        
    Raises:
        ValueError: If user_id is not in request state
    """
    user_id = getattr(request.state, "user_id", None)
    
    if user_id is None:
        raise ValueError("User ID not found in request state")
    
    return user_id


# Create router
router = APIRouter()


@router.get(
    "",
    response_model=VMListResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="List VMs",
    description="List all VMs for the authenticated user with pagination and filtering"
)
async def list_vms(
    request: Request,
    page: int = Query(default=1, ge=1, description="Page number"),
    per_page: int = Query(default=50, ge=1, le=100, description="Items per page"),
    tags: Optional[str] = Query(default=None, description="Comma-separated tags to filter by"),
    is_reachable: Optional[bool] = Query(default=None, description="Filter by reachability status"),
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    List all VMs for the authenticated user with pagination and filtering.
    
    Features:
    - Returns paginated VM list for the authenticated user
    - Supports filtering by tags and reachability status
    - Cached in Redis with 30-second TTL for performance
    - Cache key includes user_id and query parameters for isolation
    
    Args:
        request: HTTP request with user_id in state
        page: Page number (default 1)
        per_page: Items per page (default 50, max 100)
        tags: Comma-separated tags to filter by
        is_reachable: Filter by reachability status
        db: Database session
        
    Returns:
        JSON response with paginated VM list
        
    Raises:
        401: Unauthorized (no valid token)
        500: Internal server error
        
    Requirements: 1.1, 3.1, 12.1, 13.1-13.5
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    try:
        user_id = get_user_id(request)
        
        # Parse tags if provided
        tags_list = None
        if tags:
            tags_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
        
        # Generate cache key based on user_id and query parameters
        cache_key_parts = [
            f"vmlist:user:{user_id}",
            f"page:{page}",
            f"per_page:{per_page}"
        ]
        if tags:
            cache_key_parts.append(f"tags:{tags}")
        if is_reachable is not None:
            cache_key_parts.append(f"reachable:{is_reachable}")
        cache_key = ":".join(cache_key_parts)
        
        # Try to get cached data from Redis
        cached_data = None
        if redis_client:
            try:
                cached_data = redis_client.get(cache_key)
                if cached_data:
                    logger.debug(
                        f"VM list cache hit for user {user_id}",
                        extra={"context": {"user_id": user_id, "cache_key": cache_key, "request_id": request_id}}
                    )
                    # Parse cached JSON and return
                    list_data = json.loads(cached_data)
                    return JSONResponse(
                        status_code=status.HTTP_200_OK,
                        content={
                            "success": True,
                            "data": list_data,
                            "cached": True,
                            "request_id": request_id
                        }
                    )
            except redis.RedisError as e:
                logger.warning(f"Redis cache read error: {e}")
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to decode cached VM list data: {e}")
        
        # Cache miss or Redis unavailable - fetch from database
        logger.debug(
            f"VM list cache miss for user {user_id}, fetching from database",
            extra={"context": {"user_id": user_id, "cache_key": cache_key, "request_id": request_id}}
        )
        
        # Create filters
        filters = VMFilters(
            page=page,
            per_page=per_page,
            tags=tags_list,
            is_reachable=is_reachable
        )
        
        # Get VMs
        vm_service = VMRegistryService(db)
        result = vm_service.list_vms(user_id, filters)
        
        logger.info(
            f"Listed {len(result['vms'])} VMs for user {user_id}",
            extra={
                "context": {
                    "user_id": user_id,
                    "page": page,
                    "per_page": per_page,
                    "total": result['total'],
                    "request_id": request_id
                }
            }
        )
        
        # Convert VMs to response schema
        vms_response = [
            VMResponseSchema.model_validate(vm) for vm in result['vms']
        ]
        
        # Build response data
        list_data = {
            "vms": [vm.model_dump(mode='json') for vm in vms_response],
            "total": result['total'],
            "page": result['page'],
            "per_page": result['per_page'],
            "pages": result['pages']
        }
        
        # Cache the result in Redis with 30-second TTL
        if redis_client:
            try:
                redis_client.setex(
                    cache_key,
                    30,  # 30-second TTL
                    json.dumps(list_data)
                )
                logger.debug(
                    f"VM list data cached for user {user_id}",
                    extra={"context": {"user_id": user_id, "cache_key": cache_key, "request_id": request_id}}
                )
            except redis.RedisError as e:
                logger.warning(f"Redis cache write error: {e}")
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "data": list_data,
                "cached": False,
                "request_id": request_id
            }
        )
        
    except ValueError as e:
        logger.warning(
            f"List VMs failed: {str(e)}",
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
        
    except Exception as e:
        logger.error(
            f"List VMs error: {str(e)}",
            exc_info=True,
            extra={"context": {"request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to retrieve VMs. Please try again."
                },
                "request_id": request_id
            }
        )


@router.post(
    "",
    response_model=VMResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Register VM",
    description="Register a new VM with credentials"
)
async def create_vm(
    request: Request,
    vm_data: VMCreateSchema,
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Register a new VM with credentials.
    
    Validates:
    - IP address format (IPv4 or IPv6)
    - SSH port range (1-65535)
    - SSH key format (if provided)
    - At least one credential type (SSH key or password)
    - No duplicate IP+port combination for user
    
    Args:
        request: HTTP request with user_id in state
        vm_data: VM registration data
        db: Database session
        
    Returns:
        JSON response with created VM data
        
    Raises:
        400: Validation error, duplicate VM, or invalid SSH key
        401: Unauthorized (no valid token)
        500: Internal server error
        
    Requirements: 1.1-1.6, 2.1-2.5, 3.1
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    try:
        user_id = get_user_id(request)
        
        # Create VM
        vm_service = VMRegistryService(db)
        vm = vm_service.create_vm(user_id, vm_data)
        
        logger.info(
            f"Created VM {vm.id} for user {user_id}: {vm.hostname} ({vm.ip_address}:{vm.ssh_port})",
            extra={
                "context": {
                    "user_id": user_id,
                    "vm_id": vm.id,
                    "hostname": vm.hostname,
                    "ip_address": vm.ip_address,
                    "request_id": request_id
                }
            }
        )
        
        # Invalidate caches
        invalidate_dashboard_cache(user_id)
        invalidate_vmlist_cache(user_id)
        
        # Convert to response schema
        vm_response = VMResponseSchema.model_validate(vm)
        
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "success": True,
                "data": vm_response.model_dump(mode='json'),
                "request_id": request_id
            }
        )
        
    except ValueError as e:
        logger.warning(
            f"Create VM failed: {str(e)}",
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
        
    except DuplicateVMError as e:
        logger.warning(
            f"Create VM failed: Duplicate VM - {str(e)}",
            extra={"context": {"request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error": {
                    "code": "DUPLICATE_VM",
                    "message": str(e)
                },
                "request_id": request_id
            }
        )
        
    except InvalidSSHKeyError as e:
        logger.warning(
            f"Create VM failed: Invalid SSH key - {str(e)}",
            extra={"context": {"request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error": {
                    "code": "INVALID_SSH_KEY",
                    "message": str(e)
                },
                "request_id": request_id
            }
        )
        
    except VMRegistryError as e:
        logger.warning(
            f"Create VM failed: {str(e)}",
            extra={"context": {"request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error": {
                    "code": "VM_REGISTRY_ERROR",
                    "message": str(e)
                },
                "request_id": request_id
            }
        )
        
    except Exception as e:
        logger.error(
            f"Create VM error: {str(e)}",
            exc_info=True,
            extra={"context": {"request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to create VM. Please try again."
                },
                "request_id": request_id
            }
        )

@router.get(
    "/tools/resolve",
    status_code=status.HTTP_200_OK,
    summary="Resolve hostname from IP",
    description="Automatically detect hostname from IP address"
)
async def resolve_ip(
    request: Request,
    ip: str = Query(..., description="IP address to resolve")
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    try:
        import asyncio
        import socket
        hostname, _, _ = await asyncio.to_thread(socket.gethostbyaddr, ip)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "data": {"hostname": hostname},
                "request_id": request_id
            }
        )
    except Exception as e:
        logger.debug(f"Failed to resolve hostname for IP {ip}: {e}")
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": False,
                "data": {"hostname": None},
                "error": {
                    "code": "RESOLUTION_FAILED",
                    "message": "Could not resolve hostname for IP"
                },
                "request_id": request_id
            }
        )

@router.get(
    "/alerts",
    status_code=status.HTTP_200_OK,
    summary="Get global alert history",
    description="Get alert notification history for all VMs owned by the user"
)
async def get_global_alerts(
    request: Request,
    limit: int = Query(default=50, ge=1, le=1000, description="Maximum number of results"),
    db: Session = Depends(get_db)
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    try:
        user_id = get_user_id(request)
        
        from vmledger.models.alert import Alert
        from vmledger.models.vm import VM
        alerts = (
            db.query(Alert, VM)
            .join(VM, Alert.vm_id == VM.id)
            .filter(VM.user_id == user_id)
            .order_by(Alert.sent_at.desc())
            .limit(limit)
            .all()
        )
        
        alerts_data = [
            {
                "id": alert.id,
                "vm_id": alert.vm_id,
                "hostname": vm.hostname,
                "alert_type": alert.alert_type,
                "sent_at": alert.sent_at.isoformat() if alert.sent_at else None,
                "notification_method": alert.notification_method,
                "success": alert.success,
                "error_message": alert.error_message
            }
            for alert, vm in alerts
        ]
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "data": {
                    "alerts": alerts_data,
                    "count": len(alerts_data)
                },
                "request_id": request_id
            }
        )
    except Exception as e:
        logger.error(f"Global alert history error: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to retrieve global alerts."
                },
                "request_id": request_id
            }
        )


@router.get(
    "/{vm_id}",
    response_model=VMResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Get VM details",
    description="Get details for a specific VM with user ownership verification"
)
async def get_vm(
    request: Request,
    vm_id: int,
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Get details for a specific VM.
    
    Verifies that the VM belongs to the authenticated user.
    
    Args:
        request: HTTP request with user_id in state
        vm_id: VM ID to retrieve
        db: Database session
        
    Returns:
        JSON response with VM data
        
    Raises:
        401: Unauthorized (no valid token)
        403: Forbidden (VM belongs to another user)
        404: VM not found
        500: Internal server error
        
    Requirements: 3.1, 3.2
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    try:
        user_id = get_user_id(request)
        
        # Get VM with ownership verification
        vm_service = VMRegistryService(db)
        vm = vm_service.get_vm(user_id, vm_id)
        
        logger.info(
            f"Retrieved VM {vm_id} for user {user_id}",
            extra={
                "context": {
                    "user_id": user_id,
                    "vm_id": vm_id,
                    "request_id": request_id
                }
            }
        )
        
        # Convert to response schema
        vm_response = VMResponseSchema.model_validate(vm)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "data": vm_response.model_dump(mode='json'),
                "request_id": request_id
            }
        )
        
    except ValueError as e:
        logger.warning(
            f"Get VM failed: {str(e)}",
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
        
    except VMNotFoundError as e:
        logger.warning(
            f"Get VM failed: VM not found - {str(e)}",
            extra={"context": {"vm_id": vm_id, "request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "error": {
                    "code": "VM_NOT_FOUND",
                    "message": str(e)
                },
                "request_id": request_id
            }
        )
        
    except UnauthorizedAccessError as e:
        logger.warning(
            f"Get VM failed: Unauthorized access - {str(e)}",
            extra={"context": {"vm_id": vm_id, "request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "success": False,
                "error": {
                    "code": "FORBIDDEN",
                    "message": str(e)
                },
                "request_id": request_id
            }
        )
        
    except Exception as e:
        logger.error(
            f"Get VM error: {str(e)}",
            exc_info=True,
            extra={"context": {"vm_id": vm_id, "request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to retrieve VM. Please try again."
                },
                "request_id": request_id
            }
        )


@router.put(
    "/{vm_id}",
    response_model=VMResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Update VM",
    description="Update VM details with user ownership verification"
)
async def update_vm(
    request: Request,
    vm_id: int,
    vm_data: VMUpdateSchema,
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Update VM details.
    
    Verifies that the VM belongs to the authenticated user.
    All fields are optional for partial updates.
    
    Args:
        request: HTTP request with user_id in state
        vm_id: VM ID to update
        vm_data: VM update data
        db: Database session
        
    Returns:
        JSON response with updated VM data
        
    Raises:
        400: Validation error, duplicate VM, or invalid SSH key
        401: Unauthorized (no valid token)
        403: Forbidden (VM belongs to another user)
        404: VM not found
        500: Internal server error
        
    Requirements: 3.2, 11.1, 11.2
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    try:
        user_id = get_user_id(request)
        
        # Update VM with ownership verification
        vm_service = VMRegistryService(db)
        vm = vm_service.update_vm(user_id, vm_id, vm_data)
        
        logger.info(
            f"Updated VM {vm_id} for user {user_id}",
            extra={
                "context": {
                    "user_id": user_id,
                    "vm_id": vm_id,
                    "request_id": request_id
                }
            }
        )
        
        # Invalidate caches
        invalidate_dashboard_cache(user_id)
        invalidate_vmlist_cache(user_id)
        
        # Convert to response schema
        vm_response = VMResponseSchema.model_validate(vm)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "data": vm_response.model_dump(mode='json'),
                "request_id": request_id
            }
        )
        
    except ValueError as e:
        logger.warning(
            f"Update VM failed: {str(e)}",
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
        
    except VMNotFoundError as e:
        logger.warning(
            f"Update VM failed: VM not found - {str(e)}",
            extra={"context": {"vm_id": vm_id, "request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "error": {
                    "code": "VM_NOT_FOUND",
                    "message": str(e)
                },
                "request_id": request_id
            }
        )
        
    except UnauthorizedAccessError as e:
        logger.warning(
            f"Update VM failed: Unauthorized access - {str(e)}",
            extra={"context": {"vm_id": vm_id, "request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "success": False,
                "error": {
                    "code": "FORBIDDEN",
                    "message": str(e)
                },
                "request_id": request_id
            }
        )
        
    except DuplicateVMError as e:
        logger.warning(
            f"Update VM failed: Duplicate VM - {str(e)}",
            extra={"context": {"vm_id": vm_id, "request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error": {
                    "code": "DUPLICATE_VM",
                    "message": str(e)
                },
                "request_id": request_id
            }
        )
        
    except InvalidSSHKeyError as e:
        logger.warning(
            f"Update VM failed: Invalid SSH key - {str(e)}",
            extra={"context": {"vm_id": vm_id, "request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error": {
                    "code": "INVALID_SSH_KEY",
                    "message": str(e)
                },
                "request_id": request_id
            }
        )
        
    except VMRegistryError as e:
        logger.warning(
            f"Update VM failed: {str(e)}",
            extra={"context": {"vm_id": vm_id, "request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error": {
                    "code": "VM_REGISTRY_ERROR",
                    "message": str(e)
                },
                "request_id": request_id
            }
        )
        
    except Exception as e:
        logger.error(
            f"Update VM error: {str(e)}",
            exc_info=True,
            extra={"context": {"vm_id": vm_id, "request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to update VM. Please try again."
                },
                "request_id": request_id
            }
        )


@router.delete(
    "/{vm_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete VM",
    description="Delete VM with cascade deletion of all related data"
)
async def delete_vm(
    request: Request,
    vm_id: int,
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Delete VM with cascade deletion of all related data.
    
    Verifies that the VM belongs to the authenticated user.
    Deletes:
    - VM record
    - Credentials (via cascade)
    - Ping results (via cascade)
    - Metrics (via cascade)
    - Alerts (via cascade)
    - Alert configuration (via cascade)
    
    Args:
        request: HTTP request with user_id in state
        vm_id: VM ID to delete
        db: Database session
        
    Returns:
        JSON response with success message
        
    Raises:
        401: Unauthorized (no valid token)
        403: Forbidden (VM belongs to another user)
        404: VM not found
        500: Internal server error
        
    Requirements: 3.3, 11.3, 11.4
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    try:
        user_id = get_user_id(request)
        
        # Delete VM with ownership verification
        vm_service = VMRegistryService(db)
        vm_service.delete_vm(user_id, vm_id)
        
        logger.info(
            f"Deleted VM {vm_id} for user {user_id}",
            extra={
                "context": {
                    "user_id": user_id,
                    "vm_id": vm_id,
                    "request_id": request_id
                }
            }
        )
        
        # Invalidate caches
        invalidate_dashboard_cache(user_id)
        invalidate_vmlist_cache(user_id)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "data": {
                    "message": f"VM {vm_id} deleted successfully"
                },
                "request_id": request_id
            }
        )
        
    except ValueError as e:
        logger.warning(
            f"Delete VM failed: {str(e)}",
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
        
    except VMNotFoundError as e:
        logger.warning(
            f"Delete VM failed: VM not found - {str(e)}",
            extra={"context": {"vm_id": vm_id, "request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "error": {
                    "code": "VM_NOT_FOUND",
                    "message": str(e)
                },
                "request_id": request_id
            }
        )
        
    except UnauthorizedAccessError as e:
        logger.warning(
            f"Delete VM failed: Unauthorized access - {str(e)}",
            extra={"context": {"vm_id": vm_id, "request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "success": False,
                "error": {
                    "code": "FORBIDDEN",
                    "message": str(e)
                },
                "request_id": request_id
            }
        )
        
    except VMRegistryError as e:
        logger.warning(
            f"Delete VM failed: {str(e)}",
            extra={"context": {"vm_id": vm_id, "request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error": {
                    "code": "VM_REGISTRY_ERROR",
                    "message": str(e)
                },
                "request_id": request_id
            }
        )
        
    except Exception as e:
        logger.error(
            f"Delete VM error: {str(e)}",
            exc_info=True,
            extra={"context": {"vm_id": vm_id, "request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to delete VM. Please try again."
                },
                "request_id": request_id
            }
        )


@router.get(
    "/search",
    status_code=status.HTTP_200_OK,
    summary="Search VMs",
    description="Search VMs using full-text search across metadata and deployment notes"
)
async def search_vms(
    request: Request,
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum results"),
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Search VMs using full-text search.
    
    Searches across:
    - IP addresses
    - Hostnames
    - Domains
    - Tags
    - Deployment notes
    
    Features:
    - Partial word matching
    - Relevance ranking
    - Highlighted matches in deployment notes
    - OR logic for multi-term queries
    
    Args:
        request: HTTP request with user_id in state
        q: Search query string
        limit: Maximum number of results (default 50, max 100)
        db: Database session
        
    Returns:
        JSON response with search results
        
    Raises:
        401: Unauthorized (no valid token)
        500: Internal server error
        
    Requirements: 7.1-7.6
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    try:
        user_id = get_user_id(request)
        
        # Search VMs
        search_service = SearchEngineService(db)
        results = search_service.search_vms(user_id, q, limit)
        
        logger.info(
            f"Search returned {len(results)} results for user {user_id}",
            extra={
                "context": {
                    "user_id": user_id,
                    "query": q,
                    "results_count": len(results),
                    "request_id": request_id
                }
            }
        )
        
        # Convert results to dict format
        results_data = [result.to_dict() for result in results]
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "data": {
                    "results": results_data,
                    "count": len(results_data),
                    "query": q
                },
                "request_id": request_id
            }
        )
        
    except ValueError as e:
        logger.warning(
            f"Search VMs failed: {str(e)}",
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
        
    except Exception as e:
        logger.error(
            f"Search VMs error: {str(e)}",
            exc_info=True,
            extra={"context": {"query": q, "request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Search failed. Please try again."
                },
                "request_id": request_id
            }
        )


@router.get(
    "/{vm_id}/metrics",
    status_code=status.HTTP_200_OK,
    summary="Get VM metrics history",
    description="Get historical metrics data for a VM with configurable limit"
)
async def get_vm_metrics(
    request: Request,
    vm_id: int,
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of results"),
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Get historical metrics data for a VM.
    
    Returns metrics ordered by timestamp descending (most recent first).
    Verifies that the VM belongs to the authenticated user.
    
    Args:
        request: HTTP request with user_id in state
        vm_id: VM ID to retrieve metrics for
        limit: Maximum number of results (default 100, max 1000)
        db: Database session
        
    Returns:
        JSON response with metrics history
        
    Raises:
        401: Unauthorized (no valid token)
        403: Forbidden (VM belongs to another user)
        404: VM not found
        500: Internal server error
        
    Requirements: 4.1-4.6, 5.1-5.7, 12.1-12.6
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    try:
        user_id = get_user_id(request)
        
        # Verify VM ownership
        vm_service = VMRegistryService(db)
        vm = vm_service.get_vm(user_id, vm_id)
        
        # Get metrics history
        from vmledger.services.metric_collector_service import MetricCollectorService
        metric_service = MetricCollectorService(db)
        metrics = metric_service.get_metric_history(vm_id, limit)
        
        logger.info(
            f"Retrieved {len(metrics)} metrics for VM {vm_id}",
            extra={
                "context": {
                    "user_id": user_id,
                    "vm_id": vm_id,
                    "count": len(metrics),
                    "request_id": request_id
                }
            }
        )
        
        # Convert metrics to dict format
        metrics_data = [
            {
                "id": m.id,
                "vm_id": m.vm_id,
                "timestamp": m.timestamp.isoformat() if m.timestamp else None,
                "cpu_usage_percent": m.cpu_usage_percent,
                "ram_used_mb": m.ram_used_mb,
                "ram_total_mb": m.ram_total_mb,
                "disk_used_gb": m.disk_used_gb,
                "disk_total_gb": m.disk_total_gb,
                "disk_usage_percent": m.disk_usage_percent,
                "collection_success": m.collection_success,
                "error_message": m.error_message
            }
            for m in metrics
        ]
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "data": {
                    "metrics": metrics_data,
                    "count": len(metrics_data),
                    "vm_id": vm_id
                },
                "request_id": request_id
            }
        )
        
    except ValueError as e:
        logger.warning(
            f"Get VM metrics failed: {str(e)}",
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
        
    except VMNotFoundError as e:
        logger.warning(
            f"Get VM metrics failed: VM not found - {str(e)}",
            extra={"context": {"vm_id": vm_id, "request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "error": {
                    "code": "VM_NOT_FOUND",
                    "message": str(e)
                },
                "request_id": request_id
            }
        )
        
    except UnauthorizedAccessError as e:
        logger.warning(
            f"Get VM metrics failed: Unauthorized access - {str(e)}",
            extra={"context": {"vm_id": vm_id, "request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "success": False,
                "error": {
                    "code": "FORBIDDEN",
                    "message": str(e)
                },
                "request_id": request_id
            }
        )
        
    except Exception as e:
        logger.error(
            f"Get VM metrics error: {str(e)}",
            exc_info=True,
            extra={"context": {"vm_id": vm_id, "request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to retrieve metrics. Please try again."
                },
                "request_id": request_id
            }
        )


@router.get(
    "/{vm_id}/ping",
    status_code=status.HTTP_200_OK,
    summary="Get VM ping history",
    description="Get historical ping results for a VM with configurable limit"
)
async def get_vm_ping_history(
    request: Request,
    vm_id: int,
    limit: int = Query(default=100, ge=1, le=100, description="Maximum number of results"),
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Get historical ping results for a VM.
    
    Returns ping results ordered by timestamp descending (most recent first).
    Verifies that the VM belongs to the authenticated user.
    
    Args:
        request: HTTP request with user_id in state
        vm_id: VM ID to retrieve ping history for
        limit: Maximum number of results (default 100, max 100)
        db: Database session
        
    Returns:
        JSON response with ping history
        
    Raises:
        401: Unauthorized (no valid token)
        403: Forbidden (VM belongs to another user)
        404: VM not found
        500: Internal server error
        
    Requirements: 4.1-4.6, 5.1-5.7, 12.1-12.6
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    try:
        user_id = get_user_id(request)
        
        # Verify VM ownership
        vm_service = VMRegistryService(db)
        vm = vm_service.get_vm(user_id, vm_id)
        
        # Get ping history
        from vmledger.services.health_check_service import HealthCheckService
        health_service = HealthCheckService(db)
        ping_results = health_service.get_ping_history(vm_id, limit)
        
        logger.info(
            f"Retrieved {len(ping_results)} ping results for VM {vm_id}",
            extra={
                "context": {
                    "user_id": user_id,
                    "vm_id": vm_id,
                    "count": len(ping_results),
                    "request_id": request_id
                }
            }
        )
        
        # Convert ping results to dict format
        ping_data = [
            {
                "id": p.id,
                "vm_id": p.vm_id,
                "timestamp": p.timestamp.isoformat() if p.timestamp else None,
                "success": p.success,
                "response_time_ms": p.response_time_ms,
                "error_type": p.error_type,
                "icmp_success": p.icmp_success,
                "tcp_success": p.tcp_success
            }
            for p in ping_results
        ]
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "data": {
                    "ping_results": ping_data,
                    "count": len(ping_data),
                    "vm_id": vm_id
                },
                "request_id": request_id
            }
        )
        
    except ValueError as e:
        logger.warning(
            f"Get VM ping history failed: {str(e)}",
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
        
    except VMNotFoundError as e:
        logger.warning(
            f"Get VM ping history failed: VM not found - {str(e)}",
            extra={"context": {"vm_id": vm_id, "request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "error": {
                    "code": "VM_NOT_FOUND",
                    "message": str(e)
                },
                "request_id": request_id
            }
        )
        
    except UnauthorizedAccessError as e:
        logger.warning(
            f"Get VM ping history failed: Unauthorized access - {str(e)}",
            extra={"context": {"vm_id": vm_id, "request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "success": False,
                "error": {
                    "code": "FORBIDDEN",
                    "message": str(e)
                },
                "request_id": request_id
            }
        )
        
    except Exception as e:
        logger.error(
            f"Get VM ping history error: {str(e)}",
            exc_info=True,
            extra={"context": {"vm_id": vm_id, "request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to retrieve ping history. Please try again."
                },
                "request_id": request_id
            }
        )


@router.get(
    "/{vm_id}/status",
    status_code=status.HTTP_200_OK,
    summary="Get VM current status",
    description="Get current VM status with latest ping result and metrics"
)
async def get_vm_status(
    request: Request,
    vm_id: int,
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Get current VM status with latest monitoring data.
    
    Returns:
    - VM basic information
    - Latest ping result (reachability status)
    - Latest metrics (CPU, RAM, disk usage)
    
    Verifies that the VM belongs to the authenticated user.
    
    Args:
        request: HTTP request with user_id in state
        vm_id: VM ID to retrieve status for
        db: Database session
        
    Returns:
        JSON response with current VM status
        
    Raises:
        401: Unauthorized (no valid token)
        403: Forbidden (VM belongs to another user)
        404: VM not found
        500: Internal server error
        
    Requirements: 4.1-4.6, 5.1-5.7, 12.1-12.6
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    try:
        user_id = get_user_id(request)
        
        # Get VM with latest monitoring data
        vm_service = VMRegistryService(db)
        vm_data = vm_service.get_vm_with_latest_metrics(user_id, vm_id)
        
        vm = vm_data["vm"]
        latest_metric = vm_data["latest_metric"]
        latest_ping = vm_data["latest_ping"]
        
        logger.info(
            f"Retrieved status for VM {vm_id}",
            extra={
                "context": {
                    "user_id": user_id,
                    "vm_id": vm_id,
                    "request_id": request_id
                }
            }
        )
        
        # Build response
        status_data = {
            "vm": {
                "id": vm.id,
                "hostname": vm.hostname,
                "ip_address": vm.ip_address,
                "ssh_port": vm.ssh_port,
                "is_reachable": vm.is_reachable,
                "last_seen": vm.last_seen.isoformat() if vm.last_seen else None
            },
            "latest_ping": None,
            "latest_metrics": None
        }
        
        # Add latest ping result if available
        if latest_ping:
            status_data["latest_ping"] = {
                "timestamp": latest_ping.timestamp.isoformat() if latest_ping.timestamp else None,
                "success": latest_ping.success,
                "response_time_ms": latest_ping.response_time_ms,
                "error_type": latest_ping.error_type,
                "icmp_success": latest_ping.icmp_success,
                "tcp_success": latest_ping.tcp_success
            }
        
        # Add latest metrics if available
        if latest_metric:
            status_data["latest_metrics"] = {
                "timestamp": latest_metric.timestamp.isoformat() if latest_metric.timestamp else None,
                "cpu_usage_percent": latest_metric.cpu_usage_percent,
                "ram_used_mb": latest_metric.ram_used_mb,
                "ram_total_mb": latest_metric.ram_total_mb,
                "disk_used_gb": latest_metric.disk_used_gb,
                "disk_total_gb": latest_metric.disk_total_gb,
                "disk_usage_percent": latest_metric.disk_usage_percent,
                "collection_success": latest_metric.collection_success,
                "error_message": latest_metric.error_message
            }
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "data": status_data,
                "request_id": request_id
            }
        )
        
    except ValueError as e:
        logger.warning(
            f"Get VM status failed: {str(e)}",
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
        
    except VMNotFoundError as e:
        logger.warning(
            f"Get VM status failed: VM not found - {str(e)}",
            extra={"context": {"vm_id": vm_id, "request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "error": {
                    "code": "VM_NOT_FOUND",
                    "message": str(e)
                },
                "request_id": request_id
            }
        )
        
    except UnauthorizedAccessError as e:
        logger.warning(
            f"Get VM status failed: Unauthorized access - {str(e)}",
            extra={"context": {"vm_id": vm_id, "request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "success": False,
                "error": {
                    "code": "FORBIDDEN",
                    "message": str(e)
                },
                "request_id": request_id
            }
        )
        
    except Exception as e:
        logger.error(
            f"Get VM status error: {str(e)}",
            exc_info=True,
            extra={"context": {"vm_id": vm_id, "request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to retrieve VM status. Please try again."
                },
                "request_id": request_id
            }
        )



@router.get(
    "/{vm_id}/specs",
    status_code=status.HTTP_200_OK,
    summary="Get VM Specs",
    description="Live fetch detailed hardware and OS specs from a VM via SSH"
)
def get_vm_specs(
    request: Request,
    vm_id: int,
    db: Session = Depends(get_db)
):
    """
    Live fetch detailed hardware and OS specs from a VM via SSH.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    user_id = getattr(request.state, "user_id", None)
    
    if not user_id:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"success": False, "message": "Not authenticated"}
        )
    logger.info(
        f"Fetching live specs for VM {vm_id} (user {user_id})",
        extra={"context": {"vm_id": vm_id, "request_id": request_id}}
    )
    
    try:
        from vmledger.services.vm_registry_service import VMRegistryService
        vm_service = VMRegistryService(db)
        vm = vm_service.get_vm(user_id, vm_id)
        if not vm:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "success": False,
                    "error": {
                        "code": "NOT_FOUND",
                        "message": f"VM {vm_id} not found"
                    },
                    "request_id": request_id
                }
            )
            
        from vmledger.services.metric_collector_service import MetricCollectorService
        collector = MetricCollectorService(db)
        specs = collector.fetch_vm_specs(vm_id)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "data": specs,
                "request_id": request_id
            }
        )
    except Exception as e:
        logger.error(
            f"Failed to fetch specs for VM {vm_id}: {str(e)}",
            exc_info=True,
            extra={"context": {"vm_id": vm_id, "request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": "SPECS_FETCH_ERROR",
                    "message": f"Failed to fetch VM specs: {str(e)}"
                },
                "request_id": request_id
            }
        )

@router.get(
    "/{vm_id}/alerts/config",
    status_code=status.HTTP_200_OK,
    summary="Get alert configuration",
    description="Get alert configuration for a specific VM"
)
async def get_alert_config(
    request: Request,
    vm_id: int,
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Get alert configuration for a VM.
    
    Returns the alert configuration including webhook URL, email recipient,
    cooldown period, and enabled status.
    
    Verifies that the VM belongs to the authenticated user.
    
    Args:
        request: HTTP request with user_id in state
        vm_id: VM ID to retrieve alert config for
        db: Database session
        
    Returns:
        JSON response with alert configuration
        
    Raises:
        401: Unauthorized (no valid token)
        403: Forbidden (VM belongs to another user)
        404: VM or alert config not found
        500: Internal server error
        
    Requirements: 8.1-8.7
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    try:
        user_id = get_user_id(request)
        
        # Verify VM ownership
        vm_service = VMRegistryService(db)
        vm = vm_service.get_vm(user_id, vm_id)
        
        # Get alert configuration
        from vmledger.models.alert_config import AlertConfig
        alert_config = db.query(AlertConfig).filter(
            AlertConfig.vm_id == vm_id
        ).first()
        
        if not alert_config:
            logger.warning(
                f"Alert config not found for VM {vm_id}",
                extra={"context": {"vm_id": vm_id, "request_id": request_id}}
            )
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "success": False,
                    "error": {
                        "code": "ALERT_CONFIG_NOT_FOUND",
                        "message": f"Alert configuration not found for VM {vm_id}"
                    },
                    "request_id": request_id
                }
            )
        
        logger.info(
            f"Retrieved alert config for VM {vm_id}",
            extra={
                "context": {
                    "user_id": user_id,
                    "vm_id": vm_id,
                    "request_id": request_id
                }
            }
        )
        
        # Build response
        config_data = {
            "id": alert_config.id,
            "vm_id": alert_config.vm_id,
            "enabled": alert_config.enabled,
            "webhook_url": alert_config.webhook_url,
            "email_recipient": alert_config.email_recipient,
            "cooldown_minutes": alert_config.cooldown_minutes,
            "created_at": alert_config.created_at.isoformat() if alert_config.created_at else None,
            "updated_at": alert_config.updated_at.isoformat() if alert_config.updated_at else None
        }
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "data": config_data,
                "request_id": request_id
            }
        )
        
    except ValueError as e:
        logger.warning(
            f"Get alert config failed: {str(e)}",
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
        
    except VMNotFoundError as e:
        logger.warning(
            f"Get alert config failed: VM not found - {str(e)}",
            extra={"context": {"vm_id": vm_id, "request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "error": {
                    "code": "VM_NOT_FOUND",
                    "message": str(e)
                },
                "request_id": request_id
            }
        )
        
    except UnauthorizedAccessError as e:
        logger.warning(
            f"Get alert config failed: Unauthorized access - {str(e)}",
            extra={"context": {"vm_id": vm_id, "request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "success": False,
                "error": {
                    "code": "FORBIDDEN",
                    "message": str(e)
                },
                "request_id": request_id
            }
        )
        
    except Exception as e:
        logger.error(
            f"Get alert config error: {str(e)}",
            exc_info=True,
            extra={"context": {"vm_id": vm_id, "request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to retrieve alert configuration. Please try again."
                },
                "request_id": request_id
            }
        )


@router.put(
    "/{vm_id}/alerts/config",
    status_code=status.HTTP_200_OK,
    summary="Update alert configuration",
    description="Update alert configuration for a specific VM with validation"
)
async def update_alert_config(
    request: Request,
    vm_id: int,
    config_data: Dict[str, Any],
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Update alert configuration for a VM.
    
    Validates:
    - Webhook URL format (if provided)
    - Email address format (if provided)
    - At least one notification method is configured
    - Cooldown period is within valid range (1-1440 minutes)
    
    Verifies that the VM belongs to the authenticated user.
    
    Args:
        request: HTTP request with user_id in state
        vm_id: VM ID to update alert config for
        config_data: Alert configuration data
        db: Database session
        
    Returns:
        JSON response with updated alert configuration
        
    Raises:
        400: Validation error
        401: Unauthorized (no valid token)
        403: Forbidden (VM belongs to another user)
        404: VM or alert config not found
        500: Internal server error
        
    Requirements: 8.1-8.7
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    try:
        user_id = get_user_id(request)
        
        # Verify VM ownership
        vm_service = VMRegistryService(db)
        vm = vm_service.get_vm(user_id, vm_id)
        
        # Get alert configuration
        from vmledger.models.alert_config import AlertConfig
        alert_config = db.query(AlertConfig).filter(
            AlertConfig.vm_id == vm_id
        ).first()
        
        if not alert_config:
            logger.warning(
                f"Alert config not found for VM {vm_id}",
                extra={"context": {"vm_id": vm_id, "request_id": request_id}}
            )
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "success": False,
                    "error": {
                        "code": "ALERT_CONFIG_NOT_FOUND",
                        "message": f"Alert configuration not found for VM {vm_id}"
                    },
                    "request_id": request_id
                }
            )
        
        # Validate and update fields
        if "enabled" in config_data:
            if not isinstance(config_data["enabled"], bool):
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "success": False,
                        "error": {
                            "code": "VALIDATION_ERROR",
                            "message": "Field 'enabled' must be a boolean"
                        },
                        "request_id": request_id
                    }
                )
            alert_config.enabled = config_data["enabled"]
        
        if "webhook_url" in config_data:
            webhook_url = config_data["webhook_url"]
            if webhook_url is not None:
                # Validate webhook URL format
                if not isinstance(webhook_url, str) or not webhook_url.startswith(("http://", "https://")):
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={
                            "success": False,
                            "error": {
                                "code": "VALIDATION_ERROR",
                                "message": "Webhook URL must start with http:// or https://"
                            },
                            "request_id": request_id
                        }
                    )
            alert_config.webhook_url = webhook_url
        
        if "email_recipient" in config_data:
            email = config_data["email_recipient"]
            if email is not None:
                # Validate email format
                import re
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                if not isinstance(email, str) or not re.match(email_pattern, email):
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={
                            "success": False,
                            "error": {
                                "code": "VALIDATION_ERROR",
                                "message": "Invalid email address format"
                            },
                            "request_id": request_id
                        }
                    )
            alert_config.email_recipient = email
        
        if "cooldown_minutes" in config_data:
            cooldown = config_data["cooldown_minutes"]
            if not isinstance(cooldown, int) or cooldown < 1 or cooldown > 1440:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "success": False,
                        "error": {
                            "code": "VALIDATION_ERROR",
                            "message": "Cooldown period must be between 1 and 1440 minutes"
                        },
                        "request_id": request_id
                    }
                )
            alert_config.cooldown_minutes = cooldown
        
        # Validate at least one notification method is configured
        if alert_config.webhook_url is None and alert_config.email_recipient is None:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "success": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "At least one notification method (webhook_url or email_recipient) must be configured"
                    },
                    "request_id": request_id
                }
            )
        
        # Save changes
        db.commit()
        db.refresh(alert_config)
        
        logger.info(
            f"Updated alert config for VM {vm_id}",
            extra={
                "context": {
                    "user_id": user_id,
                    "vm_id": vm_id,
                    "request_id": request_id
                }
            }
        )
        
        # Build response
        config_response = {
            "id": alert_config.id,
            "vm_id": alert_config.vm_id,
            "enabled": alert_config.enabled,
            "webhook_url": alert_config.webhook_url,
            "email_recipient": alert_config.email_recipient,
            "cooldown_minutes": alert_config.cooldown_minutes,
            "created_at": alert_config.created_at.isoformat() if alert_config.created_at else None,
            "updated_at": alert_config.updated_at.isoformat() if alert_config.updated_at else None
        }
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "data": config_response,
                "request_id": request_id
            }
        )
        
    except ValueError as e:
        logger.warning(
            f"Update alert config failed: {str(e)}",
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
        
    except VMNotFoundError as e:
        logger.warning(
            f"Update alert config failed: VM not found - {str(e)}",
            extra={"context": {"vm_id": vm_id, "request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "error": {
                    "code": "VM_NOT_FOUND",
                    "message": str(e)
                },
                "request_id": request_id
            }
        )
        
    except UnauthorizedAccessError as e:
        logger.warning(
            f"Update alert config failed: Unauthorized access - {str(e)}",
            extra={"context": {"vm_id": vm_id, "request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "success": False,
                "error": {
                    "code": "FORBIDDEN",
                    "message": str(e)
                },
                "request_id": request_id
            }
        )
        
    except Exception as e:
        logger.error(
            f"Update alert config error: {str(e)}",
            exc_info=True,
            extra={"context": {"vm_id": vm_id, "request_id": request_id}}
        )
        db.rollback()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to update alert configuration. Please try again."
                },
                "request_id": request_id
            }
        )


@router.get(
    "/{vm_id}/alerts/history",
    status_code=status.HTTP_200_OK,
    summary="Get alert history",
    description="Get alert notification history for a specific VM"
)
async def get_alert_history(
    request: Request,
    vm_id: int,
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of results"),
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Get alert notification history for a VM.
    
    Returns alerts ordered by sent_at descending (most recent first).
    Verifies that the VM belongs to the authenticated user.
    
    Args:
        request: HTTP request with user_id in state
        vm_id: VM ID to retrieve alert history for
        limit: Maximum number of results (default 100, max 1000)
        db: Database session
        
    Returns:
        JSON response with alert history
        
    Raises:
        401: Unauthorized (no valid token)
        403: Forbidden (VM belongs to another user)
        404: VM not found
        500: Internal server error
        
    Requirements: 8.1-8.7
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    try:
        user_id = get_user_id(request)
        
        # Verify VM ownership
        vm_service = VMRegistryService(db)
        vm = vm_service.get_vm(user_id, vm_id)
        
        # Get alert history
        from vmledger.models.alert import Alert
        alerts = (
            db.query(Alert)
            .filter(Alert.vm_id == vm_id)
            .order_by(Alert.sent_at.desc())
            .limit(limit)
            .all()
        )
        
        logger.info(
            f"Retrieved {len(alerts)} alerts for VM {vm_id}",
            extra={
                "context": {
                    "user_id": user_id,
                    "vm_id": vm_id,
                    "count": len(alerts),
                    "request_id": request_id
                }
            }
        )
        
        # Convert alerts to dict format
        alerts_data = [
            {
                "id": alert.id,
                "vm_id": alert.vm_id,
                "alert_type": alert.alert_type,
                "sent_at": alert.sent_at.isoformat() if alert.sent_at else None,
                "notification_method": alert.notification_method,
                "success": alert.success,
                "error_message": alert.error_message
            }
            for alert in alerts
        ]
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "data": {
                    "alerts": alerts_data,
                    "count": len(alerts_data),
                    "vm_id": vm_id
                },
                "request_id": request_id
            }
        )
        
    except ValueError as e:
        logger.warning(
            f"Get alert history failed: {str(e)}",
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
        
    except VMNotFoundError as e:
        logger.warning(
            f"Get alert history failed: VM not found - {str(e)}",
            extra={"context": {"vm_id": vm_id, "request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "error": {
                    "code": "VM_NOT_FOUND",
                    "message": str(e)
                },
                "request_id": request_id
            }
        )
        
    except UnauthorizedAccessError as e:
        logger.warning(
            f"Get alert history failed: Unauthorized access - {str(e)}",
            extra={"context": {"vm_id": vm_id, "request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "success": False,
                "error": {
                    "code": "FORBIDDEN",
                    "message": str(e)
                },
                "request_id": request_id
            }
        )
        
    except Exception as e:
        logger.error(
            f"Get alert history error: {str(e)}",
            exc_info=True,
            extra={"context": {"vm_id": vm_id, "request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to retrieve alert history. Please try again."
                },
                "request_id": request_id
            }
        )


@router.get(
    "/dashboard",
    status_code=status.HTTP_200_OK,
    summary="Get dashboard data",
    description="Get all VMs with latest metrics and ping results, optimized with caching"
)
async def get_dashboard(
    request: Request,
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Get dashboard data with all VMs and their latest monitoring information.
    
    Features:
    - Returns all VMs for the authenticated user
    - Includes latest ping result for each VM
    - Includes latest metrics for each VM
    - Optimized with database joins to minimize queries
    - Cached in Redis with 30-second TTL for performance
    - Cache key includes user_id for isolation
    
    Args:
        request: HTTP request with user_id in state
        db: Database session
        
    Returns:
        JSON response with dashboard data
        
    Raises:
        401: Unauthorized (no valid token)
        500: Internal server error
        
    Requirements: 12.1-12.6, 13.1-13.5
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    try:
        user_id = get_user_id(request)
        
        # Try to get cached data from Redis
        cache_key = f"dashboard:user:{user_id}"
        cached_data = None
        
        if redis_client:
            try:
                cached_data = redis_client.get(cache_key)
                if cached_data:
                    logger.debug(
                        f"Dashboard cache hit for user {user_id}",
                        extra={"context": {"user_id": user_id, "request_id": request_id}}
                    )
                    # Parse cached JSON and return
                    dashboard_data = json.loads(cached_data)
                    return JSONResponse(
                        status_code=status.HTTP_200_OK,
                        content={
                            "success": True,
                            "data": dashboard_data,
                            "cached": True,
                            "request_id": request_id
                        }
                    )
            except redis.RedisError as e:
                logger.warning(f"Redis cache read error: {e}")
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to decode cached dashboard data: {e}")
        
        # Cache miss or Redis unavailable - fetch from database
        logger.debug(
            f"Dashboard cache miss for user {user_id}, fetching from database",
            extra={"context": {"user_id": user_id, "request_id": request_id}}
        )
        
        # Use optimized service method with joins
        vm_service = VMRegistryService(db)
        vms_with_data = vm_service.list_vms_with_latest_metrics(user_id)
        
        # Build dashboard response
        dashboard_vms = []
        for item in vms_with_data:
            vm = item["vm"]
            latest_metric = item["latest_metric"]
            latest_ping = item["latest_ping"]
            
            # Deserialize tags if needed (for SQLite compatibility)
            tags = vm.tags
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except json.JSONDecodeError:
                    tags = []
            
            vm_data = {
                "id": vm.id,
                "ip_address": vm.ip_address,
                "hostname": vm.hostname,
                "domain": vm.domain,
                "ssh_port": vm.ssh_port,
                "tags": tags if tags else [],
                "is_reachable": vm.is_reachable,
                "last_seen": vm.last_seen.isoformat() if vm.last_seen else None,
                "created_at": vm.created_at.isoformat() if vm.created_at else None,
                "updated_at": vm.updated_at.isoformat() if vm.updated_at else None,
                "latest_ping": None,
                "latest_metrics": None
            }
            
            # Add latest ping result if available
            if latest_ping:
                vm_data["latest_ping"] = {
                    "timestamp": latest_ping.timestamp.isoformat() if latest_ping.timestamp else None,
                    "success": latest_ping.success,
                    "response_time_ms": latest_ping.response_time_ms,
                    "error_type": latest_ping.error_type
                }
            
            # Add latest metrics if available
            if latest_metric:
                vm_data["latest_metrics"] = {
                    "timestamp": latest_metric.timestamp.isoformat() if latest_metric.timestamp else None,
                    "cpu_usage_percent": latest_metric.cpu_usage_percent,
                    "ram_used_mb": latest_metric.ram_used_mb,
                    "ram_total_mb": latest_metric.ram_total_mb,
                    "disk_used_gb": latest_metric.disk_used_gb,
                    "disk_total_gb": latest_metric.disk_total_gb,
                    "disk_usage_percent": latest_metric.disk_usage_percent,
                    "collection_success": latest_metric.collection_success
                }
            
            dashboard_vms.append(vm_data)
        
        dashboard_data = {
            "vms": dashboard_vms,
            "total_vms": len(dashboard_vms),
            "reachable_vms": sum(1 for vm in dashboard_vms if vm.get("is_reachable") is True),
            "unreachable_vms": sum(1 for vm in dashboard_vms if vm.get("is_reachable") is False)
        }
        
        # Cache the result in Redis with 30-second TTL
        if redis_client:
            try:
                redis_client.setex(
                    cache_key,
                    30,  # 30-second TTL
                    json.dumps(dashboard_data)
                )
                logger.debug(
                    f"Dashboard data cached for user {user_id}",
                    extra={"context": {"user_id": user_id, "request_id": request_id}}
                )
            except redis.RedisError as e:
                logger.warning(f"Redis cache write error: {e}")
        
        logger.info(
            f"Retrieved dashboard data for user {user_id}: {len(dashboard_vms)} VMs",
            extra={
                "context": {
                    "user_id": user_id,
                    "total_vms": len(dashboard_vms),
                    "request_id": request_id
                }
            }
        )
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "data": dashboard_data,
                "cached": False,
                "request_id": request_id
            }
        )
        
    except ValueError as e:
        logger.warning(
            f"Get dashboard failed: {str(e)}",
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
        
    except Exception as e:
        logger.error(
            f"Get dashboard error: {str(e)}",
            exc_info=True,
            extra={"context": {"request_id": request_id}}
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to retrieve dashboard data. Please try again."
                },
                "request_id": request_id
            }
        )


def invalidate_dashboard_cache(user_id: int) -> None:
    """
    Invalidate dashboard cache for a user.
    
    Should be called when:
    - VM is created
    - VM is updated
    - VM is deleted
    - Monitoring data is updated
    
    Args:
        user_id: User ID whose cache should be invalidated
    """
    if redis_client:
        try:
            cache_key = f"dashboard:user:{user_id}"
            redis_client.delete(cache_key)
            logger.debug(f"Invalidated dashboard cache for user {user_id}")
        except redis.RedisError as e:
            logger.warning(f"Failed to invalidate dashboard cache: {e}")


def invalidate_vmlist_cache(user_id: int) -> None:
    """
    Invalidate VM list cache for a user.
    
    This function invalidates all cached VM list queries for a user by using
    a pattern match to delete all cache keys that start with the user's VM list prefix.
    This ensures that all paginated and filtered views are invalidated.
    
    Should be called when:
    - VM is created
    - VM is updated
    - VM is deleted
    
    Args:
        user_id: User ID whose cache should be invalidated
    """
    if redis_client:
        try:
            # Use pattern matching to delete all VM list cache keys for this user
            # This handles all pagination and filter combinations
            pattern = f"vmlist:user:{user_id}:*"
            
            # Get all matching keys
            keys = redis_client.keys(pattern)
            
            if keys:
                # Delete all matching keys
                redis_client.delete(*keys)
                logger.debug(f"Invalidated {len(keys)} VM list cache entries for user {user_id}")
            else:
                logger.debug(f"No VM list cache entries to invalidate for user {user_id}")
                
        except redis.RedisError as e:
            logger.warning(f"Failed to invalidate VM list cache: {e}")


# ─── Manual Trigger Endpoints ─────────────────────────────────────────────────
# These endpoints allow users to trigger monitoring tasks on-demand for a single
# VM instead of waiting for the scheduled Celery Beat intervals.


@router.post(
    "/{vm_id}/trigger/ping",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger Manual Ping Check",
    description="Dispatch a ping check task for a single VM immediately"
)
async def trigger_ping_check(
    vm_id: int,
    request: Request,
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Trigger an on-demand ping check for a specific VM.

    Dispatches the ping_check_task Celery task immediately.
    The task runs asynchronously; poll the VM status endpoint for results.
    """
    try:
        user_id = get_user_id(request)
        vm_service = VMRegistryService(db)
        vm = vm_service.get_vm(user_id=user_id, vm_id=vm_id)

        from vmledger.tasks import ping_check_task
        task_result = ping_check_task.delay(vm.id)

        logger.info(f"Manual ping check triggered for VM {vm_id} by user {user_id}, task_id={task_result.id}")

        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "success": True,
                "message": f"Ping check dispatched for VM {vm.hostname}",
                "data": {
                    "task_id": task_result.id,
                    "vm_id": vm.id,
                    "hostname": vm.hostname,
                }
            }
        )

    except VMNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "VM not found"}
        )
    except UnauthorizedAccessError:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"success": False, "message": "Not authorized to access this VM"}
        )
    except Exception as e:
        logger.error(f"Failed to trigger ping check for VM {vm_id}: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "message": "Failed to trigger ping check"}
        )


@router.post(
    "/{vm_id}/trigger/dns-check",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger Manual DNS Resolution",
    description="Dispatch a DNS resolution task for a single VM immediately"
)
async def trigger_dns_check(
    vm_id: int,
    request: Request,
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Trigger an on-demand DNS resolution check for a specific VM.

    Resolves the VM hostname and compares against the registered IP address.
    The task runs asynchronously; refresh the VM details to see updated results.
    """
    try:
        user_id = get_user_id(request)
        vm_service = VMRegistryService(db)
        vm = vm_service.get_vm(user_id=user_id, vm_id=vm_id)

        from vmledger.tasks import dns_resolve_task
        task_result = dns_resolve_task.delay(vm.id)

        logger.info(f"Manual DNS check triggered for VM {vm_id} by user {user_id}, task_id={task_result.id}")

        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "success": True,
                "message": f"DNS resolution dispatched for VM {vm.hostname}",
                "data": {
                    "task_id": task_result.id,
                    "vm_id": vm.id,
                    "hostname": vm.hostname,
                }
            }
        )

    except VMNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "VM not found"}
        )
    except UnauthorizedAccessError:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"success": False, "message": "Not authorized to access this VM"}
        )
    except Exception as e:
        logger.error(f"Failed to trigger DNS check for VM {vm_id}: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "message": "Failed to trigger DNS check"}
        )


@router.post(
    "/{vm_id}/trigger/collect-metrics",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger Manual Metrics Collection",
    description="Dispatch a metrics collection task for a single VM immediately"
)
async def trigger_collect_metrics(
    vm_id: int,
    request: Request,
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Trigger an on-demand metrics collection for a specific VM.

    Collects CPU, RAM, and Disk usage via SSH.
    The task runs asynchronously; refresh the VM details to see updated metrics.
    """
    try:
        user_id = get_user_id(request)
        vm_service = VMRegistryService(db)
        vm = vm_service.get_vm(user_id=user_id, vm_id=vm_id)

        from vmledger.tasks import collect_metrics_task
        task_result = collect_metrics_task.delay(vm.id)

        logger.info(f"Manual metrics collection triggered for VM {vm_id} by user {user_id}, task_id={task_result.id}")

        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "success": True,
                "message": f"Metrics collection dispatched for VM {vm.hostname}",
                "data": {
                    "task_id": task_result.id,
                    "vm_id": vm.id,
                    "hostname": vm.hostname,
                }
            }
        )

    except VMNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "VM not found"}
        )
    except UnauthorizedAccessError:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"success": False, "message": "Not authorized to access this VM"}
        )
    except Exception as e:
        logger.error(f"Failed to trigger metrics collection for VM {vm_id}: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "message": "Failed to trigger metrics collection"}
        )
