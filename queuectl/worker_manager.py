"""
Worker manager for controlling worker processes.
"""

import os
import signal
import subprocess
import time
import psutil
from pathlib import Path
from typing import List, Dict


class WorkerManager:
    """Manages worker processes."""
    
    def __init__(self, db_path: str = "queuectl.db"):
        """Initialize worker manager."""
        self.db_path = db_path
        self.pid_file = Path(".queuectl_workers.pid")
    
    def start_workers(self, count: int = 1) -> List[int]:
        """Start worker processes."""
        pids = []
        
        # Check if workers are already running
        existing_pids = self._get_running_workers()
        if existing_pids:
            print(f"Workers already running with PIDs: {existing_pids}")
            print("Stop existing workers before starting new ones.")
            return []
        
        for i in range(count):
            worker_id = f"worker-{i+1}"
            pid = self._start_worker(worker_id)
            if pid:
                pids.append(pid)
                print(f"Started {worker_id} with PID {pid}")
        
        # Save PIDs to file
        if pids:
            self._save_pids(pids)
            print(f"\nStarted {len(pids)} worker(s)")
        
        return pids
    
    def _start_worker(self, worker_id: str) -> int:
        """Start a single worker process."""
        try:
            # Start worker as subprocess
            process = subprocess.Popen(
                [
                    "python3", "-c",
                    f"from queuectl.worker_logic import run_worker; "
                    f"run_worker('{worker_id}', '{self.db_path}')"
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True  # Detach from parent
            )
            
            # Give it a moment to start
            time.sleep(0.5)
            
            # Check if process is still running
            if process.poll() is None:
                return process.pid
            else:
                print(f"Failed to start {worker_id}")
                return None
                
        except Exception as e:
            print(f"Error starting worker {worker_id}: {e}")
            return None
    
    def stop_workers(self, graceful: bool = True) -> int:
        """Stop all worker processes."""
        pids = self._get_running_workers()
        
        if not pids:
            print("No workers running")
            return 0
        
        stopped_count = 0
        
        for pid in pids:
            try:
                if self._is_process_running(pid):
                    if graceful:
                        # Send SIGTERM for graceful shutdown
                        os.kill(pid, signal.SIGTERM)
                        print(f"Sent shutdown signal to worker with PID {pid}")
                        
                        # Wait up to 10 seconds for graceful shutdown
                        for _ in range(10):
                            if not self._is_process_running(pid):
                                break
                            time.sleep(1)
                        
                        # Force kill if still running
                        if self._is_process_running(pid):
                            os.kill(pid, signal.SIGKILL)
                            print(f"Force killed worker with PID {pid}")
                    else:
                        # Immediate kill
                        os.kill(pid, signal.SIGKILL)
                        print(f"Killed worker with PID {pid}")
                    
                    stopped_count += 1
            except ProcessLookupError:
                # Process already dead
                pass
            except Exception as e:
                print(f"Error stopping worker {pid}: {e}")
        
        # Clear PID file
        if self.pid_file.exists():
            self.pid_file.unlink()
        
        print(f"\nStopped {stopped_count} worker(s)")
        return stopped_count
    
    def get_worker_status(self) -> List[Dict]:
        """Get status of running workers."""
        pids = self._get_running_workers()
        workers = []
        
        for pid in pids:
            try:
                if self._is_process_running(pid):
                    process = psutil.Process(pid)
                    workers.append({
                        'pid': pid,
                        'status': process.status(),
                        'cpu_percent': process.cpu_percent(interval=0.1),
                        'memory_mb': process.memory_info().rss / 1024 / 1024,
                        'created': time.strftime('%Y-%m-%d %H:%M:%S', 
                                                time.localtime(process.create_time()))
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        return workers
    
    def _save_pids(self, pids: List[int]):
        """Save PIDs to file."""
        with open(self.pid_file, 'w') as f:
            f.write('\n'.join(map(str, pids)))
    
    def _get_running_workers(self) -> List[int]:
        """Get list of running worker PIDs."""
        if not self.pid_file.exists():
            return []
        
        try:
            with open(self.pid_file, 'r') as f:
                pids = [int(line.strip()) for line in f if line.strip()]
            
            # Filter out dead processes
            running_pids = [pid for pid in pids if self._is_process_running(pid)]
            
            # Update PID file with only running processes
            if len(running_pids) != len(pids):
                if running_pids:
                    self._save_pids(running_pids)
                else:
                    self.pid_file.unlink()
            
            return running_pids
        except Exception as e:
            print(f"Error reading PID file: {e}")
            return []
    
    def _is_process_running(self, pid: int) -> bool:
        """Check if a process is running."""
        try:
            process = psutil.Process(pid)
            return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False