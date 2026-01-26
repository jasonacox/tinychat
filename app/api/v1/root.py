"""Root route for serving the chat UI."""

import logging
import os

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

logger = logging.getLogger("tinychat")

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def get_chat_ui():
    """
    Serve the main chat user interface. Tries known locations and fails gracefully
    with a helpful HTML message if the static files are missing.

    Returns:
        HTMLResponse: The rendered HTML page or a friendly error page
    """
    possible_paths = ["static/index.html", "app/static/index.html"]

    for path in possible_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return HTMLResponse(f.read())
            except FileNotFoundError:
                # Race condition, try next candidate
                logger.error(f"Static file briefly missing when trying to open {path}")
                continue
            except Exception as e:
                logger.error(f"Error reading static file {path}: {e}")
                break

    # If we reach here, no static index file was available
    logger.error("Static index.html not found in any expected location; returning friendly error page.")
    error_html = """
    <html>
      <head><title>TinyChat - Missing Static Files</title></head>
      <body style="font-family: Arial, sans-serif; padding: 2rem;">
        <h1 style="color:#d9534f">TinyChat: Static files missing</h1>
        <p>The server could not find <code>index.html</code> in either <code>static/</code> or <code>app/static/</code>.</p>
        <p>If you are running locally, ensure you are in the project root and that the repository is intact. For development mode, run <code>./local.sh dev</code>.</p>
        <p>If this service is running inside a container, rebuild or re-deploy the image so the static assets are included.</p>
      </body>
    </html>
    """
    return HTMLResponse(error_html, status_code=500)
