#!/bin/bash

# --- 1. Check if setup has been run ---
if [ ! -f "venv/bin/activate" ]; then
    echo "❌ Error: Virtual environment not found."
    echo "Please run ./setup.sh first to install dependencies."
    exit 1
fi

# --- 2. Activate the environment ---
echo "Activating virtual environment..."
source venv/bin/activate

# --- 3. Stop any old processes (just in case) ---
echo "Stopping any old dashboard or worker processes..."
# We'll use a .pid file to be very specific
if [ -f .dashboard.pid ]; then
    kill $(cat .dashboard.pid) 2>/dev/null || true
    rm -f .dashboard.pid
fi
queuectl worker stop --force >/dev/null 2>&1

# --- 4. Start the dashboard in the background ---
echo "Starting dashboard in the background..."
echo "(Logs will be saved to dashboard.log)"

# 'nohup' keeps it running, '&' puts it in the background
# Output is sent to 'dashboard.log'
nohup python3 -m queuectl.dashboard > dashboard.log 2>&1 &

# Save the Process ID (PID) of the dashboard
echo $! > .dashboard.pid

sleep 1 # Give it a second to start
echo "✅ Dashboard is running at http://127.0.0.1:5000"
echo "--------------------------------------------------"
echo ""
echo "✅ You are now in an activated shell."
echo "You can run your commands (e.g., ./run_examples.sh or queuectl --help)"
echo "Type 'exit' or press Ctrl+D to leave this shell."
echo "Run ./stop.sh to stop the background dashboard."
echo ""

# --- 5. Start a new shell session ---
# 'exec bash' replaces the script with a new shell.
# When you 'exit' this shell, the script is done.
exec bash