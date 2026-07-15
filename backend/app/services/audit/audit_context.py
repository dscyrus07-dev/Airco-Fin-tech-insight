"""
Audit Context - User Context Propagation Helper
Ensures user context flows through entire pipeline for multi-tenant audit logging
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid


@dataclass
class AuditContext:
    """
    User context for audit logging
    Propagates through entire pipeline to ensure all events have proper context
    """
    # Tenant context
    tenant_id: str
    tenant_slug: str
    
    # User context
    user_id: str
    user_email: str
    user_name: Optional[str] = None
    user_role: str = 'USER'
    
    # Session context
    session_id: Optional[str] = None
    session_token: Optional[str] = None
    
    # Request context
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    browser: Optional[str] = None
    os: Optional[str] = None
    device_type: Optional[str] = None
    
    # Geographic context
    country_code: Optional[str] = None
    city: Optional[str] = None
    
    # Job context (for processing jobs)
    job_id: Optional[str] = None
    batch_id: Optional[str] = None
    correlation_id: Optional[str] = None
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Timestamp
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for serialization"""
        return {
            'tenant_id': self.tenant_id,
            'tenant_slug': self.tenant_slug,
            'user_id': self.user_id,
            'user_email': self.user_email,
            'user_name': self.user_name,
            'user_role': self.user_role,
            'session_id': self.session_id,
            'session_token': self.session_token,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'browser': self.browser,
            'os': self.os,
            'device_type': self.device_type,
            'country_code': self.country_code,
            'city': self.city,
            'job_id': self.job_id,
            'batch_id': self.batch_id,
            'correlation_id': self.correlation_id,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat()
        }
    
    def to_rabbitmq_message(self) -> Dict[str, Any]:
        """Convert context to RabbitMQ message format"""
        return {
            'audit_context': self.to_dict(),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    def with_job(self, job_id: str) -> 'AuditContext':
        """Create new context with job_id"""
        return AuditContext(
            tenant_id=self.tenant_id,
            tenant_slug=self.tenant_slug,
            user_id=self.user_id,
            user_email=self.user_email,
            user_name=self.user_name,
            user_role=self.user_role,
            session_id=self.session_id,
            session_token=self.session_token,
            ip_address=self.ip_address,
            user_agent=self.user_agent,
            browser=self.browser,
            os=self.os,
            device_type=self.device_type,
            country_code=self.country_code,
            city=self.city,
            job_id=job_id,
            batch_id=self.batch_id,
            correlation_id=self.correlation_id,
            metadata=self.metadata.copy()
        )
    
    def with_batch(self, batch_id: str) -> 'AuditContext':
        """Create new context with batch_id"""
        return AuditContext(
            tenant_id=self.tenant_id,
            tenant_slug=self.tenant_slug,
            user_id=self.user_id,
            user_email=self.user_email,
            user_name=self.user_name,
            user_role=self.user_role,
            session_id=self.session_id,
            session_token=self.session_token,
            ip_address=self.ip_address,
            user_agent=self.user_agent,
            browser=self.browser,
            os=self.os,
            device_type=self.device_type,
            country_code=self.country_code,
            city=self.city,
            job_id=self.job_id,
            batch_id=batch_id,
            correlation_id=self.correlation_id,
            metadata=self.metadata.copy()
        )
    
    def with_correlation(self, correlation_id: str) -> 'AuditContext':
        """Create new context with correlation_id"""
        return AuditContext(
            tenant_id=self.tenant_id,
            tenant_slug=self.tenant_slug,
            user_id=self.user_id,
            user_email=self.user_email,
            user_name=self.user_name,
            user_role=self.user_role,
            session_id=self.session_id,
            session_token=self.session_token,
            ip_address=self.ip_address,
            user_agent=self.user_agent,
            browser=self.browser,
            os=self.os,
            device_type=self.device_type,
            country_code=self.country_code,
            city=self.city,
            job_id=self.job_id,
            batch_id=self.batch_id,
            correlation_id=correlation_id,
            metadata=self.metadata.copy()
        )


class AuditContextManager:
    """
    Manages audit context lifecycle
    Extracts context from requests and ensures proper propagation
    """
    
    @staticmethod
    def from_fastapi_request(request) -> AuditContext:
        """Extract audit context from FastAPI request"""
        # Extract from request state (set by middleware)
        if hasattr(request.state, 'audit_context'):
            return request.state.audit_context
        
        # Fallback: extract from request directly
        headers = dict(request.headers)
        
        return AuditContext(
            tenant_id=headers.get('X-Tenant-ID', 'default'),
            tenant_slug=headers.get('X-Tenant-Slug', 'default'),
            user_id=headers.get('X-User-ID', 'anonymous'),
            user_email=headers.get('X-User-Email', 'anonymous@example.com'),
            user_name=headers.get('X-User-Name'),
            user_role=headers.get('X-User-Role', 'USER'),
            session_id=headers.get('X-Session-ID'),
            session_token=headers.get('Authorization', '').replace('Bearer ', ''),
            ip_address=request.client.host if request.client else None,
            user_agent=headers.get('User-Agent'),
            browser=headers.get('X-Browser'),
            os=headers.get('X-OS'),
            device_type=headers.get('X-Device-Type'),
            country_code=headers.get('X-Country-Code'),
            city=headers.get('X-City')
        )
    
    @staticmethod
    def from_rabbitmq_message(message: Dict[str, Any]) -> Optional[AuditContext]:
        """Extract audit context from RabbitMQ message"""
        if 'audit_context' not in message:
            return None
        
        context_data = message['audit_context']
        
        return AuditContext(
            tenant_id=context_data.get('tenant_id', 'default'),
            tenant_slug=context_data.get('tenant_slug', 'default'),
            user_id=context_data.get('user_id', 'anonymous'),
            user_email=context_data.get('user_email', 'anonymous@example.com'),
            user_name=context_data.get('user_name'),
            user_role=context_data.get('user_role', 'USER'),
            session_id=context_data.get('session_id'),
            session_token=context_data.get('session_token'),
            ip_address=context_data.get('ip_address'),
            user_agent=context_data.get('user_agent'),
            browser=context_data.get('browser'),
            os=context_data.get('os'),
            device_type=context_data.get('device_type'),
            country_code=context_data.get('country_code'),
            city=context_data.get('city'),
            job_id=context_data.get('job_id'),
            batch_id=context_data.get('batch_id'),
            correlation_id=context_data.get('correlation_id'),
            metadata=context_data.get('metadata', {})
        )
    
    @staticmethod
    def create_system_context(tenant_id: str = 'system') -> AuditContext:
        """Create system-level audit context for background jobs"""
        return AuditContext(
            tenant_id=tenant_id,
            tenant_slug='system',
            user_id='system',
            user_email='system@airco-insights.com',
            user_name='System',
            user_role='SYSTEM',
            ip_address='127.0.0.1',
            user_agent='Airco-Insights-System/1.0'
        )
    
    @staticmethod
    def enrich_message(message: Dict[str, Any], context: AuditContext) -> Dict[str, Any]:
        """Enrich a message with audit context"""
        enriched = message.copy()
        enriched['audit_context'] = context.to_dict()
        enriched['timestamp'] = datetime.now(timezone.utc).isoformat()
        return enriched


# FastAPI dependency for injecting audit context
def get_audit_context(request) -> AuditContext:
    """FastAPI dependency to get audit context from request"""
    return AuditContextManager.from_fastapi_request(request)
