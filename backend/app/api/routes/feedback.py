"""
Feedback API Routes
Handles user corrections, learning triggers, and status monitoring.

NOTE: Learning features are temporarily disabled pending architecture cleanup.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging

from ...dependencies.auth import get_current_user, require_user_role
from ...utils.logging import get_logger

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["feedback"])

# Request/Response Models
class TransactionCorrectionRequest(BaseModel):
    transaction_id: str
    corrected_category: str
    user_id: Optional[str] = None
    method: str = "ui"  # ui, whatsapp, api

class CategorySuggestionRequest(BaseModel):
    description: str
    amount: float
    is_debit: bool
    suggested_category: str
    reasoning: Optional[str] = None

class LearningTriggerRequest(BaseModel):
    force: bool = False
    bank_name: Optional[str] = None

# API Endpoints

@router.post("/transaction")
async def submit_transaction_correction(
    request: TransactionCorrectionRequest,
    background_tasks: BackgroundTasks
):
    """
    Submit a user correction for a transaction.
    
    NOTE: Learning features are temporarily disabled.
    """
    try:
        # Placeholder implementation
        logger.info(f"Transaction correction received: {request.transaction_id} -> {request.corrected_category}")
        
        return {
            "success": True,
            "message": "Correction saved. Learning features temporarily disabled.",
            "learning_stats": {
                "total_corrections": 0,
                "unclassified": 0,
                "ready_for_learning": False
            }
        }
        
    except Exception as e:
        logger.error(f"Error submitting correction: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/category-suggestion")
async def submit_category_suggestion(request: CategorySuggestionRequest):
    """
    Submit a category suggestion for a new pattern.
    """
    try:
        logger.info(f"Category suggestion received: {request.description[:50]} -> {request.suggested_category}")
        
        return {
            "success": True,
            "message": "Thank you for your suggestion! We'll review it for inclusion."
        }
        
    except Exception as e:
        logger.error(f"Error submitting suggestion: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/learning/summary")
async def get_learning_summary():
    """
    Get comprehensive learning system summary.
    
    NOTE: Learning features are temporarily disabled.
    """
    try:
        return {
            "data_collection": {
                "total_corrections": 0,
                "unclassified": 0,
                "ready_for_learning": False
            },
            "dynamic_rules": {
                "total_rules": 0,
                "active_rules": 0,
                "pending_rules": 0
            },
            "system_status": {
                "learning_enabled": False,
                "auto_deploy_enabled": False,
                "monitoring_active": False,
                "message": "Learning features temporarily disabled during architecture cleanup"
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting learning summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/learning/trigger")
async def trigger_learning(
    request: LearningTriggerRequest,
    background_tasks: BackgroundTasks
):
    """
    Manually trigger the learning process.
    
    NOTE: Learning features are temporarily disabled.
    """
    try:
        return {
            "success": False,
            "message": "Learning features temporarily disabled during architecture cleanup",
            "stats": {
                "total_corrections": 0,
                "unclassified": 0,
                "ready_for_learning": False
            }
        }
        
    except Exception as e:
        logger.error(f"Error triggering learning: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/learning/patterns")
async def get_discovered_patterns():
    """
    Get recently discovered patterns from learning.
    
    NOTE: Learning features are temporarily disabled.
    """
    try:
        return {
            "patterns": [],
            "message": "Pattern discovery temporarily disabled during architecture cleanup"
        }
        
    except Exception as e:
        logger.error(f"Error getting patterns: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/rules/dynamic")
async def get_dynamic_rules():
    """
    Get all dynamic rules and their status.
    
    NOTE: Learning features are temporarily disabled.
    """
    try:
        return {
            "rules": [],
            "stats": {
                "total_rules": 0,
                "active_rules": 0,
                "pending_rules": 0
            },
            "message": "Dynamic rules temporarily disabled during architecture cleanup"
        }
        
    except Exception as e:
        logger.error(f"Error getting dynamic rules: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/rules/activate/{rule_id}")
async def activate_rule(rule_id: str):
    """
    Activate a dynamic rule.
    
    NOTE: Learning features are temporarily disabled.
    """
    try:
        raise HTTPException(
            status_code=503, 
            detail="Dynamic rules temporarily disabled during architecture cleanup"
        )
        
    except Exception as e:
        logger.error(f"Error activating rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/rules/deactivate/{rule_id}")
async def deactivate_rule(rule_id: str):
    """
    Deactivate a dynamic rule.
    
    NOTE: Learning features are temporarily disabled.
    """
    try:
        raise HTTPException(
            status_code=503, 
            detail="Dynamic rules temporarily disabled during architecture cleanup"
        )
        
    except Exception as e:
        logger.error(f"Error deactivating rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))
