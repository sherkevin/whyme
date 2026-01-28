"""Launch the AgentOS server."""

import uvicorn
import webbrowser
import os
import sys
import asyncio

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

# Fix Windows subprocess issue
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

def main():
    # Force use of local sandbox for this demo
    os.environ["AGENTOS_SANDBOX"] = "local"
    
    print("Starting AgentOS Studio...")
    print("Opening browser in 3 seconds...")
    
    # Open browser slightly after start
    import threading
    import time
    def open_browser():
        time.sleep(3)
        webbrowser.open("http://localhost:8003")
    
    threading.Thread(target=open_browser, daemon=True).start()
    
    uvicorn.run(
        "agent_os.server.app:app",
        host="127.0.0.1",
        port=8003,  # Changed to avoid ghost connections on port 8000
        reload=False  # Disabled reload to prevent caching issues
    )

if __name__ == "__main__":
    main()
