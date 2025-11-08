#!/bin/bash
echo "Stopping background dashboard..."

if [ ! -f .dashboard.pid ]; then
    echo "No dashboard process found (no .dashboard.pid file)."
else
    PID=$(cat .dashboard.pid)
    kill $PID 2>/dev/null
    rm -f .dashboard.pid
    echo "✅ Dashboard (PID: $PID) stopped."
fi

echo "Stopping all queuectl workers..."
source venv/bin/activate
queuectl worker stop --force

echo "✅ Cleanup complete."