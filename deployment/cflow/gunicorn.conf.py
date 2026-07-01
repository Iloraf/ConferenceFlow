# gunicorn configuration goes here
bind = "0.0.0.0:8080"  # do not change me
workers = 4
worker_class = "gthread"
threads = 4
timeout = 1200
accesslog = "-"
errorlog = "-"
loglevel = "info"
