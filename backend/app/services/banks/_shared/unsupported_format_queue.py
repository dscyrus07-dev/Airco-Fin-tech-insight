"""
Airco Insights — Unsupported Format Queue (Level 3)
====================================================
Queue for PDFs that failed all parsing attempts.
Used for manual review and parser updates.

Tracks failed statements that need manual intervention.
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class UnsupportedFormatQueue:
    """
    Queue for PDFs that failed all parsing attempts across all banks.
    
    Stores metadata about failed files for manual review and helps
    identify which bank formats need parser updates.
    """
    
    DEFAULT_STORAGE_PATH = "/app/data/unsupported_formats"
    QUEUE_FILE = "queue.json"
    MAX_QUEUE_SIZE = 1000  # Prevent unbounded growth
    
    def __init__(self, storage_path: str = None):
        """
        Initialize the queue.
        
        Args:
            storage_path: Directory to store queue file. Defaults to /app/data/unsupported_formats
        """
        self.storage_path = Path(storage_path or self.DEFAULT_STORAGE_PATH)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.queue_file = self.storage_path / self.QUEUE_FILE
        
        logger.info(f"UnsupportedFormatQueue initialized at {self.storage_path}")
    
    def add(self, entry: Dict) -> str:
        """
        Add a failed PDF to the queue.
        
        Args:
            entry: Dictionary containing:
                - bank: Bank name
                - file: File path or identifier
                - timestamp: ISO format timestamp
                - attempts: List of parsing attempts
                - [optional] error_details: Additional error information
                
        Returns:
            entry_id: Unique ID assigned to this entry
        """
        try:
            queue = self._load_queue()
            
            # Generate unique ID
            entry_id = (
                f"{entry.get('bank', 'UNKNOWN')}_"
                f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_"
                f"{len(queue):04d}"
            )
            
            entry["id"] = entry_id
            entry["status"] = "pending_review"
            entry["added_at"] = datetime.now().isoformat()
            
            # Add to queue
            queue.append(entry)
            
            # Trim if exceeds max size (remove oldest)
            if len(queue) > self.MAX_QUEUE_SIZE:
                queue = queue[-self.MAX_QUEUE_SIZE:]
                logger.warning(f"Queue trimmed to {self.MAX_QUEUE_SIZE} entries")
            
            self._save_queue(queue)
            
            logger.warning(
                f"Added to unsupported format queue: {entry_id} "
                f"(Bank: {entry.get('bank')}, Queue size: {len(queue)})"
            )
            
            return entry_id
            
        except Exception as e:
            logger.error(f"Failed to add entry to queue: {e}", exc_info=True)
            return None
    
    def get_pending(self, bank: str = None, limit: int = 100) -> List[Dict]:
        """
        Get all pending items awaiting review.
        
        Args:
            bank: Optional filter by bank name
            limit: Maximum number of items to return
            
        Returns:
            List of pending queue entries
        """
        try:
            queue = self._load_queue()
            pending = [q for q in queue if q.get("status") == "pending_review"]
            
            if bank:
                pending = [q for q in pending if q.get("bank") == bank]
            
            # Sort by timestamp (oldest first)
            pending.sort(key=lambda x: x.get("added_at", ""))
            
            return pending[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get pending items: {e}", exc_info=True)
            return []
    
    def get_by_id(self, entry_id: str) -> Optional[Dict]:
        """Get a specific queue entry by ID."""
        try:
            queue = self._load_queue()
            for entry in queue:
                if entry.get("id") == entry_id:
                    return entry
            return None
        except Exception as e:
            logger.error(f"Failed to get entry {entry_id}: {e}")
            return None
    
    def mark_resolved(self, entry_id: str, resolution: str, resolution_notes: str = None) -> bool:
        """
        Mark an entry as resolved.
        
        Args:
            entry_id: ID of the entry to resolve
            resolution: Resolution type (e.g., "parser_updated", "user_error", "scanned_pdf")
            resolution_notes: Optional additional notes
            
        Returns:
            True if successfully marked resolved, False otherwise
        """
        try:
            queue = self._load_queue()
            
            for q in queue:
                if q.get("id") == entry_id:
                    q["status"] = "resolved"
                    q["resolution"] = resolution
                    q["resolution_notes"] = resolution_notes
                    q["resolved_at"] = datetime.now().isoformat()
                    q["resolved_by"] = "manual"  # Could be extended to track user
                    
                    self._save_queue(queue)
                    
                    logger.info(f"Marked entry {entry_id} as resolved: {resolution}")
                    return True
            
            logger.warning(f"Entry {entry_id} not found in queue")
            return False
            
        except Exception as e:
            logger.error(f"Failed to mark entry {entry_id} resolved: {e}", exc_info=True)
            return False
    
    def mark_in_progress(self, entry_id: str) -> bool:
        """Mark an entry as being reviewed/in progress."""
        try:
            queue = self._load_queue()
            
            for q in queue:
                if q.get("id") == entry_id:
                    q["status"] = "in_progress"
                    q["review_started_at"] = datetime.now().isoformat()
                    self._save_queue(queue)
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Failed to mark entry {entry_id} in progress: {e}")
            return False
    
    def get_stats(self) -> Dict:
        """
        Get queue statistics.
        
        Returns:
            Dictionary with counts by status and bank
        """
        try:
            queue = self._load_queue()
            
            stats = {
                "total": len(queue),
                "pending": len([q for q in queue if q.get("status") == "pending_review"]),
                "in_progress": len([q for q in queue if q.get("status") == "in_progress"]),
                "resolved": len([q for q in queue if q.get("status") == "resolved"]),
                "by_bank": {},
                "by_resolution": {},
            }
            
            # Count by bank
            for q in queue:
                bank = q.get("bank", "UNKNOWN")
                stats["by_bank"][bank] = stats["by_bank"].get(bank, 0) + 1
                
                if q.get("status") == "resolved":
                    resolution = q.get("resolution", "unknown")
                    stats["by_resolution"][resolution] = stats["by_resolution"].get(resolution, 0) + 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get stats: {e}", exc_info=True)
            return {"total": 0, "error": str(e)}
    
    def get_bank_needs_attention(self, threshold: int = 5) -> List[str]:
        """
        Get list of banks with high failure counts that need parser updates.
        
        Args:
            threshold: Minimum pending failures to flag a bank
            
        Returns:
            List of bank names needing attention
        """
        stats = self.get_stats()
        needs_attention = []
        
        for bank, count in stats.get("by_bank", {}).items():
            if count >= threshold:
                needs_attention.append(bank)
        
        return needs_attention
    
    def clear_resolved(self, older_than_days: int = 30) -> int:
        """
        Clear resolved entries older than specified days.
        
        Args:
            older_than_days: Remove entries resolved more than this many days ago
            
        Returns:
            Number of entries removed
        """
        try:
            from datetime import timedelta
            
            queue = self._load_queue()
            cutoff = datetime.now() - timedelta(days=older_than_days)
            
            original_count = len(queue)
            queue = [
                q for q in queue
                if not (
                    q.get("status") == "resolved" and
                    q.get("resolved_at") and
                    datetime.fromisoformat(q["resolved_at"]) < cutoff
                )
            ]
            
            removed = original_count - len(queue)
            self._save_queue(queue)
            
            logger.info(f"Cleared {removed} resolved entries older than {older_than_days} days")
            return removed
            
        except Exception as e:
            logger.error(f"Failed to clear resolved entries: {e}", exc_info=True)
            return 0
    
    def export_for_analysis(self, output_path: str = None) -> str:
        """
        Export queue data for analysis.
        
        Args:
            output_path: Path for export file. Defaults to queue directory.
            
        Returns:
            Path to exported file
        """
        try:
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = self.storage_path / f"unsupported_formats_export_{timestamp}.json"
            
            queue = self._load_queue()
            export_data = {
                "exported_at": datetime.now().isoformat(),
                "stats": self.get_stats(),
                "entries": queue,
            }
            
            with open(output_path, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            logger.info(f"Exported queue data to {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Failed to export queue: {e}", exc_info=True)
            return None
    
    def _load_queue(self) -> List[Dict]:
        """Load queue from storage."""
        if self.queue_file.exists():
            try:
                with open(self.queue_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Corrupted queue file: {e}. Starting fresh.")
                return []
        return []
    
    def _save_queue(self, queue: List[Dict]):
        """Save queue to storage."""
        try:
            # Write to temp file first for atomicity
            temp_file = self.queue_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(queue, f, indent=2, default=str)
            
            # Atomic rename
            temp_file.replace(self.queue_file)
            
        except Exception as e:
            logger.error(f"Failed to save queue: {e}", exc_info=True)
            raise
