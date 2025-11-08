#!/bin/bash

echo "🧹 Starting a full project clean..."

# 1. Stop any running processes
echo "Stopping dashboard and workers..."
./stop.sh > /dev/null 2>&1

# 2. Remove virtual environment
echo "Removing Python virtual environment (venv)..."
rm -rf venv

# 3. Remove database files
echo "Removing database files..."
rm -f queuectl.db
rm -f queuectl.db-journal

# 4. Remove logs and temporary files
echo "Removing logs and temporary files..."
rm -f dashboard.log
rm -f .dashboard.pid
rm -f dashboard_status.json

# 5. Remove test artifacts
rm -f test_output.txt
rm -f fix_me.txt

# 6. Remove Python build/cache files
echo "Removing Python cache and build artifacts..."
rm -rf .pytest_cache
rm -rf queuectl.egg-info
find . -type d -name "__pycache__" -exec rm -rf {} +

echo "✅ Clean complete. Your project is reset."
echo "You can now run ./setup.sh to start over."