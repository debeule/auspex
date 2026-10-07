# One process: prometheus_client keeps metrics per process, so several workers would each
# expose a partial count and /metrics would jump between them. Runs are I/O bound
# (HTTP fetch, LLM call), so threads give the concurrency.
workers = 1
worker_class = "gthread"
threads = 8
timeout = 3600
bind = "0.0.0.0:8000"
