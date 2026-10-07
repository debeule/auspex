# A refresh downloads every ticker's history on a cold start; Yahoo rate limits make that slow.
workers = 1
worker_class = "gthread"
threads = 2
timeout = 1800
bind = "0.0.0.0:8001"
