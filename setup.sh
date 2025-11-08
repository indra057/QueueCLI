#!/bin/bash
echo "--- 1. Creating Python Virtual Environment (venv) ---"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ Virtual environment created."
else
    echo "ℹ️ Virtual environment already exists."
fi

echo ""
echo "--- 2. Activating Environment & Installing Dependencies ---"
(
    source venv/bin/activate
    
    # Reads your setup.py and installs your project + dependencies
    echo "Installing queuectl and all dependencies..."
    pip install -e .
    
    # Install dashboard dependency
    echo "Installing Flask for the dashboard..."
    pip install Flask
)

echo ""
echo "--- ✅ Setup Complete! ---"
echo "You can now run ./start.sh to launch the application."