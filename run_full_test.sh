#!/bin/bash

# Enhanced QueueCTL FunctionalTest Suite
# Verifies core + advanced features, detects hangs, and logs debug info.

set +e  # Don't exit on first error; continue to collect all failures

echo "======================================"
echo "QueueCTL Diagnostic Test Suite"
echo "======================================"
echo ""

# --- Colors ---
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

TESTS_PASSED=0
TESTS_FAILED=0

DEBUG=${DEBUG:-0} # Enable with DEBUG=1 ./run_full_test.sh

# --- Utility Functions ---
section() {
    echo ""
    echo "================================================================================"
    echo "$1"
    echo "================================================================================"
}

cleanup() {
    echo ""
    echo "🧹 Cleaning up old data and workers..."
    queuectl worker stop --force >/dev/null 2>&1 || true
    # ✅ FIX: Added ./fix_me.txt to the cleanup
    rm -f queuectl.db queuectl.db-journal .queuectl_workers.pid worker.log test_output.txt ./fix_me.txt
    echo "Cleanup complete."
}

trap cleanup EXIT

run_test() {
    local name="$1"
    local cmd="$2"
    echo -e "${YELLOW}TEST:${NC} $name"
    [ "$DEBUG" -eq 1 ] && echo "→ $cmd"
    if eval "$cmd" >/dev/null 2>&1; then
        echo -e "${GREEN}✓ PASSED${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}✗ FAILED${NC}"
        ((TESTS_FAILED++))
    fi
    echo ""
}

# --- Setup ---
cleanup
section "SETUP ENVIRONMENT"
run_test "QueueCTL command available" "command -v queuectl >/dev/null"
run_test "Display help" "queuectl --help"
queuectl status

# --- Basic Enqueue/Execution Test ---
section "BASIC JOB EXECUTION"
queuectl enqueue '{"id":"basic-job","command":"echo Hello from QueueCTL > test_output.txt"}'
queuectl worker start --count 1 >worker.log 2>&1 &
sleep 4
run_test "Worker created output file" "grep -q 'Hello from QueueCTL' test_output.txt"
queuectl worker stop --force >/dev/null 2>&1

# --- Timeout Handling ---
section "JOB TIMEOUT TEST"
queuectl enqueue '{"id":"timeout-job","command":"sleep 4 && echo Done","timeout":2,"max_retries":1}'
queuectl worker start --count 1 >worker.log 2>&1 &

# Wait a bit longer to let the worker detect the timeout and update DB
echo "⏳ Waiting for job to time out..."
sleep 10

echo ""
echo "Current failed jobs:"
queuectl list --state failed || echo "No failed jobs yet"
echo ""

run_test "Job failed due to timeout" "queuectl dlq list | grep -q 'timeout-job'"


queuectl worker stop --force >/dev/null 2>&1


# --- Retry & Backoff Test ---
section "RETRY & BACKOFF TEST"
rm -f ./fix_me.txt # Ensure the file doesn't exist so the job fails
# ✅ FIX: Changed command from 'exit 1' to 'cat ./fix_me.txt'
queuectl enqueue '{"id":"retry-job","command":"cat ./fix_me.txt","max_retries":3}'
queuectl worker start --count 1 >worker.log 2>&1 &
sleep 15
queuectl dlq list
run_test "Retry job moved to DLQ" "queuectl dlq list | grep -q 'retry-job'"
queuectl worker stop --force >/dev/null 2>&1

# --- Priority Scheduling ---
section "PRIORITY QUEUE TEST"

# Enqueue jobs with different priorities
queuectl enqueue '{"id":"low-prio","command":"echo Low","priority":3}'
queuectl enqueue '{"id":"high-prio","command":"echo High","priority":1}'

# Start a single worker so it must choose which job to run first
queuectl worker start --count 1 >worker.log 2>&1 &
sleep 6  # allow enough time for both jobs to complete

# Check which job completed first using the database timestamps
first_completed=$(sqlite3 queuectl.db "SELECT id FROM jobs 
WHERE state='completed' AND id IN ('high-prio','low-prio') 
ORDER BY updated_at ASC LIMIT 1;")


if [[ "$first_completed" == "high-prio" ]]; then
    echo -e "${GREEN}✓ Priority scheduling correct${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}✗ Priority scheduling incorrect${NC}"
    ((TESTS_FAILED++))
    echo "  Expected 'high-prio' to complete before 'low-prio', got: $first_completed"
fi

queuectl worker stop --force >/dev/null 2>&1


# --- DLQ Retry Test ---
section "DEAD LETTER QUEUE TEST"
queuectl dlq list

# We specifically want to test the 'retry-job', which we've designed to be fixable
DLQ_JOB="retry-job" 

if queuectl dlq list 2>/dev/null | grep -q "$DLQ_JOB"; then
    echo "Fixing external condition for job '$DLQ_JOB'..."
    # ✅ FIX: This command now fixes the 'cat ./fix_me.txt' job
    touch ./fix_me.txt # Create the file, so 'cat ./fix_me.txt' will now succeed

    echo "Retrying DLQ job: $DLQ_JOB"
    queuectl dlq retry "$DLQ_JOB" --reset-attempts

    # Start worker to reprocess job
    queuectl worker start --count 1 >worker.log 2>&1 &
    echo "⏳ Waiting for reprocessed job to complete..."

    for i in {1..15}; do
        # ✅ Directly query DB for accuracy
        if sqlite3 queuectl.db "SELECT state FROM jobs WHERE id='$DLQ_JOB';" | grep -q 'completed'; then
            echo -e "${GREEN}✓ Job reprocessed successfully${NC}"
            ((TESTS_PASSED++))
            queuectl worker stop --force >/dev/null 2>&1
            break
        fi
        sleep 1
    done

    # Fallback if still not found
    if ! sqlite3 queuectl.db "SELECT state FROM jobs WHERE id='$DLQ_JOB';" | grep -q 'completed'; then
        echo -e "${RED}✗ DLQ job reprocessed successfully${NC}"
        ((TESTS_FAILED++))
        queuectl worker stop --force >/dev/null 2>&1
    fi
else
    # This might happen if the retry-job succeeded, which would be a bug
    echo -e "${YELLOW}Job '$DLQ_JOB' not in DLQ — skipping retry test.${NC}"
    ((TESTS_FAILED++))
fi