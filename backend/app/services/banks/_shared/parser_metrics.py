"""
Airco Insights — Parser Metrics (Monitoring)
=============================================
Track parsing success rates and format changes.
Helps identify which banks need parser updates.

Stores metrics across all bank parsers for health monitoring.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import logging
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class ParseAttemptRecord:
    """Single parsing attempt record."""
    timestamp: str
    bank: str
    method: str  # "hardcoded", "dynamic", "unsupported"
    success: bool
    transaction_count: int
    file_hash: str = None  # Optional: hash of file for deduplication
    processing_time_ms: int = 0  # Optional: performance tracking


@dataclass
class FormatChangeRecord:
    """Record of when dynamic parser succeeded but hardcoded failed."""
    timestamp: str
    bank: str
    file_path: str
    transaction_count: int
    headers_detected: List[str] = None


class ParserMetrics:
    """
    Track parsing success rates and format changes across all banks.
    
    Helps identify:
    - Which banks are changing layouts (high dynamic fallback rate)
    - Parser health trends
    - Success rates by bank and method
    """
    
    DEFAULT_STORAGE_PATH = "/app/data/parser_metrics.json"
    MAX_ATTEMPTS_PER_BANK = 500  # Keep last N attempts per bank
    MAX_FORMAT_CHANGES = 100  # Keep last N format changes per bank
    
    def __init__(self, storage_path: str = None):
        """
        Initialize metrics storage.
        
        Args:
            storage_path: Path to JSON storage file
        """
        self.storage_path = Path(storage_path or self.DEFAULT_STORAGE_PATH)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.data: Dict[str, Any] = {
            "attempts": {},  # bank -> List[ParseAttemptRecord]
            "format_changes": {},  # bank -> List[FormatChangeRecord]
            "last_updated": None,
        }
        
        self._load()
        logger.info(f"ParserMetrics initialized at {self.storage_path}")
    
    def record_attempt(
        self,
        bank: str,
        method: str,
        success: bool,
        transaction_count: int,
        file_hash: str = None,
        processing_time_ms: int = 0,
    ):
        """
        Record a parsing attempt.
        
        Args:
            bank: Bank name
            method: "hardcoded", "dynamic", or "unsupported"
            success: Whether parsing succeeded
            transaction_count: Number of transactions extracted
            file_hash: Optional file hash for deduplication
            processing_time_ms: Optional processing time
        """
        try:
            if bank not in self.data["attempts"]:
                self.data["attempts"][bank] = []
            
            record = ParseAttemptRecord(
                timestamp=datetime.now().isoformat(),
                bank=bank,
                method=method,
                success=success,
                transaction_count=transaction_count,
                file_hash=file_hash,
                processing_time_ms=processing_time_ms,
            )
            
            self.data["attempts"][bank].append(asdict(record))
            
            # Keep only last N attempts
            if len(self.data["attempts"][bank]) > self.MAX_ATTEMPTS_PER_BANK:
                self.data["attempts"][bank] = self.data["attempts"][bank][-self.MAX_ATTEMPTS_PER_BANK:]
            
            self.data["last_updated"] = datetime.now().isoformat()
            self._save()
            
            logger.debug(
                f"Recorded attempt: {bank} | {method} | success={success} | "
                f"transactions={transaction_count}"
            )
            
        except Exception as e:
            logger.error(f"Failed to record attempt: {e}", exc_info=True)
    
    def record_format_change(
        self,
        bank: str,
        file_path: str,
        dynamic_success: bool,
        transaction_count: int,
        headers_detected: List[str] = None,
    ):
        """
        Record when dynamic parser succeeded but hardcoded failed.
        This indicates bank changed layout.
        
        Args:
            bank: Bank name
            file_path: Path to the file that triggered format change
            dynamic_success: Whether dynamic parser succeeded
            transaction_count: Number of transactions extracted
            headers_detected: Headers detected by dynamic parser
        """
        try:
            if bank not in self.data["format_changes"]:
                self.data["format_changes"][bank] = []
            
            record = FormatChangeRecord(
                timestamp=datetime.now().isoformat(),
                bank=bank,
                file_path=file_path,
                transaction_count=transaction_count,
                headers_detected=headers_detected or [],
            )
            
            self.data["format_changes"][bank].append(asdict(record))
            
            # Keep only last N format changes
            if len(self.data["format_changes"][bank]) > self.MAX_FORMAT_CHANGES:
                self.data["format_changes"][bank] = self.data["format_changes"][bank][-self.MAX_FORMAT_CHANGES:]
            
            self._save()
            
            logger.warning(
                f"Format change recorded for {bank}: "
                f"{transaction_count} transactions via dynamic parser. "
                f"Headers: {headers_detected}"
            )
            
        except Exception as e:
            logger.error(f"Failed to record format change: {e}", exc_info=True)
    
    def get_bank_stats(self, bank: str, days: int = 30) -> Dict[str, Any]:
        """
        Get statistics for a specific bank.
        
        Args:
            bank: Bank name
            days: Lookback period in days
            
        Returns:
            Dictionary with success rates, method breakdown, etc.
        """
        try:
            attempts = self.data["attempts"].get(bank, [])
            
            if not attempts:
                return {
                    "bank": bank,
                    "total_attempts": 0,
                    "success_rate": 0.0,
                    "dynamic_fallback_rate": 0.0,
                    "needs_attention": False,
                }
            
            # Filter by date range
            cutoff = datetime.now() - timedelta(days=days)
            recent_attempts = [
                a for a in attempts
                if datetime.fromisoformat(a["timestamp"]) > cutoff
            ]
            
            if not recent_attempts:
                recent_attempts = attempts[-10:] if attempts else []  # Fallback to last 10
            
            total = len(recent_attempts)
            successful = len([a for a in recent_attempts if a["success"]])
            hardcoded = len([a for a in recent_attempts if a["method"] == "hardcoded"])
            dynamic = len([a for a in recent_attempts if a["method"] == "dynamic"])
            unsupported = len([a for a in recent_attempts if a["method"] == "unsupported"])
            
            # Calculate rates
            success_rate = (successful / total * 100) if total > 0 else 0.0
            dynamic_fallback_rate = (dynamic / total * 100) if total > 0 else 0.0
            unsupported_rate = (unsupported / total * 100) if total > 0 else 0.0
            
            # Average transactions per successful parse
            successful_attempts = [a for a in recent_attempts if a["success"]]
            avg_transactions = (
                sum(a["transaction_count"] for a in successful_attempts) / len(successful_attempts)
                if successful_attempts else 0
            )
            
            return {
                "bank": bank,
                "period_days": days,
                "total_attempts": total,
                "successful_attempts": successful,
                "failed_attempts": total - successful,
                "success_rate": round(success_rate, 2),
                "dynamic_fallback_rate": round(dynamic_fallback_rate, 2),
                "unsupported_rate": round(unsupported_rate, 2),
                "avg_transactions_per_file": round(avg_transactions, 1),
                "needs_attention": dynamic_fallback_rate > 30 or success_rate < 90,
                "trend": self._calculate_trend(recent_attempts),
            }
            
        except Exception as e:
            logger.error(f"Failed to get stats for {bank}: {e}", exc_info=True)
            return {"bank": bank, "error": str(e)}
    
    def get_health_report(self, days: int = 7) -> Dict[str, Any]:
        """
        Get health report for all banks.
        
        Args:
            days: Lookback period in days
            
        Returns:
            Dictionary with health metrics for all banks
        """
        try:
            all_banks = set(self.data["attempts"].keys())
            
            report = {
                "generated_at": datetime.now().isoformat(),
                "period_days": days,
                "banks": {},
                "summary": {
                    "total_banks": len(all_banks),
                    "healthy_banks": 0,
                    "banks_needing_attention": 0,
                    "total_attempts": 0,
                    "overall_success_rate": 0.0,
                },
                "needs_attention": [],
            }
            
            total_attempts_all = 0
            total_success_all = 0
            
            for bank in all_banks:
                stats = self.get_bank_stats(bank, days)
                report["banks"][bank] = stats
                
                total_attempts_all += stats.get("total_attempts", 0)
                total_success_all += stats.get("successful_attempts", 0)
                
                if stats.get("needs_attention"):
                    report["summary"]["banks_needing_attention"] += 1
                    report["needs_attention"].append({
                        "bank": bank,
                        "reason": self._get_attention_reason(stats),
                        "success_rate": stats.get("success_rate"),
                        "dynamic_fallback_rate": stats.get("dynamic_fallback_rate"),
                    })
                else:
                    report["summary"]["healthy_banks"] += 1
            
            report["summary"]["total_attempts"] = total_attempts_all
            report["summary"]["overall_success_rate"] = round(
                (total_success_all / total_attempts_all * 100) if total_attempts_all > 0 else 0, 2
            )
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate health report: {e}", exc_info=True)
            return {"error": str(e)}
    
    def get_format_change_summary(self, bank: str = None, days: int = 30) -> Dict:
        """
        Get summary of format changes detected.
        
        Args:
            bank: Optional filter by bank
            days: Lookback period
            
        Returns:
            Dictionary with format change statistics
        """
        try:
            cutoff = datetime.now() - timedelta(days=days)
            
            if bank:
                changes = self.data["format_changes"].get(bank, [])
                changes = [
                    c for c in changes
                    if datetime.fromisoformat(c["timestamp"]) > cutoff
                ]
                return {
                    "bank": bank,
                    "period_days": days,
                    "format_changes_detected": len(changes),
                    "changes": changes[-10:],  # Last 10
                }
            else:
                # All banks
                all_changes = []
                for bnk, changes in self.data["format_changes"].items():
                    recent = [
                        c for c in changes
                        if datetime.fromisoformat(c["timestamp"]) > cutoff
                    ]
                    all_changes.extend(recent)
                
                return {
                    "period_days": days,
                    "total_format_changes": len(all_changes),
                    "by_bank": {
                        bnk: len([
                            c for c in chgs
                            if datetime.fromisoformat(c["timestamp"]) > cutoff
                        ])
                        for bnk, chgs in self.data["format_changes"].items()
                    },
                }
                
        except Exception as e:
            logger.error(f"Failed to get format change summary: {e}", exc_info=True)
            return {"error": str(e)}
    
    def export_metrics(self, output_path: str = None) -> str:
        """
        Export all metrics to file for analysis.
        
        Args:
            output_path: Export file path
            
        Returns:
            Path to exported file
        """
        try:
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = self.storage_path.parent / f"parser_metrics_export_{timestamp}.json"
            
            export_data = {
                "exported_at": datetime.now().isoformat(),
                "health_report": self.get_health_report(days=30),
                "raw_data": self.data,
            }
            
            with open(output_path, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            logger.info(f"Exported metrics to {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Failed to export metrics: {e}", exc_info=True)
            return None
    
    def reset_bank_metrics(self, bank: str) -> bool:
        """
        Reset metrics for a specific bank.
        Use when parser is updated.
        
        Args:
            bank: Bank name to reset
            
        Returns:
            True if reset successful
        """
        try:
            if bank in self.data["attempts"]:
                del self.data["attempts"][bank]
            if bank in self.data["format_changes"]:
                del self.data["format_changes"][bank]
            
            self._save()
            logger.info(f"Reset metrics for {bank}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reset metrics for {bank}: {e}")
            return False
    
    def _calculate_trend(self, attempts: List[Dict]) -> str:
        """Calculate trend (improving, stable, declining) from recent attempts."""
        if len(attempts) < 10:
            return "insufficient_data"
        
        # Split into first half and second half
        mid = len(attempts) // 2
        first_half = attempts[:mid]
        second_half = attempts[mid:]
        
        first_success_rate = sum(1 for a in first_half if a["success"]) / len(first_half)
        second_success_rate = sum(1 for a in second_half if a["success"]) / len(second_half)
        
        diff = second_success_rate - first_success_rate
        
        if diff > 0.1:
            return "improving"
        elif diff < -0.1:
            return "declining"
        else:
            return "stable"
    
    def _get_attention_reason(self, stats: Dict) -> str:
        """Get reason why bank needs attention."""
        reasons = []
        
        if stats.get("success_rate", 100) < 90:
            reasons.append(f"low_success_rate ({stats.get('success_rate')}%)")
        
        if stats.get("dynamic_fallback_rate", 0) > 30:
            reasons.append(f"high_dynamic_fallback ({stats.get('dynamic_fallback_rate')}%)")
        
        if stats.get("unsupported_rate", 0) > 10:
            reasons.append(f"high_unsupported_rate ({stats.get('unsupported_rate')}%)")
        
        return ", ".join(reasons) if reasons else "unknown"
    
    def _load(self):
        """Load data from storage."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    loaded = json.load(f)
                    self.data.update(loaded)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load metrics: {e}. Starting fresh.")
    
    def _save(self):
        """Save data to storage."""
        try:
            # Write to temp file first for atomicity
            temp_file = self.storage_path.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(self.data, f, indent=2, default=str)
            
            # Atomic rename
            temp_file.replace(self.storage_path)
            
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}", exc_info=True)
            raise
