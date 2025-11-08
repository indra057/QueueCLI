"""
Worker process implementation for job execution.
"""

import os
import signal
import subprocess
import time
import sys
from datetime import datetime, timedelta
from typing import Optional

from .entities import Job, JobState, Config
from .database import Storage


class Worker:
    """Worker process that executes jobs from the queue."""
    
    def __init__(self, worker_id: str, db_path: str = "queuectl.db"):
        """Initialize worker."""
        self.worker_id = worker_id
        self.storage = Storage(db_path)
        self.config = self.storage.get_config()
        self.running = False
        self.current_job: Optional[Job] = None
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)
    
    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully."""
        print(f"[Worker {self.worker_id}] Received shutdown signal, finishing current job...")
        self.running = False
    
    def start(self):
        """Start the worker loop."""
        self.running = True
        print(f"[Worker {self.worker_id}] Started")

        # 🛠️ Auto-recover jobs stuck in 'processing' (crashed workers)
        try:
            with self.storage._get_cursor() as cursor:
                cursor.execute("""
                    UPDATE jobs
                    SET state='failed', locked_by=NULL, locked_at=NULL
                    WHERE state='processing'
                """)
            print(f"[Worker {self.worker_id}] Recovered any stuck jobs from previous runs")
        except Exception as e:
            print(f"[Worker {self.worker_id}] Error recovering stuck jobs: {e}")
        
        try:
            while self.running:
                # Reload config periodically
                self.config = self.storage.get_config()
                
                # Try to acquire a job
                job = self.storage.acquire_job(self.worker_id)
                
                if job:
                    self.current_job = job
                    self._execute_job(job)
                    self.current_job = None
                else:
                    # No jobs available, sleep
                    time.sleep(self.config.worker_poll_interval)
        
        except Exception as e:
            print(f"[Worker {self.worker_id}] Error: {e}")
        
        finally:
            # Release any locked job if interrupted
            if self.current_job:
                self.storage.release_job(self.current_job.id)
            self.storage.close()
            print(f"[Worker {self.worker_id}] Stopped")
    
    def _execute_job(self, job: Job):
        """Execute a job."""
        print(f"[Worker {self.worker_id}] Executing job {job.id}: {job.command}")
        
        job.attempts += 1
        start_time = time.time()
        
        try:
            # Determine timeout: per-job if set, otherwise global config
            timeout_secs = job.timeout if getattr(job, 'timeout', None) is not None else self.config.job_timeout

            # Execute the command
            result = subprocess.run(
                job.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_secs
            )
            
            execution_time = time.time() - start_time
            
            if result.returncode == 0:
                # Success
                job.state = JobState.COMPLETED
                job.error_message = None
                print(f"[Worker {self.worker_id}] Job {job.id} completed successfully "
                      f"in {execution_time:.2f}s")
                
                if result.stdout:
                    print(f"[Worker {self.worker_id}] Output: {result.stdout.strip()}")
            else:
                # Failed
                error_msg = result.stderr.strip() if result.stderr else f"Exit code: {result.returncode}"
                self._handle_job_failure(job, error_msg)
        
        except subprocess.TimeoutExpired:
            # Job exceeded its allowed time
            timeout_used = getattr(job, 'timeout', None) or self.config.job_timeout
            error_msg = f"Job timed out after {timeout_used} seconds"
            self._handle_job_failure(job, error_msg)
        
        except Exception as e:
            error_msg = str(e)
            self._handle_job_failure(job, error_msg)
        
        finally:
            # 🛠️ Defensive save and unlock
            try:
                self.storage.save_job(job)
                self.storage.release_job(job.id)
            except Exception as e:
                print(f"[Worker {self.worker_id}] Warning: failed to save or release job {job.id}: {e}")
    
    def _handle_job_failure(self, job: Job, error_message: str):
        """Handle job failure with retry logic."""
        job.error_message = error_message
        
        if job.attempts >= job.max_retries:
            # Move to DLQ
            job.state = JobState.DEAD
            job.next_retry_at = None
            print(f"[Worker {self.worker_id}] Job {job.id} failed permanently "
                  f"after {job.attempts} attempts, moving to DLQ")
            print(f"[Worker {self.worker_id}] Error: {error_message}")
        else:
            # Schedule retry with exponential backoff
            job.state = JobState.FAILED
            backoff_seconds = self.config.backoff_base ** job.attempts
            next_retry = datetime.utcnow() + timedelta(seconds=backoff_seconds)
            job.next_retry_at = next_retry.isoformat() + "Z"
            
            print(f"[Worker {self.worker_id}] Job {job.id} failed "
                  f"(attempt {job.attempts}/{job.max_retries}), "
                  f"retrying in {backoff_seconds}s")
            print(f"[Worker {self.worker_id}] Error: {error_message}")


def run_worker(worker_id: str, db_path: str = "queuectl.db"):
    """Entry point for worker process."""
    worker = Worker(worker_id, db_path)
    worker.start()
