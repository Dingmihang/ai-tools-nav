import os

bind = f"0.0.0.0:{os.getenv('PORT', '8080')}"
workers = 4
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = "info"
