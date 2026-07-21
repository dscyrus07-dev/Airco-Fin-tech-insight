"""
Supabase Audit Service - Multi-Tenant Audit System
Production-grade audit logging with tenant isolation
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func
import uuid
import logging

from app.database.audit_models import (
    Tenant, User, Session, AuditLog, Batch, ProcessingJob, JobEvent,
    HygieneReport, ReportGenerationLog, DownloadLog, ParserMetric, UnsupportedFormatQueue,
    RawTransaction, StatementMetadata,
)

logger = logging.getLogger(__name__)


class AuditService:
    """Core audit service for Supabase multi-tenant audit logging"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ============================================
    # TENANT OPERATIONS
    # ============================================
    
    def create_tenant(
        self,
        tenant_id: str,
        tenant_name: str,
        tenant_slug: str,
        plan: str = 'FREE',
        max_users: int = 5,
        max_storage_gb: int = 10,
        max_jobs_per_month: int = 100
    ) -> Tenant:
        """Create a new tenant"""
        tenant = Tenant(
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            tenant_slug=tenant_slug,
            plan=plan,
            max_users=max_users,
            max_storage_gb=max_storage_gb,
            max_jobs_per_month=max_jobs_per_month
        )
        self.db.add(tenant)
        self.db.commit()
        self.db.refresh(tenant)
        logger.info(f"Created tenant: {tenant_id}")
        return tenant
    
    def get_tenant_by_id(self, tenant_id: str) -> Optional[Tenant]:
        """Get tenant by ID"""
        return self.db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
    
    def get_tenant_by_slug(self, slug: str) -> Optional[Tenant]:
        """Get tenant by slug"""
        return self.db.query(Tenant).filter(Tenant.tenant_slug == slug).first()
    
    # ============================================
    # USER OPERATIONS
    # ============================================
    
    def create_user(
        self,
        tenant_id: str,
        user_id: str,
        email: str,
        full_name: Optional[str] = None,
        role: str = 'USER',
        auth_provider: str = 'KEYCLOAK',
        auth_provider_id: Optional[str] = None
    ) -> User:
        """Create a new user"""
        tenant = self.get_tenant_by_id(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant not found: {tenant_id}")
        
        user = User(
            tenant_id=tenant.id,
            user_id=user_id,
            email=email,
            full_name=full_name,
            role=role,
            auth_provider=auth_provider,
            auth_provider_id=auth_provider_id
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        logger.info(f"Created user: {user_id} for tenant: {tenant_id}")
        return user
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        return self.db.query(User).filter(User.user_id == user_id).first()
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        return self.db.query(User).filter(User.email == email).first()

    def _get_or_create_user(
        self,
        user_id: str,
        tenant_id: str = "default",
        email: Optional[str] = None,
        full_name: Optional[str] = None,
    ) -> User:
        """Return existing user row or auto-provision tenant+user on first encounter."""
        user = self.get_user_by_id(user_id)
        if user:
            return user

        # Ensure tenant exists
        tenant = self.get_tenant_by_id(tenant_id)
        if not tenant:
            try:
                tenant = Tenant(
                    tenant_id=tenant_id,
                    tenant_name=tenant_id.capitalize(),
                    tenant_slug=tenant_id.lower().replace(" ", "-"),
                    plan="FREE",
                )
                self.db.add(tenant)
                self.db.commit()
                self.db.refresh(tenant)
                logger.info(f"Auto-created tenant: {tenant_id}")
            except Exception:
                self.db.rollback()
                tenant = self.get_tenant_by_id(tenant_id)

        user = User(
            tenant_id=tenant.id,
            user_id=user_id,
            email=email or f"{user_id}@auto.local",
            full_name=full_name or user_id,
            role="USER",
            auth_provider="KEYCLOAK",
            is_active=True,
        )
        try:
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
            logger.info(f"Auto-created user: {user_id} for tenant: {tenant_id}")
        except Exception:
            self.db.rollback()
            user = self.get_user_by_id(user_id)
        return user
    
    def update_user_login(self, user_id: str, ip_address: str) -> User:
        """Update user login statistics"""
        user = self.get_user_by_id(user_id)
        if user:
            user.last_login_at = datetime.now(timezone.utc)
            user.login_count = (user.login_count or 0) + 1
            self.db.commit()
            self.db.refresh(user)
        return user
    
    # ============================================
    # SESSION OPERATIONS
    # ============================================
    
    def create_session(
        self,
        tenant_id: str,
        user_id: str,
        session_token: str,
        ip_address: str,
        user_agent: str,
        browser: Optional[str] = None,
        os: Optional[str] = None,
        device_type: Optional[str] = None
    ) -> Session:
        """Create a new session"""
        user = self.get_user_by_id(user_id)
        if not user:
            raise ValueError(f"User not found: {user_id}")
        
        session = Session(
            tenant_id=user.tenant_id,
            user_id=user.id,
            session_token=session_token,
            ip_address=ip_address,
            user_agent=user_agent,
            browser=browser,
            os=os,
            device_type=device_type
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        logger.info(f"Created session for user: {user_id}")
        return session
    
    def end_session(
        self,
        session_token: str,
        logout_reason: str = 'USER_LOGOUT'
    ) -> Optional[Session]:
        """End a session"""
        session = self.db.query(Session).filter(
            Session.session_token == session_token,
            Session.is_active == True
        ).first()
        
        if session:
            session.is_active = False
            session.logout_time = datetime.now(timezone.utc)
            session.logout_reason = logout_reason
            if session.login_time:
                duration = (session.logout_time - session.login_time).total_seconds()
                session.session_duration_seconds = int(duration)
            self.db.commit()
            self.db.refresh(session)
            logger.info(f"Ended session: {session_token}")
        
        return session
    
    def get_active_session(self, session_token: str) -> Optional[Session]:
        """Get active session by token"""
        return self.db.query(Session).filter(
            Session.session_token == session_token,
            Session.is_active == True
        ).first()
    
    # ============================================
    # AUDIT LOG OPERATIONS
    # ============================================
    
    def create_audit_log(
        self,
        tenant_id: str,
        event_type: str,
        event_name: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        event_category: Optional[str] = None,
        description: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        status: str = 'SUCCESS',
        severity: str = 'INFO',
        error_message: Optional[str] = None
    ) -> AuditLog:
        """Create an audit log entry"""
        tenant = self.get_tenant_by_id(tenant_id)
        if not tenant:
            # Auto-provision tenant so audit logs are never silently dropped
            auto_user = self._get_or_create_user(user_id=user_id or "system", tenant_id=tenant_id)
            tenant = self.get_tenant_by_id(tenant_id)
        
        user = None
        if user_id:
            user = self.get_user_by_id(user_id)
        
        session = None
        if session_id:
            session = self.db.query(Session).filter(Session.session_token == session_id).first()
        
        audit_log = AuditLog(
            tenant_id=tenant.id,
            user_id=user.id if user else None,
            session_id=session.id if session else None,
            event_type=event_type,
            event_name=event_name,
            event_category=event_category,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            extra_data=metadata or {},
            status=status,
            severity=severity,
            error_message=error_message
        )
        self.db.add(audit_log)
        self.db.commit()
        self.db.refresh(audit_log)
        return audit_log
    
    def get_user_audit_logs(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditLog]:
        """Get audit logs for a user"""
        user = self.get_user_by_id(user_id)
        if not user:
            return []
        
        return self.db.query(AuditLog).filter(
            AuditLog.user_id == user.id
        ).order_by(desc(AuditLog.timestamp)).limit(limit).offset(offset).all()
    
    def get_tenant_audit_logs(
        self,
        tenant_id: str,
        event_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditLog]:
        """Get audit logs for a tenant"""
        tenant = self.get_tenant_by_id(tenant_id)
        if not tenant:
            return []
        
        query = self.db.query(AuditLog).filter(AuditLog.tenant_id == tenant.id)
        
        if event_type:
            query = query.filter(AuditLog.event_type == event_type)
        
        return query.order_by(desc(AuditLog.timestamp)).limit(limit).offset(offset).all()
    
    # ============================================
    # PROCESSING JOB OPERATIONS
    # ============================================
    
    def create_processing_job(
        self,
        tenant_id: str,
        user_id: str,
        job_id: str,
        original_filename: str,
        file_hash: str,
        file_size_bytes: int,
        processing_mode: str = 'FREE',
        batch_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> ProcessingJob:
        """Create a new processing job — auto-provisions tenant/user if they don't exist."""
        user = self._get_or_create_user(user_id=user_id, tenant_id=tenant_id)
        if not user:
            raise ValueError(f"Could not resolve user: {user_id}")

        session = None
        if session_id:
            session = self.db.query(Session).filter(Session.session_token == session_id).first()
        
        batch = None
        if batch_id:
            batch = self.db.query(Batch).filter(Batch.batch_id == batch_id).first()
        
        job = ProcessingJob(
            tenant_id=user.tenant_id,
            user_id=user.id,
            session_id=session.id if session else None,
            batch_id=batch.id if batch else None,
            job_id=job_id,
            original_filename=original_filename,
            file_hash=file_hash,
            file_size_bytes=file_size_bytes,
            processing_mode=processing_mode,
            status='QUEUED'
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        logger.info(f"Created processing job: {job_id}")
        return job
    
    def update_processing_job(
        self,
        job_id: str,
        status: Optional[str] = None,
        bank_name: Optional[str] = None,
        page_count: Optional[int] = None,
        transaction_count: Optional[int] = None,
        parser_used: Optional[str] = None,
        fallback_used: Optional[bool] = None,
        fallback_level: Optional[int] = None,
        confidence_score: Optional[float] = None,
        processing_time_ms: Optional[int] = None,
        error_message: Optional[str] = None,
        report_object_key: Optional[str] = None
    ) -> Optional[ProcessingJob]:
        """Update a processing job"""
        try:
            # Recover from aborted transaction state if needed
            self.db.rollback()
        except Exception:
            pass  # No active transaction to rollback
        
        job = self.db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
        
        if job:
            if status:
                job.status = status
                if status == 'COMPLETED':
                    job.completed_at = datetime.now(timezone.utc)
                elif status == 'PROCESSING' and not job.processing_start_time:
                    job.processing_start_time = datetime.now(timezone.utc)
            
            if bank_name:
                job.bank_name = bank_name
            if page_count is not None:
                job.page_count = page_count
            if transaction_count is not None:
                job.transaction_count = transaction_count
            if parser_used:
                job.parser_used = parser_used
            if fallback_used is not None:
                job.fallback_used = fallback_used
            if fallback_level is not None:
                job.fallback_level = fallback_level
            if confidence_score is not None:
                job.confidence_score = confidence_score
            if processing_time_ms is not None:
                job.processing_time_ms = processing_time_ms
                if job.processing_start_time:
                    job.processing_end_time = datetime.now(timezone.utc)
            if error_message:
                job.error_message = error_message
            if report_object_key:
                job.report_object_key = report_object_key
            
            self.db.commit()
            self.db.refresh(job)
        
        return job
    
    def get_processing_job(self, job_id: str) -> Optional[ProcessingJob]:
        """Get processing job by ID"""
        return self.db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
    
    def get_user_processing_jobs(
        self,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[ProcessingJob]:
        """Get processing jobs for a user"""
        user = self.get_user_by_id(user_id)
        if not user:
            return []
        
        query = self.db.query(ProcessingJob).filter(ProcessingJob.user_id == user.id)
        
        if status:
            query = query.filter(ProcessingJob.status == status)
        
        return query.order_by(desc(ProcessingJob.upload_time)).limit(limit).all()
    
    # ============================================
    # JOB EVENT OPERATIONS
    # ============================================
    
    def create_job_event(
        self,
        job_id: str,
        event_type: str,
        event_name: str,
        event_category: Optional[str] = None,
        description: Optional[str] = None,
        status: str = 'SUCCESS',
        duration_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> JobEvent:
        """Create a job event"""
        job = self.get_processing_job(job_id)
        if not job:
            raise ValueError(f"Processing job not found: {job_id}")
        
        event = JobEvent(
            tenant_id=job.tenant_id,
            job_id=job.id,
            event_type=event_type,
            event_name=event_name,
            event_category=event_category,
            description=description,
            status=status,
            duration_ms=duration_ms,
            extra_data=metadata or {},
            error_message=error_message,
            correlation_id=correlation_id
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event
    
    def get_job_events(self, job_id: str) -> List[JobEvent]:
        """Get all events for a job"""
        job = self.get_processing_job(job_id)
        if not job:
            return []
        
        return self.db.query(JobEvent).filter(
            JobEvent.job_id == job.id
        ).order_by(JobEvent.timestamp).all()
    
    def get_user_activity_timeline(
        self,
        user_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get user's complete activity timeline"""
        user = self.get_user_by_id(user_id)
        if not user:
            return []
        
        events = self.db.query(JobEvent).join(ProcessingJob).filter(
            ProcessingJob.user_id == user.id
        ).order_by(desc(JobEvent.timestamp)).limit(limit).all()
        
        timeline = []
        for event in events:
            job = self.db.query(ProcessingJob).filter(
                ProcessingJob.id == event.job_id
            ).first()
            
            timeline.append({
                'event_name': event.event_name,
                'event_type': event.event_type,
                'timestamp': event.timestamp,
                'status': event.status,
                'duration_ms': event.duration_ms,
                'metadata': event.extra_data,
                'job_id': job.job_id if job else None,
                'filename': job.original_filename if job else None
            })
        
        return timeline
    
    # ============================================
    # HYGIENE REPORT OPERATIONS
    # ============================================
    
    def create_hygiene_report(
        self,
        job_id: str,
        format_id: Optional[str],
        page_count: int,
        transaction_count: int,
        is_healthy: bool,
        warnings: List[str],
        issues: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        check_duration_ms: Optional[int] = None,
        file_name: Optional[str] = None,
        bank_name: Optional[str] = None,
        user_id: Optional[str] = None,
        goal_id: Optional[str] = None,
    ) -> HygieneReport:
        """Create a hygiene report with accurate job-linked fields."""
        from datetime import date as _date

        job = self.get_processing_job(job_id)
        if not job:
            raise ValueError(f"Processing job not found: {job_id}")

        def _to_date(v):
            if v is None or v == "" or v == "N/A":
                return None
            if isinstance(v, _date):
                return v
            try:
                return datetime.fromisoformat(str(v)[:10]).date()
            except Exception:
                try:
                    return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
                except Exception:
                    return None

        start_d = _to_date(start_date)
        end_d = _to_date(end_date)
        pages = int(page_count or 0)
        txns = int(transaction_count or 0)
        resolved_file = (
            file_name
            or getattr(job, "original_filename", None)
            or getattr(job, "file_name", None)
            or "statement.pdf"
        )
        resolved_user = user_id or getattr(job, "user_id", None) or "SYSTEM"
        resolved_bank = bank_name or job.bank_name or "unknown"
        resolved_goal = goal_id or "GENERAL"
        warn_list = list(warnings or [])
        issue_list = list(issues or [])
        has_structure = pages > 0
        has_txns = txns > 0
        has_dates = bool(start_d and end_d)

        report = HygieneReport(
            tenant_id=job.tenant_id,
            job_id=job.id,
            file_name=resolved_file,
            bank_name=resolved_bank,
            user_id=str(resolved_user),
            goal_id=str(resolved_goal),
            format_id=format_id,
            page_count=pages,
            transaction_count=txns,
            is_healthy=bool(is_healthy),
            warnings=warn_list,
            issues=issue_list,
            start_date=start_d,
            end_date=end_d,
            check_duration_ms=check_duration_ms,
            has_valid_structure=has_structure,
            has_valid_transactions=has_txns,
            has_valid_dates=has_dates,
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    
    # ============================================
    # PARSER METRIC OPERATIONS
    # ============================================
    
    def create_parser_metric(
        self,
        job_id: str,
        parser_type: str,
        parser_name: str,
        bank_name: Optional[str],
        execution_time_ms: int,
        transactions_extracted: int,
        confidence_score: Optional[float],
        fallback_level: int = 0,
        status: str = 'SUCCESS',
        error_message: Optional[str] = None
    ) -> ParserMetric:
        """Create a parser metric entry"""
        job = self.get_processing_job(job_id)
        if not job:
            raise ValueError(f"Processing job not found: {job_id}")
        
        metric = ParserMetric(
            tenant_id=job.tenant_id,
            job_id=job.id,
            parser_type=parser_type,
            parser_name=parser_name,
            bank_name=bank_name,
            execution_time_ms=execution_time_ms,
            transactions_extracted=transactions_extracted,
            confidence_score=confidence_score,
            fallback_level=fallback_level,
            status=status,
            error_message=error_message
        )
        self.db.add(metric)
        self.db.commit()
        self.db.refresh(metric)
        return metric
    
    def get_bank_performance(
        self,
        tenant_id: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get parser performance by bank"""
        tenant = self.get_tenant_by_id(tenant_id)
        if not tenant:
            return []
        
        from datetime import timedelta
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        results = self.db.query(
            ParserMetric.bank_name,
            func.count(ParserMetric.id).label('total_jobs'),
            func.avg(ParserMetric.execution_time_ms).label('avg_time_ms'),
            func.avg(ParserMetric.transactions_extracted).label('avg_transactions'),
            func.avg(ParserMetric.confidence_score).label('avg_confidence')
        ).join(ProcessingJob).filter(
            ProcessingJob.tenant_id == tenant.id,
            ProcessingJob.upload_time >= cutoff_date
        ).group_by(ParserMetric.bank_name).all()
        
        performance = []
        for result in results:
            performance.append({
                'bank_name': result.bank_name,
                'total_jobs': result.total_jobs,
                'avg_time_ms': float(result.avg_time_ms) if result.avg_time_ms else 0,
                'avg_transactions': float(result.avg_transactions) if result.avg_transactions else 0,
                'avg_confidence': float(result.avg_confidence) if result.avg_confidence else 0
            })
        
        return performance
    
    # ============================================
    # DOWNLOAD LOG OPERATIONS
    # ============================================
    
    def create_download_log(
        self,
        job_id: str,
        user_id: str,
        filename: str,
        ip_address: str,
        download_number: int,
        file_size_bytes: Optional[int] = None,
        user_agent: Optional[str] = None,
        browser: Optional[str] = None,
        os: Optional[str] = None
    ) -> DownloadLog:
        """Create a download log entry"""
        job = self.get_processing_job(job_id)
        if not job:
            raise ValueError(f"Processing job not found: {job_id}")
        
        user = self.get_user_by_id(user_id)
        if not user:
            raise ValueError(f"User not found: {user_id}")
        
        download = DownloadLog(
            tenant_id=job.tenant_id,
            job_id=job.id,
            user_id=user.id,
            filename=filename,
            file_size_bytes=file_size_bytes,
            ip_address=ip_address,
            user_agent=user_agent,
            browser=browser,
            os=os,
            download_number=download_number
        )
        self.db.add(download)
        self.db.commit()
        self.db.refresh(download)
        
        # Update user download count
        user.total_downloads = (user.total_downloads or 0) + 1
        self.db.commit()
        
        return download
    
    def get_user_downloads(self, user_id: str, limit: int = 50) -> List[DownloadLog]:
        """Get download logs for a user"""
        user = self.get_user_by_id(user_id)
        if not user:
            return []
        
        return self.db.query(DownloadLog).filter(
            DownloadLog.user_id == user.id
        ).order_by(desc(DownloadLog.download_time)).limit(limit).all()
    
    # ============================================
    # UNSUPPORTED FORMAT QUEUE OPERATIONS
    # ============================================
    
    def add_to_unsupported_queue(
        self,
        job_id: str,
        issue_type: str,
        issue_description: str,
        issue_severity: str = 'MEDIUM',
        suggested_action: Optional[str] = None
    ) -> UnsupportedFormatQueue:
        """Add job to unsupported format queue"""
        job = self.get_processing_job(job_id)
        if not job:
            raise ValueError(f"Processing job not found: {job_id}")
        
        queue_entry = UnsupportedFormatQueue(
            tenant_id=job.tenant_id,
            job_id=job.id,
            queue_status='QUEUED',
            issue_type=issue_type,
            issue_description=issue_description,
            issue_severity=issue_severity,
            suggested_action=suggested_action
        )
        self.db.add(queue_entry)
        self.db.commit()
        self.db.refresh(queue_entry)
        return queue_entry
    
    def resolve_unsupported_format(
        self,
        queue_id: str,
        resolved_by: str,
        resolution_notes: str,
        resolution_method: str
    ) -> Optional[UnsupportedFormatQueue]:
        """Resolve an unsupported format issue"""
        entry = self.db.query(UnsupportedFormatQueue).filter(
            UnsupportedFormatQueue.id == queue_id
        ).first()
        
        if entry:
            resolver = self.get_user_by_id(resolved_by)
            if resolver:
                entry.queue_status = 'RESOLVED'
                entry.resolved_by = resolver.id
                entry.resolution_time = datetime.now(timezone.utc)
                entry.resolution_notes = resolution_notes
                entry.resolution_method = resolution_method
                self.db.commit()
                self.db.refresh(entry)
        
        return entry
    
    def get_unsupported_queue(
        self,
        tenant_id: str,
        status: Optional[str] = None
    ) -> List[UnsupportedFormatQueue]:
        """Get unsupported format queue for tenant"""
        tenant = self.get_tenant_by_id(tenant_id)
        if not tenant:
            return []
        
        query = self.db.query(UnsupportedFormatQueue).filter(
            UnsupportedFormatQueue.tenant_id == tenant.id
        )
        
        if status:
            query = query.filter(UnsupportedFormatQueue.queue_status == status)
        
        return query.order_by(desc(UnsupportedFormatQueue.queued_time)).all()
    
    # ============================================
    # REPORT GENERATION LOG OPERATIONS
    # ============================================
    
    def create_report_generation_log(
        self,
        job_id: str,
        excel_filename: str,
        sheet_count: int,
        template_used: Optional[str] = None
    ) -> ReportGenerationLog:
        """Create a report generation log entry"""
        job = self.get_processing_job(job_id)
        if not job:
            raise ValueError(f"Processing job not found: {job_id}")
        
        log = ReportGenerationLog(
            tenant_id=job.tenant_id,
            job_id=job.id,
            excel_filename=excel_filename,
            sheet_count=sheet_count,
            template_used=template_used,
            status='STARTED'
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log
    
    def update_report_generation_log(
        self,
        job_id: str,
        generation_time_ms: int,
        file_size_bytes: int,
        status: str = 'COMPLETED',
        error_message: Optional[str] = None
    ) -> Optional[ReportGenerationLog]:
        """Update report generation log"""
        log = self.db.query(ReportGenerationLog).filter(
            ReportGenerationLog.job_id == self.get_processing_job(job_id).id
        ).first()
        
        if log:
            log.generation_end_time = datetime.now(timezone.utc)
            log.generation_time_ms = generation_time_ms
            log.excel_file_size_bytes = file_size_bytes
            log.status = status
            log.error_message = error_message
            self.db.commit()
            self.db.refresh(log)
        
        return log

    # ============================================
    # RAW TRANSACTION OPERATIONS
    # ============================================

    def create_raw_transaction(
        self,
        job_id: str,
        raw_json: Any,
    ) -> RawTransaction:
        """Persist the full extracted transaction list as JSONB."""
        job = self.get_processing_job(job_id)
        if not job:
            raise ValueError(f"Processing job not found: {job_id}")
        record = RawTransaction(
            job_id=job.id,
            raw_json=raw_json,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    # ============================================
    # STATEMENT METADATA  (extracted summary per statement)
    # ============================================

    def save_statement_metadata(
        self,
        job_id: str,
        metadata: Dict[str, Any],
    ) -> Optional[StatementMetadata]:
        """
        Upsert a statement_metadata row for the given job.
        `metadata` must be the dict produced by
        `StatementMetadataExtractor.extract(...).to_dict()`.
        """
        job = self.db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
        if not job:
            logger.warning(f"save_statement_metadata: job {job_id} not found")
            return None

        # Coerce ISO date strings to date objects (NUMERIC + DATE Supabase columns)
        from datetime import date as _date
        def _to_date(v):
            if v is None or isinstance(v, _date):
                return v
            try:
                return datetime.fromisoformat(str(v)[:10]).date()
            except Exception:
                return None

        record = self.db.query(StatementMetadata).filter(
            StatementMetadata.job_id == job.job_id
        ).first()

        fields = {
            "tenant_id": job.tenant_id,
            "user_id": job.user_id,
            "job_id": job.job_id,
            "chitid": metadata.get("chitid") or job.job_id,
            # Prefer the real upload name stored on the job; metadata often carries
            # a temp basename (e.g. tmpabc123.pdf) from the local processing path.
            "filename": job.original_filename or metadata.get("filename"),
            "bankname": metadata.get("bankname") or job.bank_name,
            "accountno": metadata.get("accountno"),
            "formatidentify": metadata.get("formatidentify"),
            "startdate": _to_date(metadata.get("startdate")),
            "enddate": _to_date(metadata.get("enddate")),
            "nooftransactions": int(metadata.get("nooftransactions") or 0),
            "havesalary": bool(metadata.get("havesalary")),
            "noofsalarycredit": int(metadata.get("noofsalarycredit") or 0),
            "amtofsalarycredit": metadata.get("amtofsalarycredit") or 0,
            "hasloanrepayment": bool(metadata.get("hasloanrepayment")),
            "noofloanrepayments": int(metadata.get("noofloanrepayments") or 0),
            "amtofloanrepayments": metadata.get("amtofloanrepayments") or 0,
            "loancredit": bool(metadata.get("loancredit")),
            "noofloancredits": int(metadata.get("noofloancredits") or 0),
            "amtofloancredits": metadata.get("amtofloancredits") or 0,
            "noofcredits": int(metadata.get("noofcredits") or 0),
            "amtofcredits": metadata.get("amtofcredits") or 0,
            "noofcashdeposits": int(metadata.get("noofcashdeposits") or 0),
            "amtofcashdeposits": metadata.get("amtofcashdeposits") or 0,
            "noofupicredits": int(metadata.get("noofupicredits") or 0),
            "amtofupicredits": metadata.get("amtofupicredits") or 0,
            "noofneft_imps_credits": int(metadata.get("noofneft_imps_credits") or 0),
            "amtofneft_imps_credits": metadata.get("amtofneft_imps_credits") or 0,
            "noofnetbanking_credits": int(metadata.get("noofnetbanking_credits") or 0),
            "amtofnetbanking_credits": metadata.get("amtofnetbanking_credits") or 0,
            "noofdebits": int(metadata.get("noofdebits") or 0),
            "amtofdebits": metadata.get("amtofdebits") or 0,
            "noofcashwithdrawals": int(metadata.get("noofcashwithdrawals") or 0),
            "amtofcashwithdrawals": metadata.get("amtofcashwithdrawals") or 0,
            "noofupidebits": int(metadata.get("noofupidebits") or 0),
            "amtofupidebits": metadata.get("amtofupidebits") or 0,
            "noofneft_imps_debits": int(metadata.get("noofneft_imps_debits") or 0),
            "amtofneft_imps_debits": metadata.get("amtofneft_imps_debits") or 0,
            "noofnetbanking_debits": int(metadata.get("noofnetbanking_debits") or 0),
            "amtofnetbanking_debits": metadata.get("amtofnetbanking_debits") or 0,
            "extra": metadata.get("extra") or {},
        }

        if record:
            for k, v in fields.items():
                setattr(record, k, v)
        else:
            record = StatementMetadata(**fields)
            self.db.add(record)

        self.db.commit()
        self.db.refresh(record)
        return record

    # ============================================
    # FINALISE JOB AUDIT  (single atomic write)
    # ============================================

    def finalize_job_audit(
        self,
        job_id: str,
        *,
        hygiene_result=None,
        parser_metrics_collected: Optional[List[Dict[str, Any]]] = None,
        raw_transactions: Optional[List[Dict[str, Any]]] = None,
        excel_path: Optional[str] = None,
        sheet_count: int = 11,
        template_used: Optional[str] = None,
        generation_time_ms: int = 0,
        transaction_count: int = 0,
        classified_transactions: Optional[List[Dict[str, Any]]] = None,
        statement_header: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Called ONCE after the Excel file has been written successfully.
        Persists all collected audit artefacts atomically using a FRESH database session
        to avoid issues with poisoned transactions from the processing pipeline.
        """
        import os as _os
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import NullPool

        _db_url = _os.getenv("DATABASE_URL", "")

        def _new_session():
            """Always returns a brand-new connection — never a pooled one."""
            eng = create_engine(_db_url, poolclass=NullPool)
            sess = sessionmaker(autocommit=False, autoflush=False, bind=eng)()
            return sess, eng

        def _run(fn):
            """Run fn(audit_service) in its own isolated session, then close it."""
            s, e = _new_session()
            try:
                fn(AuditService(s))
                s.commit()
            except Exception as _ex:
                try:
                    s.rollback()
                except Exception:
                    pass
                logger.warning("finalize_job_audit sub-step failed (non-fatal): %s", _ex)
            finally:
                try:
                    s.close()
                except Exception:
                    pass
                try:
                    e.dispose()
                except Exception:
                    pass

        # 1. Hygiene report
        if hygiene_result is not None:
            _run(lambda svc: svc.create_hygiene_report(
                job_id=job_id,
                format_id=getattr(hygiene_result, 'format_id', None),
                page_count=getattr(hygiene_result, 'page_count', 0),
                transaction_count=getattr(hygiene_result, 'transaction_count', transaction_count),
                is_healthy=getattr(hygiene_result, 'is_healthy', True),
                warnings=getattr(hygiene_result, 'warnings', []),
                issues=getattr(hygiene_result, 'issues', []),
                start_date=getattr(hygiene_result, 'start_date', None),
                end_date=getattr(hygiene_result, 'end_date', None),
                check_duration_ms=getattr(hygiene_result, 'check_duration_ms', None),
                file_name=getattr(hygiene_result, 'file_name', None),
                bank_name=getattr(hygiene_result, 'bank_name', None),
                user_id=getattr(hygiene_result, 'user_id', None),
                goal_id=getattr(hygiene_result, 'goal_id', None),
            ))


        # 2. Parser metrics — one session per metric
        for m in (parser_metrics_collected or []):
            _m = m
            _run(lambda svc: svc.create_parser_metric(
                job_id=job_id,
                parser_type=_m.get('parser_type', 'unknown'),
                parser_name=_m.get('parser_name', 'unknown'),
                bank_name=_m.get('bank_name'),
                execution_time_ms=_m.get('execution_time_ms', 0),
                transactions_extracted=_m.get('transactions_extracted', 0),
                confidence_score=_m.get('confidence_score'),
                status=_m.get('status', 'SUCCESS'),
                error_message=_m.get('error_message'),
            ))

        # 3. Raw transaction JSON
        if raw_transactions is not None:
            _run(lambda svc: svc.create_raw_transaction(job_id=job_id, raw_json=raw_transactions))

        # 4. Report generation log
        if excel_path:
            _run(lambda svc: svc.create_report_generation_log(
                job_id=job_id,
                excel_filename=_os.path.basename(excel_path),
                sheet_count=sheet_count,
                template_used=template_used,
            ))
            _run(lambda svc: svc.update_report_generation_log(
                job_id=job_id,
                generation_time_ms=generation_time_ms,
                file_size_bytes=_os.path.getsize(excel_path) if _os.path.exists(excel_path) else 0,
                status='COMPLETED',
            ))

        # 5. Statement metadata — CRITICAL: isolated session, no sharing
        txns_for_meta = classified_transactions if classified_transactions is not None else raw_transactions
        if txns_for_meta:
            try:
                from app.services.metadata_extractor import StatementMetadataExtractor
                from app.services.banks._shared.finbit_analytics import build_finbit_analytics
                header = dict(statement_header or {})
                header.setdefault("chitid", job_id)
                extractor = StatementMetadataExtractor()
                md_result = extractor.extract(
                    txns_for_meta,
                    header=header,
                    write_channel_back=True,
                )
                try:
                    profile_payload = build_finbit_analytics(
                        txns_for_meta,
                        selected_account_type=header.get("account_type"),
                    ).get("statement_profile", {})
                    if profile_payload:
                        md_result.extra.setdefault("statement_profile", profile_payload)
                        md_result.extra.setdefault("financial_profile", build_finbit_analytics(
                            txns_for_meta,
                            selected_account_type=header.get("account_type"),
                        ).get("financial_profile", {}))
                except Exception as _profile_err:
                    logger.warning("statement_profile enrichment skipped: %s", _profile_err)
                _md_dict = md_result.to_dict()
                _run(lambda svc: svc.save_statement_metadata(job_id, _md_dict))
                logger.info(f"Statement metadata saved for job {job_id}")
            except Exception as _me:
                logger.error("statement_metadata extraction failed (non-fatal): %s", _me, exc_info=True)

        # 6. Final job event
        _run(lambda svc: svc.create_job_event(
            job_id=job_id,
            event_type='EXPORT',
            event_name='EXPORT_FINISHED',
            event_category='REPORT',
            description='Excel generated and all audit data persisted',
            status='SUCCESS',
            metadata={'transaction_count': transaction_count, 'excel_path': excel_path},
        ))

        # 7. Mark job COMPLETED
        _run(lambda svc: svc.update_processing_job(
            job_id=job_id,
            status='COMPLETED',
            transaction_count=transaction_count,
        ))

        logger.info(f"finalize_job_audit completed successfully for job {job_id}")
