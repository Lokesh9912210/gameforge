"""Start GameForge and open it in your browser."""
import os
import threading
import webbrowser

import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    uvicorn.run("app:app", host="127.0.0.1", port=port)
