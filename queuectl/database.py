"""
Persistent storage layer using SQLite for job queue system.
"""

import sqlite3
import json
import threading
from typing import List, Optional, Dict
from contextlib import contextmanager
from datetime import datetime

from .entities import Job, JobState, Config


class Storage:
    """Thread-safe SQLite storage for jobs and configuration."""
    
    def __init__(self, db_path: str = "queuectl.db"):
        """Initialize storage with database path."""
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                isolation_level=None  # Autocommit mode
            )
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection
    
    @contextmanager
    def _get_cursor(self):
        """Context manager for database cursor."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
        finally:
            cursor.close()
    
    def _init_db(self):
        """Initialize database schema."""
        with self._get_cursor() as cursor:
            # Jobs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    command TEXT NOT NULL,
                    state TEXT NOT NULL,
                    attempts INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    timeout INTEGER DEFAULT NULL,
                    priority INTEGER DEFAULT 2,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    next_retry_at TEXT,
                    error_message TEXT,
                    locked_by TEXT,
                    locked_at TEXT
                )
            """)
            
            # Configuration table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            
            # Create indexes for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_state 
                ON jobs(state)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_next_retry 
                ON jobs(next_retry_at) 
                WHERE next_retry_at IS NOT NULL
            """)

            # Migrate existing databases: add timeout and priority columns if missing
            cursor.execute("PRAGMA table_info(jobs)")
            cols = {r[1] for r in cursor.fetchall()}  # name is at index 1
            if 'timeout' not in cols:
                try:
                    cursor.execute("ALTER TABLE jobs ADD COLUMN timeout INTEGER DEFAULT NULL")
                except Exception:
                    # Best-effort migration
                    pass
            if 'priority' not in cols:
                try:
                    cursor.execute("ALTER TABLE jobs ADD COLUMN priority INTEGER DEFAULT 2")
                except Exception:
                    pass
    
    def save_job(self, job: Job) -> bool:
        """Save or update a job."""
        try:
            job.updated_at = datetime.utcnow().isoformat() + "Z"
            
            with self._get_cursor() as cursor:
                cursor.execute("""
                    INSERT OR REPLACE INTO jobs 
                    (id, command, state, attempts, max_retries, timeout, priority,
                     created_at, updated_at, next_retry_at, error_message,
                     locked_by, locked_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
                """, (
                    job.id, job.command, job.state, job.attempts,
                    job.max_retries, job.timeout, job.priority,
                    job.created_at, job.updated_at,
                    job.next_retry_at, job.error_message
                ))
            return True
        except Exception as e:
            print(f"Error saving job: {e}")
            return False
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Retrieve a job by ID."""
        with self._get_cursor() as cursor:
            cursor.execute("""
                SELECT id, command, state, attempts, max_retries, timeout, priority,
                       created_at, updated_at, next_retry_at, error_message
                FROM jobs WHERE id = ?
            """, (job_id,))
            
            row = cursor.fetchone()
            if row:
                return Job(**dict(row))
            return None
    
    def get_jobs_by_state(self, state: str) -> List[Job]:
        """Get all jobs in a specific state."""
        with self._get_cursor() as cursor:
            cursor.execute("""
                SELECT id, command, state, attempts, max_retries, timeout, priority,
                       created_at, updated_at, next_retry_at, error_message
                FROM jobs WHERE state = ?
                ORDER BY priority ASC, created_at ASC
            """, (state,))
            
            return [Job(**dict(row)) for row in cursor.fetchall()]
    
    def get_all_jobs(self) -> List[Job]:
        """Get all jobs."""
        with self._get_cursor() as cursor:
            cursor.execute("""
                SELECT id, command, state, attempts, max_retries, timeout, priority,
                       created_at, updated_at, next_retry_at, error_message
                FROM jobs
                ORDER BY priority ASC, created_at DESC
            """)
            
            return [Job(**dict(row)) for row in cursor.fetchall()]
    
    def acquire_job(self, worker_id: str) -> Optional[Job]:
        """
        Atomically acquire a pending job for processing.
        Returns the job if successfully acquired, None otherwise.
        """
        now = datetime.utcnow().isoformat() + "Z"
        
        with self._get_cursor() as cursor:
            # Start transaction
            cursor.execute("BEGIN EXCLUSIVE")

            try:
                # Find a pending job or a failed job ready for retry.
                # Prefer lower priority value (1 = high) then older created_at.
                cursor.execute("""
                    SELECT id, command, state, attempts, max_retries, timeout, priority,
                           created_at, updated_at, next_retry_at, error_message
                    FROM jobs
                    WHERE (state = ? OR (state = ? AND (next_retry_at IS NULL OR next_retry_at <= ?)))
                      AND (locked_by IS NULL OR locked_at < datetime('now', '-5 minutes'))
                    ORDER BY priority ASC, created_at ASC
                    LIMIT 1
                """, (JobState.PENDING, JobState.FAILED, now))

                row = cursor.fetchone()

                if row:
                    job = Job(**dict(row))

                    # Lock the job
                    cursor.execute("""
                        UPDATE jobs 
                        SET locked_by = ?, locked_at = ?, state = ?
                        WHERE id = ?
                    """, (worker_id, now, JobState.PROCESSING, job.id))

                    cursor.execute("COMMIT")

                    job.state = JobState.PROCESSING
                    return job
                else:
                    cursor.execute("COMMIT")
                    return None

            except Exception as e:
                cursor.execute("ROLLBACK")
                print(f"Error acquiring job: {e}")
                return None
    
    def release_job(self, job_id: str):
        """Release job lock."""
        with self._get_cursor() as cursor:
            cursor.execute("""
                UPDATE jobs 
                SET locked_by = NULL, locked_at = NULL
                WHERE id = ?
            """, (job_id,))
    
    def get_job_counts(self) -> Dict[str, int]:
        """Get count of jobs by state."""
        with self._get_cursor() as cursor:
            cursor.execute("""
                SELECT state, COUNT(*) as count
                FROM jobs
                GROUP BY state
            """)
            
            counts = {row['state']: row['count'] for row in cursor.fetchall()}
            
            # Ensure all states are present
            for state in [JobState.PENDING, JobState.PROCESSING, 
                         JobState.COMPLETED, JobState.FAILED, JobState.DEAD]:
                if state not in counts:
                    counts[state] = 0
            
            return counts
    
    def delete_job(self, job_id: str) -> bool:
        """Delete a job."""
        try:
            with self._get_cursor() as cursor:
                cursor.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            return True
        except Exception as e:
            print(f"Error deleting job: {e}")
            return False
    
    def save_config(self, config: Config):
        """Save configuration."""
        with self._get_cursor() as cursor:
            for key, value in config.to_dict().items():
                cursor.execute("""
                    INSERT OR REPLACE INTO config (key, value)
                    VALUES (?, ?)
                """, (key, json.dumps(value)))
    
    def get_config(self) -> Config:
        """Load configuration."""
        with self._get_cursor() as cursor:
            cursor.execute("SELECT key, value FROM config")
            rows = cursor.fetchall()
            
            if not rows:
                # Return default config
                config = Config()
                self.save_config(config)
                return config
            
            config_dict = {row['key']: json.loads(row['value']) for row in rows}
            return Config.from_dict(config_dict)
    
    def close(self):
        """Close database connection."""
        if hasattr(self._local, 'connection'):
            self._local.connection.close()

            # Inside your Storage class in database.py

    def get_dashboard_data(self) -> dict:
        """Fetches all jobs for the dashboard."""
        jobs_by_state = {
            'pending': [],
            'processing': [],
            'completed': [],
            'failed': [],
            'dead': []
        }
        
        try:
            with self._get_cursor() as cursor:
                cursor.execute("SELECT * FROM jobs ORDER BY updated_at DESC")
                for row in cursor.fetchall():
                    job = Job(**dict(row))
                    if job.state in jobs_by_state:
                        jobs_by_state[job.state].append(job.to_dict())
            return jobs_by_state
        except Exception as e:
            print(f"Error fetching dashboard data: {e}")
            return jobs_by_state