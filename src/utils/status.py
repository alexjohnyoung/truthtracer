"""
Status utility module for handling analysis status updates.
This module provides a centralised way to update analysis status
"""

from datetime import datetime
from typing import Dict, Any, Optional

# Global state
analysis_store: Dict[str, Dict[str, Any]] = {}
current_analysis_id = None

def update_status(message: str, progress: int, step_name: str = "", step: int = 0) -> None:
    """
    Update the status of the current analysis
    
    This function is designed to be imported by other modules to provide status updates.
    
    Args:
        message (str): Status message to display
        progress (int): Progress value (0-100)
        step_name (str): Name of the current step
        step (int): Current step number
    """
    global current_analysis_id
    
    if current_analysis_id and current_analysis_id in analysis_store:
        # Ensure progress is within bounds
        bounded_progress = max(0, min(100, progress))
        
        # Update the status information
        analysis_store[current_analysis_id]["status"] = {
            "message": message,
            "progress": bounded_progress,
            "step_name": step_name,
            "step": step
        }
        
        # Add to log messages with a timestamp prefix
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        analysis_store[current_analysis_id]["log_messages"].append(log_entry)

def set_current_analysis_id(analysis_id: Optional[str]):
    """Set the current analysis ID being processed"""
    global current_analysis_id
    current_analysis_id = analysis_id

def get_current_analysis_id() -> str:
    """Get the current analysis ID being processed"""
    return current_analysis_id 