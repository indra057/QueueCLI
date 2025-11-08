#!/bin/bash

# QueueCTL Usage Examples
# Demonstrates various features of the job queue system

echo "======================================"
echo "QueueCTL Usage Examples"
echo "======================================"
echo ""

# Cleanup from previous runs
echo "Cleaning up from previous runs..."
queuectl worker stop --force 2>/dev/null || true
rm -f queuectl.db queuectl.db-journal .queuectl_workers.pid
sleep 1
echo ""

# Example 1: Basic Job
echo "Example 1: Basic Job Execution"
echo "--------------------------------"
queuectl enqueue '{"id":"hello-world","command":"echo Hello, QueueCTL!"}'
queuectl status
queuectl worker start --count 1
sleep 2
queuectl list --state completed
queuectl worker stop --force >/dev/null 2>&1 || true
echo ""

# Example 2: Multiple Jobs
echo "Example 2: Multiple Jobs in Parallel"
echo "-------------------------------------"
queuectl enqueue '{"id":"job-1","command":"echo Job 1 && sleep 2"}'
queuectl enqueue '{"id":"job-2","command":"echo Job 2 && sleep 2"}'
queuectl enqueue '{"id":"job-3","command":"echo Job 3 && sleep 2"}'
queuectl worker start --count 2
sleep 5
queuectl status
queuectl worker stop --force >/dev/null 2>&1 || true
echo ""

# Example 3: Job with Failure and Retry (Visible Demo)
echo "Example 3: Job Failure with Retry (Visible Backoff Demo)"
echo "---------------------------------------------------------"

# Cleanup first
queuectl worker stop --force >/dev/null 2>&1 || true
rm -f .queuectl_workers.pid

# Enqueue a job that always fails (exit 1)
queuectl enqueue '{"id":"fail-retry-demo","command":"exit 1","max_retries":3}'

# Start a single worker in background and capture its output live
echo ""
echo "🚀 Starting worker... You’ll see each retry attempt below:"
echo "=========================================================="
python3 -c "from queuectl.worker_logic import run_worker; run_worker('demo-worker','queuectl.db')" &
WORKER_PID=$!

# Wait and show retry status updates
for i in {1..4}; do
    echo ""
    echo "🔍 Checking status (attempt cycle $i)..."
    queuectl list --state failed || true
    queuectl dlq list || true
    sleep 5
done

# Stop the live worker
echo ""
echo "🛑 Stopping worker..."
kill -TERM $WORKER_PID 2>/dev/null || true
sleep 1

# Show final DLQ
echo ""
echo "📦 Final DLQ state:"
queuectl dlq list
echo ""

# Example 4: Job Timeout Handling
echo "Example 4: Job Timeout Handling"
echo "--------------------------------"
queuectl enqueue '{"id":"timeout-job","command":"sleep 5 && echo Done!","timeout":2}'
queuectl worker start --count 1
echo "Waiting for timeout..."
sleep 6
queuectl list --state failed
queuectl dlq list
queuectl worker stop --force >/dev/null 2>&1 || true
echo ""

# Example 5: Priority Queues
echo "Example 5: Job Priority Queues"
echo "--------------------------------"
queuectl enqueue '{"id":"low-priority","command":"echo Low Priority","priority":3}'
queuectl enqueue '{"id":"high-priority","command":"echo High Priority","priority":1}'
queuectl worker start --count 1
sleep 4
queuectl list --state completed
queuectl worker stop --force >/dev/null 2>&1 || true
echo ""

# Example 6: Configuration
echo "Example 6: Configuration Management"
echo "-----------------------------------"
queuectl config show
queuectl config set max-retries 5
queuectl config show
echo ""

# Example 7: DLQ Operations
echo "Example 7: Dead Letter Queue Operations"
echo "---------------------------------------"
queuectl dlq list
# Fixed DLQ_JOB extraction to ignore header "ID"
DLQ_JOB=$(queuectl dlq list 2>/dev/null | grep -oP '^\| [a-zA-Z0-9\-]+' | awk '{print $2}' | grep -v '^ID$' | head -1 || echo "")
if [ ! -z "$DLQ_JOB" ]; then
    echo "Retrying job from DLQ: $DLQ_JOB"
    queuectl dlq retry "$DLQ_JOB" --reset-attempts
    sleep 5
    queuectl status
fi
echo ""

# Example 8: Worker Management
echo "Example 8: Worker Management"
echo "----------------------------"
queuectl worker start --count 1
sleep 2
queuectl worker status
queuectl worker stop
sleep 2
queuectl worker status || echo "No workers running"
echo ""

# Example 9: Complex Commands
echo "Example 9: Complex Shell Commands"
echo "----------------------------------"
queuectl enqueue '{"id":"complex-1","command":"echo Start && sleep 1 && echo Middle && sleep 1 && echo End"}'
queuectl enqueue '{"id":"complex-2","command":"for i in 1 2 3; do echo Iteration $i; done"}'
queuectl worker start
sleep 5
queuectl list --state completed
queuectl worker stop --force >/dev/null 2>&1 || true
echo ""

# Final cleanup
echo "Cleaning up..."
queuectl worker stop --force 2>/dev/null || true
echo ""

echo "======================================"
echo "Examples Complete!"
echo "======================================"
echo ""
echo "Try these commands yourself:"
echo "  queuectl status              # Check system status"
echo "  queuectl list                # List all jobs"
echo "  queuectl worker start -c 3   # Start 3 workers"
echo "  queuectl dlq list            # View failed jobs"
echo "  queuectl config show         # View configuration"
