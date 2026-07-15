"""
Audit Admin API Routes - Dashboard Data Endpoints
Provides audit trail data for admin dashboard visualization
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import csv
import io
import pandas as pd

from ...dependencies.auth import get_admin_user
from ...database.session import get_db
from ...services.audit.audit_service import AuditService
from ...utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/audit/admin", tags=["Audit Admin"])


@router.get("/audit-logs")
async def get_audit_logs(
    tenant_id: str = Query("default"),
    event_type: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_admin_user)
):
    """
    Get audit logs for dashboard.
    Admin-only endpoint for audit trail visualization.
    """
    audit_service = AuditService(db)
    
    try:
        if user_id:
            logs = audit_service.get_user_audit_logs(user_id, limit=limit, offset=offset)
        else:
            logs = audit_service.get_tenant_audit_logs(tenant_id, event_type=event_type, limit=limit, offset=offset)
        
        return {
            "logs": [
                {
                    "id": str(log.id),
                    "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                    "event_type": log.event_type,
                    "event_name": log.event_name,
                    "event_category": log.event_category,
                    "description": log.description,
                    "user_id": log.user_id,
                    "session_id": str(log.session_id) if log.session_id else None,
                    "ip_address": log.ip_address,
                    "status": log.status,
                    "severity": log.severity,
                    "metadata": log.metadata
                }
                for log in logs
            ],
            "total": len(logs),
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Failed to get audit logs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve audit logs")


@router.get("/sessions")
async def get_sessions(
    tenant_id: str = Query("default"),
    user_id: Optional[str] = Query(None),
    active_only: bool = Query(False),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_admin_user)
):
    """
    Get session data for dashboard.
    Admin-only endpoint for session tracking visualization.
    """
    audit_service = AuditService(db)
    
    try:
        from ...database.audit_models import Session
        from sqlalchemy import desc
        
        tenant = audit_service.get_tenant_by_id(tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        query = db.query(Session).filter(Session.tenant_id == tenant.id)
        
        if user_id:
            user = audit_service.get_user_by_id(user_id)
            if user:
                query = query.filter(Session.user_id == user.id)
        
        if active_only:
            query = query.filter(Session.is_active == True)
        
        sessions = query.order_by(desc(Session.login_time)).limit(limit).offset(offset).all()
        
        return {
            "sessions": [
                {
                    "id": str(session.id),
                    "user_id": session.user_id,
                    "login_time": session.login_time.isoformat() if session.login_time else None,
                    "logout_time": session.logout_time.isoformat() if session.logout_time else None,
                    "session_duration_seconds": session.session_duration_seconds,
                    "ip_address": session.ip_address,
                    "browser": session.browser,
                    "os": session.os,
                    "device_type": session.device_type,
                    "is_active": session.is_active,
                    "logout_reason": session.logout_reason
                }
                for session in sessions
            ],
            "total": len(sessions),
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Failed to get sessions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve sessions")


@router.get("/processing-jobs")
async def get_processing_jobs(
    tenant_id: str = Query("default"),
    user_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_admin_user)
):
    """
    Get processing jobs for dashboard.
    Admin-only endpoint for job tracking visualization.
    """
    audit_service = AuditService(db)
    
    try:
        from ...database.audit_models import ProcessingJob
        from sqlalchemy import desc
        
        tenant = audit_service.get_tenant_by_id(tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        query = db.query(ProcessingJob).filter(
            ProcessingJob.tenant_id == tenant.id,
            ProcessingJob.upload_time >= cutoff_date
        )
        
        if user_id:
            user = audit_service.get_user_by_id(user_id)
            if user:
                query = query.filter(ProcessingJob.user_id == user.id)
        
        if status:
            query = query.filter(ProcessingJob.status == status)
        
        jobs = query.order_by(desc(ProcessingJob.upload_time)).limit(limit).offset(offset).all()
        
        return {
            "jobs": [
                {
                    "id": str(job.id),
                    "job_id": job.job_id,
                    "user_id": job.user_id,
                    "original_filename": job.original_filename,
                    "file_size_bytes": job.file_size_bytes,
                    "processing_mode": job.processing_mode,
                    "status": job.status,
                    "upload_time": job.upload_time.isoformat() if job.upload_time else None,
                    "start_time": job.start_time.isoformat() if job.start_time else None,
                    "end_time": job.end_time.isoformat() if job.end_time else None,
                    "processing_time_ms": job.processing_time_ms,
                    "transaction_count": job.transaction_count,
                    "error_code": job.error_code,
                    "error_message": job.error_message
                }
                for job in jobs
            ],
            "total": len(jobs),
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Failed to get processing jobs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve processing jobs")


@router.get("/job-events/{job_id}")
async def get_job_events(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_admin_user)
):
    """
    Get job events timeline for a specific job.
    Admin-only endpoint for job timeline visualization.
    """
    audit_service = AuditService(db)
    
    try:
        from ...database.audit_models import JobEvent
        from sqlalchemy import desc
        
        job = audit_service.get_processing_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Processing job not found")
        
        events = db.query(JobEvent).filter(
            JobEvent.job_id == job.id
        ).order_by(desc(JobEvent.timestamp)).all()
        
        return {
            "job_id": job_id,
            "events": [
                {
                    "id": str(event.id),
                    "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                    "event_type": event.event_type,
                    "event_name": event.event_name,
                    "event_category": event.event_category,
                    "description": event.description,
                    "status": event.status,
                    "metadata": event.metadata
                }
                for event in events
            ],
            "total": len(events)
        }
    except Exception as e:
        logger.error(f"Failed to get job events: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve job events")


@router.get("/download-logs")
async def get_download_logs(
    tenant_id: str = Query("default"),
    user_id: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_admin_user)
):
    """
    Get download logs for dashboard.
    Admin-only endpoint for download tracking visualization.
    """
    audit_service = AuditService(db)
    
    try:
        from ...database.audit_models import DownloadLog
        from sqlalchemy import desc
        
        tenant = audit_service.get_tenant_by_id(tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        query = db.query(DownloadLog).filter(
            DownloadLog.tenant_id == tenant.id,
            DownloadLog.download_time >= cutoff_date
        )
        
        if user_id:
            user = audit_service.get_user_by_id(user_id)
            if user:
                query = query.filter(DownloadLog.user_id == user.id)
        
        logs = query.order_by(desc(DownloadLog.download_time)).limit(limit).offset(offset).all()
        
        return {
            "logs": [
                {
                    "id": str(log.id),
                    "job_id": log.job_id,
                    "user_id": log.user_id,
                    "filename": log.filename,
                    "file_size_bytes": log.file_size_bytes,
                    "download_time": log.download_time.isoformat() if log.download_time else None,
                    "ip_address": log.ip_address,
                    "browser": log.browser,
                    "os": log.os,
                    "download_number": log.download_number
                }
                for log in logs
            ],
            "total": len(logs),
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Failed to get download logs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve download logs")


@router.get("/parser-metrics")
async def get_parser_metrics(
    tenant_id: str = Query("default"),
    bank_name: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_admin_user)
):
    """
    Get parser metrics for dashboard.
    Admin-only endpoint for parser performance visualization.
    """
    audit_service = AuditService(db)
    
    try:
        from ...database.audit_models import ParserMetric
        from sqlalchemy import desc
        
        tenant = audit_service.get_tenant_by_id(tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        query = db.query(ParserMetric).join(ProcessingJob).filter(
            ProcessingJob.tenant_id == tenant.id,
            ProcessingJob.upload_time >= cutoff_date
        )
        
        if bank_name:
            query = query.filter(ParserMetric.bank_name == bank_name)
        
        metrics = query.order_by(desc(ParserMetric.created_at)).limit(limit).offset(offset).all()
        
        return {
            "metrics": [
                {
                    "id": str(metric.id),
                    "job_id": metric.job_id,
                    "parser_type": metric.parser_type,
                    "parser_name": metric.parser_name,
                    "bank_name": metric.bank_name,
                    "execution_time_ms": metric.execution_time_ms,
                    "transactions_extracted": metric.transactions_extracted,
                    "confidence_score": metric.confidence_score,
                    "fallback_level": metric.fallback_level,
                    "status": metric.status,
                    "error_message": metric.error_message,
                    "created_at": metric.created_at.isoformat() if metric.created_at else None
                }
                for metric in metrics
            ],
            "total": len(metrics),
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Failed to get parser metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve parser metrics")


@router.get("/bank-performance")
async def get_bank_performance(
    tenant_id: str = Query("default"),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_admin_user)
):
    """
    Get aggregated bank performance metrics for dashboard.
    Admin-only endpoint for performance summary visualization.
    """
    audit_service = AuditService(db)
    
    try:
        performance = audit_service.get_bank_performance(tenant_id, days=days)
        
        return {
            "tenant_id": tenant_id,
            "days": days,
            "performance": performance
        }
    except Exception as e:
        logger.error(f"Failed to get bank performance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve bank performance")


@router.get("/dashboard-summary")
async def get_dashboard_summary(
    tenant_id: str = Query("default"),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_admin_user)
):
    """
    Get dashboard summary statistics.
    Admin-only endpoint for high-level metrics.
    """
    audit_service = AuditService(db)
    
    try:
        from ...database.audit_models import ProcessingJob, Session, AuditLog, DownloadLog
        from sqlalchemy import func, desc
        from datetime import timedelta
        
        tenant = audit_service.get_tenant_by_id(tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Processing job stats
        job_stats = db.query(
            func.count(ProcessingJob.id).label('total_jobs'),
            func.sum(func.case((ProcessingJob.status == 'COMPLETED', 1), else_=0)).label('completed_jobs'),
            func.sum(func.case((ProcessingJob.status == 'FAILED', 1), else_=0)).label('failed_jobs'),
            func.avg(ProcessingJob.processing_time_ms).label('avg_processing_time_ms')
        ).filter(
            ProcessingJob.tenant_id == tenant.id,
            ProcessingJob.upload_time >= cutoff_date
        ).first()
        
        # Session stats
        session_stats = db.query(
            func.count(Session.id).label('total_sessions'),
            func.sum(func.case((Session.is_active == True, 1), else_=0)).label('active_sessions'),
            func.avg(Session.session_duration_seconds).label('avg_session_duration')
        ).filter(
            Session.tenant_id == tenant.id,
            Session.login_time >= cutoff_date
        ).first()
        
        # Download stats
        download_stats = db.query(
            func.count(DownloadLog.id).label('total_downloads'),
            func.sum(DownloadLog.file_size_bytes).label('total_bytes_downloaded')
        ).filter(
            DownloadLog.tenant_id == tenant.id,
            DownloadLog.download_time >= cutoff_date
        ).first()
        
        # Recent activity
        recent_jobs = db.query(ProcessingJob).filter(
            ProcessingJob.tenant_id == tenant.id,
            ProcessingJob.upload_time >= cutoff_date
        ).order_by(desc(ProcessingJob.upload_time)).limit(5).all()
        
        return {
            "tenant_id": tenant_id,
            "days": days,
            "summary": {
                "processing_jobs": {
                    "total": job_stats.total_jobs or 0,
                    "completed": job_stats.completed_jobs or 0,
                    "failed": job_stats.failed_jobs or 0,
                    "avg_processing_time_ms": float(job_stats.avg_processing_time_ms) if job_stats.avg_processing_time_ms else 0
                },
                "sessions": {
                    "total": session_stats.total_sessions or 0,
                    "active": session_stats.active_sessions or 0,
                    "avg_duration_seconds": float(session_stats.avg_session_duration) if session_stats.avg_session_duration else 0
                },
                "downloads": {
                    "total": download_stats.total_downloads or 0,
                    "total_bytes": download_stats.total_bytes_downloaded or 0
                }
            },
            "recent_activity": [
                {
                    "job_id": job.job_id,
                    "filename": job.original_filename,
                    "status": job.status,
                    "upload_time": job.upload_time.isoformat() if job.upload_time else None
                }
                for job in recent_jobs
            ]
        }
    except Exception as e:
        logger.error(f"Failed to get dashboard summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve dashboard summary")


@router.get("/export/audit-logs/csv")
async def export_audit_logs_csv(
    tenant_id: str = Query("default"),
    event_type: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_admin_user)
):
    """
    Export audit logs to CSV format.
    Admin-only endpoint for audit compliance reporting.
    """
    audit_service = AuditService(db)
    
    try:
        from ...database.audit_models import AuditLog
        from sqlalchemy import desc
        
        tenant = audit_service.get_tenant_by_id(tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        query = db.query(AuditLog).filter(
            AuditLog.tenant_id == tenant.id,
            AuditLog.timestamp >= cutoff_date
        )
        
        if event_type:
            query = query.filter(AuditLog.event_type == event_type)
        
        if user_id:
            user = audit_service.get_user_by_id(user_id)
            if user:
                query = query.filter(AuditLog.user_id == user.id)
        
        logs = query.order_by(desc(AuditLog.timestamp)).all()
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "ID", "Timestamp", "Event Type", "Event Name", "Event Category",
            "Description", "User ID", "Session ID", "IP Address", "User Agent",
            "Status", "Severity", "Error Message", "Metadata"
        ])
        
        # Write rows
        for log in logs:
            writer.writerow([
                str(log.id),
                log.timestamp.isoformat() if log.timestamp else "",
                log.event_type or "",
                log.event_name or "",
                log.event_category or "",
                log.description or "",
                str(log.user_id) if log.user_id else "",
                str(log.session_id) if log.session_id else "",
                log.ip_address or "",
                log.user_agent or "",
                log.status or "",
                log.severity or "",
                log.error_message or "",
                str(log.metadata) if log.metadata else ""
            ])
        
        output.seek(0)
        
        # Generate filename with timestamp
        filename = f"audit_logs_{tenant_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"Failed to export audit logs CSV: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to export audit logs")


@router.get("/export/audit-logs/excel")
async def export_audit_logs_excel(
    tenant_id: str = Query("default"),
    event_type: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_admin_user)
):
    """
    Export audit logs to Excel format.
    Admin-only endpoint for audit compliance reporting.
    """
    audit_service = AuditService(db)
    
    try:
        from ...database.audit_models import AuditLog
        from sqlalchemy import desc
        
        tenant = audit_service.get_tenant_by_id(tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        query = db.query(AuditLog).filter(
            AuditLog.tenant_id == tenant.id,
            AuditLog.timestamp >= cutoff_date
        )
        
        if event_type:
            query = query.filter(AuditLog.event_type == event_type)
        
        if user_id:
            user = audit_service.get_user_by_id(user_id)
            if user:
                query = query.filter(AuditLog.user_id == user.id)
        
        logs = query.order_by(desc(AuditLog.timestamp)).all()
        
        # Create DataFrame
        data = []
        for log in logs:
            data.append({
                "ID": str(log.id),
                "Timestamp": log.timestamp.isoformat() if log.timestamp else "",
                "Event Type": log.event_type or "",
                "Event Name": log.event_name or "",
                "Event Category": log.event_category or "",
                "Description": log.description or "",
                "User ID": str(log.user_id) if log.user_id else "",
                "Session ID": str(log.session_id) if log.session_id else "",
                "IP Address": log.ip_address or "",
                "User Agent": log.user_agent or "",
                "Status": log.status or "",
                "Severity": log.severity or "",
                "Error Message": log.error_message or "",
                "Metadata": str(log.metadata) if log.metadata else ""
            })
        
        df = pd.DataFrame(data)
        
        # Create Excel in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Audit Logs', index=False)
        
        output.seek(0)
        
        # Generate filename with timestamp
        filename = f"audit_logs_{tenant_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"Failed to export audit logs Excel: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to export audit logs")


@router.get("/export/sessions/csv")
async def export_sessions_csv(
    tenant_id: str = Query("default"),
    user_id: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_admin_user)
):
    """
    Export sessions to CSV format.
    Admin-only endpoint for session audit reporting.
    """
    audit_service = AuditService(db)
    
    try:
        from ...database.audit_models import Session
        from sqlalchemy import desc
        
        tenant = audit_service.get_tenant_by_id(tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        query = db.query(Session).filter(
            Session.tenant_id == tenant.id,
            Session.login_time >= cutoff_date
        )
        
        if user_id:
            user = audit_service.get_user_by_id(user_id)
            if user:
                query = query.filter(Session.user_id == user.id)
        
        sessions = query.order_by(desc(Session.login_time)).all()
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "ID", "User ID", "Login Time", "Logout Time", "Session Duration (seconds)",
            "IP Address", "User Agent", "Browser", "OS", "Device Type",
            "Is Active", "Logout Reason"
        ])
        
        # Write rows
        for session in sessions:
            writer.writerow([
                str(session.id),
                str(session.user_id) if session.user_id else "",
                session.login_time.isoformat() if session.login_time else "",
                session.logout_time.isoformat() if session.logout_time else "",
                session.session_duration_seconds or 0,
                session.ip_address or "",
                session.user_agent or "",
                session.browser or "",
                session.os or "",
                session.device_type or "",
                session.is_active,
                session.logout_reason or ""
            ])
        
        output.seek(0)
        
        # Generate filename with timestamp
        filename = f"sessions_{tenant_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"Failed to export sessions CSV: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to export sessions")


@router.get("/export/processing-jobs/excel")
async def export_processing_jobs_excel(
    tenant_id: str = Query("default"),
    user_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_admin_user)
):
    """
    Export processing jobs to Excel format.
    Admin-only endpoint for job audit reporting.
    """
    audit_service = AuditService(db)
    
    try:
        from ...database.audit_models import ProcessingJob
        from sqlalchemy import desc
        
        tenant = audit_service.get_tenant_by_id(tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        query = db.query(ProcessingJob).filter(
            ProcessingJob.tenant_id == tenant.id,
            ProcessingJob.upload_time >= cutoff_date
        )
        
        if user_id:
            user = audit_service.get_user_by_id(user_id)
            if user:
                query = query.filter(ProcessingJob.user_id == user.id)
        
        if status:
            query = query.filter(ProcessingJob.status == status)
        
        jobs = query.order_by(desc(ProcessingJob.upload_time)).all()
        
        # Create DataFrame
        data = []
        for job in jobs:
            data.append({
                "Job ID": job.job_id or "",
                "User ID": str(job.user_id) if job.user_id else "",
                "Original Filename": job.original_filename or "",
                "File Size (bytes)": job.file_size_bytes or 0,
                "Processing Mode": job.processing_mode or "",
                "Status": job.status or "",
                "Upload Time": job.upload_time.isoformat() if job.upload_time else "",
                "Start Time": job.start_time.isoformat() if job.start_time else "",
                "End Time": job.end_time.isoformat() if job.end_time else "",
                "Processing Time (ms)": job.processing_time_ms or 0,
                "Transaction Count": job.transaction_count or 0,
                "Error Code": job.error_code or "",
                "Error Message": job.error_message or ""
            })
        
        df = pd.DataFrame(data)
        
        # Create Excel in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Processing Jobs', index=False)
        
        output.seek(0)
        
        # Generate filename with timestamp
        filename = f"processing_jobs_{tenant_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"Failed to export processing jobs Excel: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to export processing jobs")
