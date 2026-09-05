import logging

from assistant.config import settings

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)

# LOG_LEVEL governs this assistant. Left to inherit it, the HTTP stack logs
# every request header at DEBUG, which buries our own lines in wire traffic.
for library in ("httpx", "httpcore", "groq", "urllib3", "asyncio"):
    logging.getLogger(library).setLevel(logging.WARNING)

logger = logging.getLogger("assistant")
