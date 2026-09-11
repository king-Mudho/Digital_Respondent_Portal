"""Gunicorn configuration for the DRP Django API.

Sized more conservatively than the sibling ABI project's own gunicorn
config: this VPS now runs TWO full application stacks on ~956MB RAM
(docs/27_AGENT_EXECUTION_PLAN.md Phase 10 flagged this explicitly). One
worker, two threads -- DRP's traffic (invitation-only respondent flow plus
internal Research Operations Centre) is materially lower than ABI's public
demo. Raise GUNICORN_WORKERS if the server is resized or contention proves
not to be a problem in practice.
"""

import os

# Bind to loopback only, on a different port from ABI's :8000 so both
# apps' upstreams can never collide.
bind = "127.0.0.1:8100"

workers = int(os.environ.get("GUNICORN_WORKERS", 1))
threads = int(os.environ.get("GUNICORN_THREADS", 4))
worker_class = "gthread"

timeout = 90
graceful_timeout = 30
keepalive = 5

max_requests = 1000
max_requests_jitter = 100

accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
access_log_format = '%({x-forwarded-for}i)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" %(D)sus'
