"""
Data models for QueueCTL job queue system.
"""

from dataclasses import dataclass, asdict, fields
from datetime import datetime
from typing import Optional
import json


class JobState:
    """Job state constants."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD = "dead"


@dataclass
class Job:
    """Represents a job in the queue."""
    id: str
    command: str
    state: str = JobState.PENDING
    attempts: int = 0
    max_retries: int = 3
    # Per-job timeout in seconds. If None, fall back to global config.job_timeout
    timeout: Optional[int] = None
    # Job priority: 1=high, 2=medium, 3=low
    priority: int = 2
    created_at: str = None
    updated_at: str = None
    next_retry_at: Optional[str] = None
    error_message: Optional[str] = None
    
    # These fields were added to fix the 'unexpected keyword argument' error
    locked_by: Optional[str] = None
    locked_at: Optional[str] = None
    
    def __post_init__(self):
        """Initialize timestamps if not provided."""
        now = datetime.utcnow().isoformat() + "Z"
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now
    
    def to_dict(self) -> dict:
        """
        Returns a dictionary representation of the job.
        """
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert job to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Job':
        """Create job from dictionary."""
        
        # --- THIS IS THE FIX ---
        # We just need the set of field names, which are the keys of the dict
        known_keys = set(cls.__dataclass_fields__.keys())
        # --- END OF FIX ---

        filtered_data = {k: v for k, v in data.items() if k in known_keys}
        return cls(**filtered_data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Job':
        """Create job from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class Config:
    """System configuration."""
    max_retries: int = 3
    backoff_base: int = 2
    worker_poll_interval: float = 1.0
    job_timeout: int = 300  # 5 minutes
    
    def to_dict(self) -> dict:
        """
        Convert config to dictionary.
        """
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Config':
        """Create config from dictionary."""
        # This one also needs to be safe
        known_keys = set(cls.__dataclass_fields__.keys())
        filtered_data = {k: v for k, v in data.items() if k in known_keys}
        return cls(**filtered_data)