import logging
import sys
import json
import os


class JsonFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        # Use ISO 8601 UTC with milliseconds, always ending with 'Z'
        from datetime import datetime, timezone

        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        # isoformat(timespec='milliseconds') gives e.g. 2025-06-27T12:34:56.789+00:00
        # Replace +00:00 with Z for strict ISO UTC
        return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")

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

# Log to both stdout and /logs/coordinator.log if possible
handlers = []
handlers.append(logging.StreamHandler(sys.stdout))

log_path = os.environ.get("COORDINATOR_LOG_PATH", "/logs/coordinator.log")
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