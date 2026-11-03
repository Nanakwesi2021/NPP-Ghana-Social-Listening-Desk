"""Gunicorn configuration for NPP Ghana Social Listening Desk."""
import multiprocessing

# Bind to internal unix socket or localhost
bind = "unix:/run/npp-desk/gunicorn.sock"

# Worker processes (2 * cores + 1)
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "gthread"
threads = 4

# Keep-alive and timeouts
timeout = 30
keepalive = 2

# Logging
accesslog = "/var/log/npp-desk/access.log"
errorlog = "/var/log/npp-desk/error.log"
loglevel = "info"

# Process naming
proc_name = "npp_listening_desk"

