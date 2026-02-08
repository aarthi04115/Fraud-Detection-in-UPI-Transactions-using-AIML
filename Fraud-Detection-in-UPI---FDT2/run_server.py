#!/usr/bin/env python
import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

# Import and run uvicorn
import uvicorn

if __name__ == "__main__":
    from main import app
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
