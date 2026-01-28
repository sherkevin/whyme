"""Direct server runner without uvicorn reload"""
import uvicorn
if __name__ == "__main__":
    uvicorn.run("agent_os.server.app:app", host="127.0.0.1", port=8002, reload=False, log_level="debug")
