# dev_uvicorn.py
import subprocess
import sys
import os
from dotenv import load_dotenv

load_dotenv()  # Load PYTHONPATH from .env
sys.path.insert(0, os.getcwd())  # Add current working directory to sys.path

try:
    from fastapi_service.app.main import app
except ModuleNotFoundError as e:
    missing_module = str(e).split("'")[1]
    print(f"[!] Missing module: {missing_module}. Installing with Poetry...")
    subprocess.run(["poetry", "add", missing_module])
    from fastapi_service.app.main import app

import uvicorn

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)
