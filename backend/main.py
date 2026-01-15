#!/usr/bin/env python3
"""
Main entry point for the ClipForge backend.

This script runs the FastAPI application using the reorganized backend structure.
"""

import sys
import os
from pathlib import Path

def main():
    # Get the current directory (backend directory in container)
    backend_dir = Path(__file__).parent.resolve()
    
    # Add backend directory to Python path so 'backend' module can be imported
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    
    # Set working directory to backend
    os.chdir(backend_dir)
    
    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "9000"))
    reload = os.getenv("RELOAD", "false").lower() == "true"
    
    print(f"Starting ClipForge API on {host}:{port}")
    print(f"Working directory: {os.getcwd()}")
    print(f"Backend directory: {backend_dir}")
    print(f"Using containerized backend structure")
    
    # Import uvicorn
    import uvicorn
    
    # Run the app directly from the backend directory
    uvicorn.run(
        "app:app",  # Direct import since we're in the backend directory
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )

if __name__ == "__main__":
    main()
