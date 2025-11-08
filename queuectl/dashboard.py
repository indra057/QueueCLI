import os
from flask import Flask, jsonify, render_template
from .database import Storage
from .worker_manager import WorkerManager

# Find the database, assuming it's in the parent directory
QUEUECTL_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB_PATH = os.path.join(QUEUECTL_ROOT, "queuectl.db")

app = Flask(__name__)

# --- Helper Functions ---
def get_storage():
    return Storage(db_path=DB_PATH)

def get_worker_manager():
    return WorkerManager(db_path=DB_PATH)

# --- Web Page Route ---
@app.route("/")
def serve_dashboard():
    # Serves the index.html file from the 'templates' folder
    return render_template("index.html")

# --- API Route (for data) ---
@app.route("/api/status")
def get_status_api():
    """
    This is the API our dashboard will call to get live data.
    """
    try:
        storage = get_storage()
        job_data = storage.get_dashboard_data()

        manager = get_worker_manager()
        worker_processes = manager.get_worker_status()

        return jsonify({
            'success': True,
            'jobs': job_data,
            'workers': worker_processes,
            'job_counts': {
                'pending': len(job_data['pending']),
                'processing': len(job_data['processing']),
                'completed': len(job_data['completed']),
                'failed': len(job_data['failed']),
                'dead': len(job_data['dead']),
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == "__main__":
    print(f"Starting QueueCTL Dashboard on http://127.0.0.1:5000")
    print(f"Using database: {DB_PATH}")
    app.run(host="127.0.0.1", port=5000, debug=True)