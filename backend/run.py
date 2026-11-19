import os
import tempfile
os.environ.setdefault("MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "safeher_mpl"))
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

import uvicorn
from dotenv import load_dotenv
load_dotenv()
from app.core.config import settings
from app.main import socket_app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    is_debug = bool(settings.DEBUG)
    uvicorn.run(
        "run:socket_app",
        host="0.0.0.0",
        port=port,
        reload=is_debug,
        log_level="info",
        workers=1,
        limit_concurrency=100,
        timeout_keep_alive=15,
        backlog=128,
    )
