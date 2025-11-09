# QueueCTL - A CLI-based background job queue system.

A robust, CLI-based job queue system featuring priority queuing, job timeouts, automatic retries with exponential backoff, and a real-time web dashboard. Built for production workloads with reliability and monitoring in mind.

## 🎬 Demo Video

<div align="center">
  <img src="queuectl-demo.gif" alt="QueueCTL Demo" width="600"/>
  <p><em>Watch QueueCTL in action – Real-time job queue processing with priority, timeout, and Flask dashboard.</em></p>
</div>

### 📺 Detailed Walkthrough

For a full demonstration covering job enqueueing, worker management, timeout handling, DLQ operations, and dashboard monitoring:

<div align="center">
  <a href="https://youtu.be/XIzQPtGxWyo" target="_blank">
    <img src="https://img.youtube.com/vi/XIzQPtGxWyo/maxresdefault.jpg" alt="QueueCTL Full Walkthrough" width="500"/>
  </a>
  <p><em>🎥 <strong>Complete QueueCTL Walkthrough</strong> — Deep dive into priority queues, job timeouts, DLQ retry, and the live dashboard</em></p>
  <p><a href="https://youtu.be/XIzQPtGxWyo" target="_blank">▶️ Watch on YouTube</a></p>
</div>


## 🎯 Features

- ✅ **Priority Queueing** - Support for high/medium/low priority jobs
- ✅ **Job Timeouts** - Per-job and global timeout configuration
- ✅ **Real-time Dashboard** - Flask-based web UI for monitoring
- ✅ **CLI-Based Interface** - Complete command-line control
- ✅ **Multi-Worker Support** - Run multiple workers in parallel
- ✅ **Persistent Storage** - SQLite-based storage with ACID guarantees
- ✅ **Automatic Retries** - Smart exponential backoff mechanism
- ✅ **Dead Letter Queue** - Handle permanently failed jobs
- ✅ **Job Locking** - Race-condition-free job processing
- ✅ **Graceful Shutdown** - Clean worker process management
- ✅ **Comprehensive Monitoring** - Real-time stats and job tracking

## 📋 Table of Contents

- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [Architecture](#-architecture)
  - [System Components](#system-components)
  - [Dashboard & API Architecture](#dashboard--api-architecture)
  - [Data Flow & Job States](#data-flow--job-states)
- [Usage Examples](#-usage-examples)
- [CLI Reference](#-cli-reference)
- [Technical Details](#-technical-details)
  - [Job Lifecycle](#job-lifecycle)
  - [Priority Implementation](#priority-implementation)
  - [Timeout Mechanism](#timeout-mechanism)
  - [Retry Logic](#retry-logic)
- [Configuration](#-configuration)
- [Dashboard Usage](#-dashboard-usage)
- [Testing](#-testing)
- [Project Structure](#-project-structure)
- [Contact](#-contact)
- [License](#-license)

## 🚀 Installation

### Prerequisites

- Python 3.7 or higher
- pip (Python package installer)
- `tmux` (for the `start.sh` script)

### Setup

1. Clone the repository:
```bash
git clone [https://github.com/indra057/queuectl.git](https://github.com/indra057/queuectl.git)
cd queuectl


2. Make scripts executable:
```bash
chmod +x setup.sh start.sh stop.sh clean.sh
```

3. Run setup script:
```bash
./setup.sh
```
This will create a Python virtual environment and install all dependencies.

4. Start the system:
```bash
./start.sh
```
This will start the dashboard and activate the environment.

5. Stop the system:
```bash
./stop.sh
```

6. Clean everything (if needed):
```bash
./clean.sh
```

## ⚡ Quick Start

```bash
# 1. Initial setup
chmod +x setup.sh start.sh stop.sh clean.sh
./setup.sh

# 2. Start the system (launches dashboard and shell)
./start.sh

# 3. Enqueue a job
queuectl enqueue '{"id":"hello","command":"echo Hello, QueueCTL!"}'

# 4. Start worker and check status
queuectl worker start --count 1
queuectl status

# 5. View dashboard
# Open http://127.0.0.1:5000 in your browser

# 6. When finished, stop the system
./stop.sh

# 7. To clean everything and start fresh
./clean.sh
```

## 🏗️ Architecture

### System Components

```
┌─────────────────────────────────────────────────────────┐
│                    QueueCTL CLI                         │
│   (queuectl enqueue, queuectl worker start, queuectl status)│
└─────────────┬───────────────────────────┬───────────────┘
              │                           │
              │(Enqueues Jobs)            │(Starts Workers)
              │                           │
              ▼                           ▼
┌─────────────────────────┐   ┌───────────────────────────┐
│     SQLite Database     │   │     Worker Processes      │
│     (queuectl.db)       │   │  (worker_logic.py)        │
│ ----------------------- │   │ - Fetches & locks jobs    │
│ - Jobs Table            │◄──┤ - Executes commands       │
│ - Config Table          │   │ - Updates job status      │
│ - (Single Source of Truth)│   └───────────────────────────┘
└─────────────▲─────────┘
              │
              │(Reads data every 3s)
              │
┌─────────────────────────┐
│   Web Dashboard (Flask) │
│   (dashboard.py)        │
│ - Reads DB for status   │
│ - Serves API & HTML     │
└─────────────────────────┘
```

### 🖥️ Dashboard & API Architecture

The **QueueCTL Dashboard** provides real-time job and worker monitoring through a simple web-based interface, keeping the CLI and workers separate from the web layer.

#### ⚙️ Architecture Overview

- **Backend (`dashboard.py`)** —  
  A standalone **Flask web server** that reads data from `queuectl.db` using the `Storage` class.  
  It doesn’t execute any jobs; its role is purely to serve JSON data for the frontend.

- **Frontend (`index.html`)** —  
  A lightweight **single-page web app** that runs in your browser.  
  It fetches live data from the backend API and displays job and worker stats dynamically.

- **API Endpoint (`/api/status`)** —  
  The frontend polls this endpoint every **3 seconds**, and the backend responds with a JSON snapshot of all jobs, workers, and queue metrics.

- **Data Flow** —  
  JavaScript in `index.html` receives this JSON, updates job counts, worker tables, and visual indicators —  
  creating a **real-time dashboard** without page reloads.

#### 🔄 Real-time Flow


```
───────────────────────┐         ┌──────────────────────────┐
│   User's Browser      │         │     Flask Server         │
│  (index.html + JS)    │         │    (dashboard.py)        │
└──────────┬────────────┘         └──────────┬───────────────┘
           │                                │
    1. JS runs setInterval()              │
           │                                │
    2. fetch('/api/status') ─────────────► 3. /api/status endpoint
           │                                │
           │                                │    4. storage.get_dashboard_data()
           │                                │       storage.get_worker_status()
           │                                │                 │
           │                                │                 ▼
           │                                │     ┌───────────────────┐
           │                                │     │   SQLite DB       │
           │                                ├────►│  (queuectl.db)    │
           │                                │     └───────────────────┘
           │                                │                 ▲
           │                                │                 │
    7. JSON data returned   ◄───────────── 6. Format data as JSON
           │                                │
           │                                │
    8. JS updates HTML tables & counts    │
           │                                │
           ◄───────(repeat every 3s)───────┘

```

### Data Flow & Job States
### Data Flow
1. **Job Submission**: User enqueues jobs via CLI → Stored in SQLite
2. **Job Acquisition**: Worker acquires job with atomic locking
3. **Job Execution**: Worker executes command in subprocess
4. **Result Handling**:
   - **Success**: Job marked as completed
   - **Failure**: Job scheduled for retry with exponential backoff
   - **Max Retries Exceeded**: Job moved to Dead Letter Queue

### Job States

| State | Description |
|-------|-------------|
| `pending` | Waiting to be picked up by a worker |
| `processing` | Currently being executed by a worker |
| `completed` | Successfully executed |
| `failed` | Failed but retryable (scheduled for retry) |
| `dead` | Permanently failed (in DLQ) |



### Priority Queue System
```
                High Priority Queue (1)
                       ▲
                       │
                Medium Queue (2)
                       ▲
                       │
                 Low Queue (3)
                       
Worker Selection: priority ASC, created_at ASC
```

### Job Timeout System
```
┌─────────────┐     ┌────────────┐     ┌───────────┐
│  Per-Job    │     │  Global    │     │   Kill    │
│  Timeout    ├────►│  Timeout   ├────►│  Signal   │
└─────────────┘     └────────────┘     └───────────┘
      (30s)            (300s)         (Force stop)
```



### Persistence Strategy

- **Database**: SQLite for ACID compliance and simplicity
- **Thread Safety**: Connection pooling with thread-local storage
- **Atomic Operations**: Database-level locking for job acquisition
- **Crash Recovery**: Jobs in `processing` state released on startup

## 📚 Usage Examples

### Basic Job Operations

```bash
# Simple job
queuectl enqueue '{"id":"hello-world","command":"echo Hello, QueueCTL!"}'

# High priority job
queuectl enqueue -p high '{"id":"urgent","command":"echo URGENT"}'

# Job with timeout
queuectl enqueue '{"id":"long-job","command":"sleep 60","timeout":30}'

# Job with retries
queuectl enqueue '{"id":"retry-job","command":"exit 1","max_retries":5}'
```

### Worker Management

```bash
# Start single worker
queuectl worker start

# Start multiple workers
queuectl worker start --count 3

# Check worker status
queuectl worker status

# Stop workers gracefully
queuectl worker stop

# Force stop workers
queuectl worker stop --force
```

### Job Monitoring

```bash
# Overall system status
queuectl status

# List all jobs
queuectl list

# List jobs by state
queuectl list --state pending
queuectl list --state completed
queuectl list --state failed

# Get specific job details
queuectl get job1

# Limit results
queuectl list --limit 10
```

### Dead Letter Queue (DLQ) Operations

```bash
# List failed jobs in DLQ
queuectl dlq list

# Retry a specific job
queuectl dlq retry job1

# Retry with reset attempts
queuectl dlq retry job1 --reset-attempts

# Clear all DLQ jobs
queuectl dlq clear
```

### Configuration Management

```bash
# Show current configuration
queuectl config show

# Set maximum retries
queuectl config set max-retries 5

# Set backoff base (exponential)
queuectl config set backoff-base 3

# Set job timeout (seconds)
queuectl config set job-timeout 600
```

### Data Management

```bash
# Clear completed jobs
queuectl clear --state completed

# Clear all jobs (with confirmation)
queuectl clear
```

## 📖 CLI Commands

### Core Commands

| Command | Description |
|---------|-------------|
| `queuectl enqueue <json>` | Add a new job to the queue |
| `queuectl status` | Show system status and job counts |
| `queuectl list [--state STATE]` | List jobs, optionally filtered |
| `queuectl get <job_id>` | Get detailed job information |
| `queuectl clear [--state STATE]` | Delete jobs from queue |

### Worker Commands

| Command | Description |
|---------|-------------|
| `queuectl worker start [--count N]` | Start N worker processes |
| `queuectl worker stop [--force]` | Stop all workers |
| `queuectl worker status` | Show running worker details |

### DLQ Commands

| Command | Description |
|---------|-------------|
| `queuectl dlq list` | List all jobs in DLQ |
| `queuectl dlq retry <job_id>` | Retry a failed job |
| `queuectl dlq clear` | Clear all DLQ jobs |

### Config Commands

| Command | Description |
|---------|-------------|
| `queuectl config show` | Display current configuration |
| `queuectl config set <key> <value>` | Update configuration value |

## 🔄 Job Lifecycle

```
┌──────────┐
│ Enqueued │
└────┬─────┘
     │
     ▼
┌─────────┐
│ PENDING │◄──────────┐
└────┬────┘           │
     │                │ Retry scheduled
     │ Worker picks   │ (exponential backoff)
     ▼                │
┌────────────┐    ┌───┴────┐
│ PROCESSING │───►│ FAILED │
└────┬───────┘    └───┬────┘
     │                │
     │ Success        │ Max retries
     ▼                ▼
┌───────────┐    ┌──────┐
│ COMPLETED │    │ DEAD │ (DLQ)
└───────────┘    └──────┘
```

### Retry Mechanism

**Exponential Backoff Formula**: `delay = base ^ attempts`

Example with `backoff_base = 2`:
- Attempt 1 fails → retry in 2^1 = 2 seconds
- Attempt 2 fails → retry in 2^2 = 4 seconds
- Attempt 3 fails → retry in 2^3 = 8 seconds
- Max retries (3) exceeded → move to DLQ

### Concurrency & Locking

- **Job Acquisition**: Atomic database transaction
- **Lock Mechanism**: Jobs marked with `locked_by` worker ID
- **Stale Lock Recovery**: Locks older than 5 minutes auto-released
- **Duplicate Prevention**: One job processed by one worker only

## ⚙️ Configuration

### Default Settings

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max-retries` | 3 | Maximum retry attempts |
| `backoff-base` | 2 | Exponential backoff base |
| `worker-poll-interval` | 1.0 | Seconds between job polls |
| `job-timeout` | 300 | Job execution timeout (seconds) |

### Modifying Configuration

```bash
# Increase max retries
queuectl config set max-retries 5

# Change backoff base for faster/slower retries
queuectl config set backoff-base 3

# Adjust worker polling
queuectl config set worker-poll-interval 2.0

# Set job timeout
queuectl config set job-timeout 600
```

**Note**: Configuration changes require worker restart to take effect.

## 🧪 Testing

### Automated Test Suite

Run the full test suite:
```bash
./run_full_test.sh
```

The test suite covers:
- ✅ Priority queue ordering
- ✅ Job timeout handling
- ✅ Retry mechanism with backoff
- ✅ DLQ operations
- ✅ Worker management
- ✅ Concurrent processing
- ✅ Data persistence
- ✅ Race conditions
- ✅ Dashboard functionality

### Manual Testing Scenarios

#### Test 1: Priority Queue
```bash
# 1. Submit jobs with different priorities
queuectl enqueue -p low '{"id":"low","command":"echo Low"}'
queuectl enqueue -p high '{"id":"high","command":"echo High"}'
queuectl enqueue -p medium '{"id":"med","command":"echo Medium"}'

# 2. Observe execution order
queuectl worker start -c 1
queuectl list --state completed  # Should show High → Medium → Low
```

#### Test 2: Job Timeouts
```bash
# 1. Global timeout
queuectl config set job-timeout 5
queuectl enqueue '{"id":"timeout1","command":"sleep 10"}'

# 2. Per-job timeout
queuectl enqueue '{"id":"timeout2","command":"sleep 20","timeout":3}'

# 3. Check results
queuectl worker start -c 1
sleep 10
queuectl list --state failed
```

#### Test 3: Retry & DLQ
```bash
# 1. Create failing jobs
queuectl enqueue '{"id":"dlq1","command":"exit 1","max_retries":2}'
queuectl enqueue '{"id":"dlq2","command":"exit 1","max_retries":2}'

# 2. Watch retry process
queuectl worker start -c 1
sleep 15  # Wait for retries + backoff
queuectl dlq list

# 3. Test DLQ operations
queuectl dlq retry dlq1 --reset-attempts
queuectl dlq clear
```

#### Test 4: Dashboard & Monitoring
```bash
# 1. Start the system
./start.sh

# 2. Generate load
for i in {1..5}; do
    queuectl enqueue -p high "{\"id\":\"h$i\",\"command\":\"sleep 2\"}"
    queuectl enqueue -p low "{\"id\":\"l$i\",\"command\":\"sleep 2\"}"
done

# 3. Start workers
queuectl worker start -c 3

# 4. Monitor via dashboard
# Open http://127.0.0.1:5000 in browser
# Watch real-time updates
```

### Assumptions & Trade-offs 

### Assumptions

1. **Execution Environment**: Workers run on same machine as CLI
2. **Shell Commands**: All job commands are shell-executable
3. **Storage**: Single SQLite database file sufficient for use case
4. **Concurrency**: Worker count limited by system resources
5. **Command Output**: stdout/stderr handled via subprocess, not stored

### Trade-offs

| Decision | Rationale | Alternative |
|----------|-----------|-------------|
| **SQLite vs Distributed Queue** | Simplicity, ACID guarantees, single-machine deployment | Redis/RabbitMQ for distributed systems |
| **Subprocess vs Thread Pool** | Isolation, security, handles any command | Thread pool for Python-only tasks |
| **File-based PID tracking** | Simple, no additional dependencies | Process manager like systemd |
| **Polling vs Events** | Simple implementation, predictable behavior | Event-driven for lower latency |
| **No job output storage** | Reduced storage overhead | Store outputs for audit trail |

### Limitations

- **Single Machine**: Not designed for distributed deployment
- **No Job Priority**: All jobs FIFO within state
- **No Scheduled Jobs**: No built-in cron-like scheduling
- **Basic Monitoring**: No built-in metrics/alerting
- **Command-only**: Cannot execute Python functions directly

### Potential Enhancements

- [ ] Scheduled/delayed job execution (`run_at` field)
- [ ] Job output/log storage
- [ ] Metrics and statistics (success rate, avg execution time)
- [ ] Job dependencies (DAG execution)
- [ ] Distributed mode with Redis backend
- [ ] Webhook notifications on job completion

## 📁 Project Structure

```
queuectl/
├── queuectl/
│   ├── __init__.py       # Package initialization
│   ├── cli.py            # CLI implementation (Click)
│   ├── config.py         # Configuration management
│   ├── dashboard.py      # Flask dashboard server
│   ├── database.py       # SQLite storage layer
│   ├── entities.py       # Data models (Job, Config)
│   ├── worker_logic.py   # Worker process core
│   ├── worker_manager.py # Process management
│   └── templates/
│       └── index.html    # Dashboard template
├── setup.py              # Package setup
├── setup.sh             # Environment setup
├── start.sh            # Start dashboard & shell
├── stop.sh            # Stop processes
├── clean.sh          # Cleanup script
├── run_examples.sh   # Usage examples
└── run_full_test.sh  # Test suite
```

### Component Details

#### Core Modules
- **cli.py**: Click-based CLI with command handlers
- **config.py**: Configuration with file persistence
- **database.py**: SQLite storage with ACID properties
- **entities.py**: Job/Config dataclasses
- **worker_logic.py**: Job execution & retry logic
- **worker_manager.py**: Process lifecycle control

#### Web Dashboard
- **dashboard.py**: Flask server implementation
- **index.html**: Real-time monitoring UI
  - Job counts by state
  - Active worker status
  - Real-time job updates
  - DLQ monitoring

#### Scripts
- **setup.sh**: Creates venv, installs deps
- **start.sh**: Launches dashboard & shell
- **stop.sh**: Graceful process shutdown
- **clean.sh**: Full system cleanup
- **run_examples.sh**: Usage demonstrations
- **run_full_test.sh**: Comprehensive tests

## 🔧 Development

### Running from Source

The project provides a small script-based workflow (see `setup.sh`, `start.sh`, `stop.sh`). For development you can either use the provided venv or run the CLI module directly.

Option A — use the project scripts (recommended):

```bash
# Make sure scripts are executable (one-time)
chmod +x setup.sh start.sh stop.sh clean.sh

# Create virtual environment and install deps
./setup.sh

# Activate the created venv
source venv/bin/activate

# Run the CLI or use the installed entry point
queuectl --help
```

Option B — run from source (no install):

```bash
# From the project root
source venv/bin/activate    # if you created the venv via setup.sh
python -m queuectl.cli --help
```

Option C — install editable (for development iteration):

```bash
# Inside an activated venv
pip install -e .
queuectl --help
```

> Note: `setup.sh` creates the `venv` and installs required dependencies; `start.sh` launches the dashboard and spawns an interactive shell.

### Code Structure (actual files)

- `cli.py` – Click-based CLI (entry point used by the `queuectl` command)
- `config.py` – Configuration manager with on-disk persistence
- `dashboard.py` – Flask web server and API for the dashboard
- `database.py` – SQLite storage, query helpers and migrations (Storage class)
- `entities.py` – Data models: `Job`, `Config`, `JobState`
- `worker_logic.py` – Worker implementation: acquisition, execution, retries
- `worker_manager.py` – Start/stop/status for worker processes (PID file)
- `templates/index.html` – Dashboard UI template used by Flask

- Top-level scripts: `setup.sh`, `start.sh`, `stop.sh`, `clean.sh`, `run_examples.sh`, `run_full_test.sh`

If you add files during development, keep the `setup.py` / `find_packages()` in sync so editable installs work correctly.



## 📫 Contact

- **Author:** Indrajit Das
- **Email:** indrajiitdas057@gmail.com
- **GitHub:** https://github.com/indra057

## 📝 License

This project is licensed under the MIT License.
