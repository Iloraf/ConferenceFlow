# gunicorn configuration goes here
bind = "0.0.0.0:8080"  # do not change me
workers = 3
worker_class = "sync"
timeout = 300
accesslog = "-"
errorlog = "-"
loglevel = "info"
