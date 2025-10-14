# gunicorn_config.py
import multiprocessing
import os

# Server Socket
bind = "0.0.0.0:5001"
backlog = 2048

# Worker Processes
workers = multiprocessing.cpu_count() * 2 + 1  # Recommended formula
worker_class = "sync"  # Use "gevent" for async if needed
worker_connections = 1000
timeout = 120  # Increase if you have long-running requests
keepalive = 2

# Restart workers after this many requests, to help limit memory leaks
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = "-"  # Log to stdout
errorlog = "-"   # Log to stderr
loglevel = "info"  # Can be: debug, info, warning, error, critical
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process Naming
proc_name = "qr_music_chart"

# Server Mechanics
daemon = False  # Set to True if you want to run in background
pidfile = "/tmp/gunicorn_flask_app.pid"
user = None  # Set to a specific user if needed
group = None  # Set to a specific group if needed
tmp_upload_dir = None

# SSL (uncomment if you need HTTPS)
# keyfile = "/path/to/keyfile.key"
# certfile = "/path/to/certfile.crt"

# Server Hooks (optional - useful for debugging)
def when_ready(server):
    server.log.info("Server is ready. Spawning workers")

def worker_int(worker):
    worker.log.info("Worker received INT or QUIT signal")

def pre_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def pre_exec(server):
    server.log.info("Forked child, re-executing.")

def on_exit(server):
    server.log.info("Server is shutting down")

# Preload Application
# This loads your app before forking workers - can save memory but may cause issues with some apps
preload_app = False

# Debugging (set to False in production)
reload = False  # Auto-reload on code changes
reload_engine = "auto"  # Can be: auto, poll, inotify
reload_extra_files = []  # Additional files to watch