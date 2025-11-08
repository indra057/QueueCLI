"""
Command-line interface for QueueCTL.
"""

import click
import json
import sys
from datetime import datetime
from tabulate import tabulate

from .entities import Job, JobState, Config
from .database import Storage
from .worker_manager import WorkerManager


# Create storage instance
storage = Storage()
manager = WorkerManager()


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """
    QueueCTL - A CLI-based background job queue system.
    
    Manage background jobs with worker processes, automatic retries, and DLQ support.
    """
    pass


@cli.command()
@click.option('--priority', '-p', type=click.Choice(['high', 'medium', 'low']), default=None,
              help='Job priority (high, medium, low)')
@click.option('--timeout', '-t', type=int, default=None, help='Job timeout in seconds')
@click.argument('job_json', type=str)
def enqueue(priority, timeout, job_json):
    """
    Add a new job to the queue.
    
    JOB_JSON: JSON string or file path containing job definition
    
    Example:
        queuectl enqueue '{"id":"job1","command":"echo Hello"}'
    """
    try:
        if job_json.startswith('@'):
            file_path = job_json[1:]
            with open(file_path, 'r') as f:
                job_data = json.load(f)
        else:
            job_data = json.loads(job_json)
        
        config = storage.get_config()
        if 'max_retries' not in job_data:
            job_data['max_retries'] = config.max_retries

        # Priority handling: CLI flag overrides JSON; default to medium (2)
        priority_map = {'high': 1, 'medium': 2, 'low': 3}
        if priority:
            job_data['priority'] = priority_map.get(priority, 2)
        else:
            if 'priority' not in job_data:
                job_data['priority'] = 2

        # Timeout handling: CLI flag overrides JSON; if not set, let it be None to fall back to config
        if timeout is not None:
            job_data['timeout'] = int(timeout)
        else:
            if 'timeout' not in job_data:
                job_data['timeout'] = None
        
        job = Job.from_dict(job_data)
        existing_job = storage.get_job(job.id)
        if existing_job:
            click.echo(f"Error: Job with ID '{job.id}' already exists", err=True)
            sys.exit(1)
        
        if storage.save_job(job):
            click.echo(f"✓ Job '{job.id}' enqueued successfully")
            click.echo(f"  Command: {job.command}")
            click.echo(f"  Max retries: {job.max_retries}")
            click.echo(f"  Priority: {job.priority}")
            click.echo(f"  Timeout: {job.timeout if job.timeout is not None else f'{config.job_timeout} (global)'}s")
        else:
            click.echo("Error: Failed to enqueue job", err=True)
            sys.exit(1)
    
    except json.JSONDecodeError as e:
        click.echo(f"Error: Invalid JSON: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

@cli.group(epilog="""
\b
Examples:
  Start 3 workers:
    queuectl worker start -c 3
\b
  Check worker status:
    queuectl worker status
\b
  Stop all workers gracefully:
    queuectl worker stop
\b
  Force kill all workers:
    queuectl worker stop --force
""")
def worker():
    """Manage worker processes."""
    pass

@worker.command('start')
@click.option('--count', '-c', default=1, type=int, help='Number of workers to start')
def worker_start(count):
    """Start one or more worker processes."""
    if count < 1:
        click.echo("Error: Worker count must be at least 1", err=True)
        sys.exit(1)
    
    pids = manager.start_workers(count)
    if not pids:
        sys.exit(1)


@worker.command('stop')
@click.option('--force', '-f', is_flag=True, help='Force kill workers immediately')
def worker_stop(force):
    """Stop all running workers."""
    count = manager.stop_workers(graceful=not force)
    if count == 0:
        sys.exit(1)


@worker.command('status')
def worker_status():
    """Show status of running workers."""
    workers = manager.get_worker_status()
    if not workers:
        click.echo("No workers running")
        return
    
    table_data = []
    for w in workers:
        table_data.append([
            w['pid'],
            w['status'],
            f"{w['cpu_percent']:.1f}%",
            f"{w['memory_mb']:.1f} MB",
            w['created']
        ])
    
    click.echo("\n" + tabulate(
        table_data,
        headers=['PID', 'Status', 'CPU', 'Memory', 'Started'],
        tablefmt='grid'
    ))
    click.echo(f"\nTotal workers: {len(workers)}")


@cli.command()
def status():
    """Show summary of all job states and active workers."""
    counts = storage.get_job_counts()
    workers = manager.get_worker_status()
    
    click.echo("\n=== QueueCTL Status ===\n")
    click.echo("Jobs by State:")
    
    table_data = []
    for state in [JobState.PENDING, JobState.PROCESSING, JobState.COMPLETED, 
                  JobState.FAILED, JobState.DEAD]:
        count = counts.get(state, 0)
        icon = "●" if count > 0 else "○"
        table_data.append([icon, state.upper(), count])
    
    click.echo(tabulate(table_data, headers=['', 'State', 'Count'], tablefmt='simple'))
    click.echo(f"\nTotal jobs: {sum(counts.values())}")
    click.echo(f"\nActive workers: {len(workers)}")
    
    config = storage.get_config()
    click.echo("\nConfiguration:")
    click.echo(f"  Max retries: {config.max_retries}")
    click.echo(f"  Backoff base: {config.backoff_base}")
    click.echo(f"  Job timeout: {config.job_timeout}s")
    click.echo()


# ✅ Modified Section: Added "Updated At" column
@cli.command('list')
@click.option('--state', '-s', type=str, help='Filter by job state')
@click.option('--limit', '-l', type=int, default=50, help='Maximum number of jobs to show')
def list_jobs(state, limit):
    """List jobs, optionally filtered by state."""
    if state:
        state = state.lower()
        if state not in [JobState.PENDING, JobState.PROCESSING, JobState.COMPLETED,
                         JobState.FAILED, JobState.DEAD]:
            click.echo(f"Error: Invalid state '{state}'", err=True)
            sys.exit(1)
        jobs = storage.get_jobs_by_state(state)
    else:
        jobs = storage.get_all_jobs()
    
    if not jobs:
        click.echo("No jobs found")
        return
    
    jobs = jobs[:limit]
    table_data = []
    for job in jobs:
        command = job.command[:37] + "..." if len(job.command) > 40 else job.command
        error = ""
        if job.error_message:
            error = job.error_message[:27] + "..." if len(job.error_message) > 30 else job.error_message
        
        # Priority display: map numeric to human label
        pri_map = {1: 'high', 2: 'medium', 3: 'low'}
        priority_display = pri_map.get(getattr(job, 'priority', 2), getattr(job, 'priority', 2))

        table_data.append([
            job.id,
            command,
            priority_display,
            job.state,
            f"{job.attempts}/{job.max_retries}",
            error,
            job.created_at[:19],
            job.updated_at[:19] if job.updated_at else "-"
        ])
    
    click.echo("\n" + tabulate(
        table_data,
        headers=['ID', 'Command', 'Priority', 'State', 'Attempts', 'Error', 'Created', 'Updated'],
        tablefmt='grid'
    ))
    
    click.echo(f"\nShowing {len(jobs)} job(s)")
    if len(jobs) == limit:
        click.echo(f"(Limited to {limit} results. Use --limit to show more)")


@cli.command('get')
@click.argument('job_id', type=str)
def get_job(job_id):
    """Get detailed information about a specific job."""
    job = storage.get_job(job_id)
    if not job:
        click.echo(f"Error: Job '{job_id}' not found", err=True)
        sys.exit(1)
    click.echo("\n" + job.to_json())


@cli.group(epilog="""
\b
Examples:
  List all failed jobs:
    queuectl dlq list
\b
  Retry a specific job:
    queuectl dlq retry job-id-123
\b
  Retry a job and reset its attempt count:
    queuectl dlq retry job-id-123 -r
\b
  Clear all jobs from the DLQ:
    queuectl dlq clear
""")
def dlq():
    """Manage Dead Letter Queue (DLQ)."""
    pass

@dlq.command('list')
def dlq_list():
    """List all jobs in the Dead Letter Queue."""
    jobs = storage.get_jobs_by_state(JobState.DEAD)
    if not jobs:
        click.echo("No jobs in DLQ")
        return
    
    table_data = []
    for job in jobs:
        command = job.command[:37] + "..." if len(job.command) > 40 else job.command
        error = (job.error_message or "")[:37] + "..." if job.error_message and len(job.error_message) > 40 else job.error_message
        table_data.append([
            job.id,
            command,
            job.attempts,
            error,
            job.updated_at[:19] if job.updated_at else "-"
        ])
    
    click.echo("\n" + tabulate(
        table_data,
        headers=['ID', 'Command', 'Attempts', 'Last Error', 'Failed At'],
        tablefmt='grid'
    ))
    click.echo(f"\nTotal jobs in DLQ: {len(jobs)}")


@dlq.command('retry')
@click.argument('job_id', type=str)
@click.option('--reset-attempts', '-r', is_flag=True, help='Reset attempt counter')
def dlq_retry(job_id, reset_attempts):
    """Retry a job from the Dead Letter Queue."""
    job = storage.get_job(job_id)
    if not job:
        click.echo(f"Error: Job '{job_id}' not found", err=True)
        sys.exit(1)
    if job.state != JobState.DEAD:
        click.echo(f"Error: Job '{job_id}' is not in DLQ (current state: {job.state})", err=True)
        sys.exit(1)
    
    job.state = JobState.PENDING
    job.error_message = None
    job.next_retry_at = None
    if reset_attempts:
        job.attempts = 0
    
    if storage.save_job(job):
        click.echo(f"✓ Job '{job_id}' moved back to pending queue")
        if reset_attempts:
            click.echo(f"  Attempts reset to 0")
    else:
        click.echo("Error: Failed to retry job", err=True)
        sys.exit(1)


@dlq.command('clear')
@click.confirmation_option(prompt='Are you sure you want to delete all DLQ jobs?')
def dlq_clear():
    """Clear all jobs from the Dead Letter Queue."""
    jobs = storage.get_jobs_by_state(JobState.DEAD)
    count = len(jobs)
    if count == 0:
        click.echo("No jobs in DLQ")
        return
    
    for job in jobs:
        storage.delete_job(job.id)
    click.echo(f"✓ Deleted {count} job(s) from DLQ")


@cli.group(epilog="""
\b
Examples:
  Show all settings:
    queuectl config show
\b
  Change the max retries:
    queuectl config set max_retries 5
\b
  Change the job timeout to 10 minutes (600s):
    queuectl config set job_timeout 600
""")
def config():
    """Manage system configuration."""
    pass

@config.command('show')
def config_show():
    """Show current configuration."""
    cfg = storage.get_config()
    table_data = [
        ['max-retries', cfg.max_retries, 'Maximum retry attempts for failed jobs'],
        ['backoff-base', cfg.backoff_base, 'Base for exponential backoff (base^attempts)'],
        ['worker-poll-interval', cfg.worker_poll_interval, 'Worker polling interval (seconds)'],
        ['job-timeout', cfg.job_timeout, 'Job execution timeout (seconds)']
    ]
    click.echo("\n=== Configuration ===\n")
    click.echo(tabulate(table_data, headers=['Key', 'Value', 'Description'], tablefmt='grid'))
    click.echo()


@config.command('set')
@click.argument('key', type=str)
@click.argument('value', type=str)
def config_set(key, value):
    """Set a configuration value."""
    key_map = {
        'max-retries': 'max_retries',
        'backoff-base': 'backoff_base',
        'worker-poll-interval': 'worker_poll_interval',
        'job-timeout': 'job_timeout'
    }
    
    # --- NEW: Define the correct type for each key ---
    key_type_map = {
        'max_retries': int,
        'backoff_base': int,
        'worker_poll_interval': float,
        'job_timeout': int
    }
    # -------------------------------------------------

    if key not in key_map:
        click.echo(f"Error: Invalid config key '{key}'", err=True)
        click.echo(f"Valid keys: {', '.join(key_map.keys())}", err=True)
        sys.exit(1)
    
    cfg = storage.get_config()
    cfg_dict = cfg.to_dict()
    internal_key = key_map[key]
    
    try:
        # --- UPDATED: Cast using the type map ---
        cast_func = key_type_map[internal_key]
        cfg_dict[internal_key] = cast_func(value)
        # ----------------------------------------
        
        new_cfg = Config.from_dict(cfg_dict)
        storage.save_config(new_cfg)
        
        click.echo(f"✓ Configuration updated: {key} = {cfg_dict[internal_key]}")
        click.echo(f"  Note: Restart workers for changes to take effect")
    except ValueError:
        click.echo(f"Error: Invalid value '{value}' for {key}. Expected a(n) {key_type_map[internal_key].__name__}.", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"An error occurred: {e}", err=True)
        sys.exit(1)




@cli.command('clear')
@click.option('--state', '-s', type=str, help='Clear jobs in specific state')
@click.confirmation_option(prompt='Are you sure you want to delete jobs?')
def clear_jobs(state):
    """Clear jobs from the queue."""
    if state:
        state = state.lower()
        if state not in [JobState.PENDING, JobState.PROCESSING, JobState.COMPLETED,
                         JobState.FAILED, JobState.DEAD]:
            click.echo(f"Error: Invalid state '{state}'", err=True)
            sys.exit(1)
        jobs = storage.get_jobs_by_state(state)
    else:
        jobs = storage.get_all_jobs()
    
    count = len(jobs)
    if count == 0:
        click.echo("No jobs to clear")
        return
    
    for job in jobs:
        storage.delete_job(job.id)
    click.echo(f"✓ Deleted {count} job(s)")


def main():
    """Entry point for the CLI."""
    try:
        cli()
    except KeyboardInterrupt:
        click.echo("\n\nInterrupted", err=True)
        sys.exit(130)
    except Exception as e:
        click.echo(f"\nError: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
