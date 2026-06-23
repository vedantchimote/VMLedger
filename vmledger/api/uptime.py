"""
Uptime and SLA Tracking API endpoints.
"""

import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Integer

from vmledger.database import get_db
from vmledger.models.vm import VM
from vmledger.models.ping_result import PingResult
from vmledger.models.uptime_summary import UptimeDailySummary

logger = logging.getLogger(__name__)

router = APIRouter()

class UptimeStatsResponse(BaseModel):
    vm_id: int
    period: str
    uptime_percent: float
    sla_tier: str
    total_checks: int
    successful_checks: int
    failed_checks: int
    avg_latency_ms: float | None
    max_latency_ms: float | None
    min_latency_ms: float | None
    daily_breakdown: List[Dict[str, Any]]

class BatchUptimeResponse(BaseModel):
    vm_id: int
    uptime_percent: float
    sla_tier: str


SLA_TIERS = [
    (99.99, "99.99%", "Elite"),
    (99.95, "99.95%", "Premium"),
    (99.9, "99.9%", "Standard"),
    (99.5, "99.5%", "Basic"),
    (99.0, "99%", "Low"),
    (0.0, "Below 99%", "Critical")
]

def get_sla_tier(uptime_percent: float) -> str:
    for threshold, label, _ in SLA_TIERS:
        if uptime_percent >= threshold:
            return label
    return "Below 99%"

def get_user_id(request: Request) -> int:
    return getattr(request.state, "user_id", None)

def _parse_period(period: str) -> int:
    """Parse period string to days."""
    period = period.lower()
    if period == '24h': return 1
    if period == '7d': return 7
    if period == '30d': return 30
    if period == '90d': return 90
    if period == '1y': return 365
    return 30

@router.get("/uptime/summary", response_model=List[BatchUptimeResponse])
def get_uptime_summary(
    period: str = Query("30d"),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_user_id)
):
    """Get uptime summary for all user's VMs."""
    days = _parse_period(period)
    cutoff_date = (datetime.utcnow() - timedelta(days=days)).date()
    
    # Get all VMs for user
    user_vms = db.query(VM.id).filter(VM.user_id == user_id).all()
    vm_ids = [v.id for v in user_vms]
    
    if not vm_ids:
        return []

    # Query daily summaries
    results = db.query(
        UptimeDailySummary.vm_id,
        func.sum(UptimeDailySummary.total_checks).label("total"),
        func.sum(UptimeDailySummary.successful_checks).label("success")
    ).filter(
        UptimeDailySummary.vm_id.in_(vm_ids),
        UptimeDailySummary.date >= cutoff_date
    ).group_by(UptimeDailySummary.vm_id).all()
    
    summary = []
    for vm_id, total, successful in results:
        uptime = round((successful / total * 100) if total and total > 0 else 0, 4)
        summary.append(BatchUptimeResponse(
            vm_id=vm_id,
            uptime_percent=uptime,
            sla_tier=get_sla_tier(uptime)
        ))
        
    return summary

@router.get("/{vm_id}/uptime", response_model=UptimeStatsResponse)
def get_vm_uptime(
    vm_id: int,
    period: str = Query("30d"),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_user_id)
):
    """Get detailed uptime statistics for a specific VM."""
    vm = db.query(VM).filter(VM.id == vm_id, VM.user_id == user_id).first()
    if not vm:
        raise HTTPException(status_code=404, detail="VM not found")
        
    days = _parse_period(period)
    cutoff_date = (datetime.utcnow() - timedelta(days=days)).date()
    
    # Query daily summaries
    daily_stats = db.query(
        UptimeDailySummary.date,
        UptimeDailySummary.total_checks,
        UptimeDailySummary.successful_checks,
        UptimeDailySummary.avg_latency_ms
    ).filter(
        UptimeDailySummary.vm_id == vm_id,
        UptimeDailySummary.date >= cutoff_date
    ).order_by(UptimeDailySummary.date.asc()).all()
    
    # Query current day from ping_results (since it's not rolled up yet)
    today = datetime.utcnow().date()
    today_stats = db.query(
        func.count(PingResult.id).label("total"),
        func.sum(cast(PingResult.success, Integer)).label("success"),
        func.avg(PingResult.response_time_ms).label("avg_latency"),
        func.max(PingResult.response_time_ms).label("max_latency"),
        func.min(PingResult.response_time_ms).label("min_latency")
    ).filter(
        PingResult.vm_id == vm_id,
        func.date(PingResult.timestamp) == today
    ).first()
    
    total_checks = sum(s.total_checks for s in daily_stats)
    successful_checks = sum(s.successful_checks for s in daily_stats)
    
    if today_stats and today_stats.total:
        total_checks += today_stats.total
        successful_checks += int(today_stats.success or 0)
        
    failed_checks = total_checks - successful_checks
    uptime_percent = round((successful_checks / total_checks * 100) if total_checks > 0 else 0, 4)
    
    # Combine historical and today for daily breakdown
    breakdown = []
    for stat in daily_stats:
        if stat.total_checks > 0:
            breakdown.append({
                "date": stat.date.isoformat(),
                "uptime_percent": round(stat.successful_checks / stat.total_checks * 100, 2),
                "checks": stat.total_checks
            })
            
    if today_stats and today_stats.total:
        breakdown.append({
            "date": today.isoformat(),
            "uptime_percent": round(int(today_stats.success or 0) / today_stats.total * 100, 2),
            "checks": today_stats.total
        })

    max_lat = today_stats.max_latency if today_stats and today_stats.max_latency else None
    min_lat = today_stats.min_latency if today_stats and today_stats.min_latency else None
    
    return UptimeStatsResponse(
        vm_id=vm_id,
        period=period,
        uptime_percent=uptime_percent,
        sla_tier=get_sla_tier(uptime_percent),
        total_checks=total_checks,
        successful_checks=successful_checks,
        failed_checks=failed_checks,
        avg_latency_ms=today_stats.avg_latency if today_stats else None,
        max_latency_ms=max_lat,
        min_latency_ms=min_lat,
        daily_breakdown=breakdown
    )
