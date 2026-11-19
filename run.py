import os
import sys
import tempfile

# Ensure backend directory is in sys.path and is the working directory
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
os.chdir(backend_dir)

os.environ.setdefault("MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "safeher_mpl"))
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_dir, ".env"))
from app.core.config import settings
from app.main import socket_app

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", settings.PORT if hasattr(settings, "PORT") else 8000))
    is_debug = bool(settings.DEBUG)
    uvicorn.run(
        "app.main:socket_app",
        host="0.0.0.0",
        port=port,
        reload=is_debug,
        log_level="info",
        workers=1,
        limit_concurrency=100,
        timeout_keep_alive=15,
        backlog=128,
    )
