import logging
import sys
import json
import os


class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_record["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_record)


# Replace the root logger's handlers and config on import
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)  # Set to DEBUG level

# Log to both stdout and /logs/worker.log if possible
handlers = []
handlers.append(logging.StreamHandler(sys.stdout))

# Determine worker ID for log file naming (use only HOSTNAME)
worker_id = os.environ.get("HOSTNAME")
if worker_id:
    log_path = f"/logs/worker-{worker_id}.log"
else:
    log_path = "/logs/worker.log"
try:
    file_handler = logging.FileHandler(log_path)
    handlers.append(file_handler)
except Exception as e:
    # Fallback: only stdout
    pass

for h in handlers:
    h.setFormatter(JsonFormatter(datefmt="%Y-%m-%dT%H:%M:%S%z"))
root_logger.handlers = handlers  # Replace any default handlers

# Optionally, export the root logger as 'logger' for convenience
logger = root_logger