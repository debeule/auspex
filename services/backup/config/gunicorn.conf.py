# One backup at a time; the API refuses a second request while one runs.
workers = 1
worker_class = "gthread"
threads = 2
# The first backup mirrors the whole raw archive.
timeout = 7200
bind = "0.0.0.0:8002"
