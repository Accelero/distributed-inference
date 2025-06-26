import logging
import sys

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    fmt="%(asctime)s.%(msecs)03d %(levelname)-8s %(name)-20s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z"  # ISO 8601 format
)
handler.setFormatter(formatter)
logger.handlers = [handler]  # Replace any default handlers