#!/usr/bin/env python3
"""
Backend startup script that properly sets up the Python path.
"""

import sys
import os
from pathlib import Path

def main():
    # Get the project root directory
    project_root = Path(__file__).parent.resolve()
    backend_dir = project_root / "backend"
    
    # Add project root to Python path so 'backend' module can be imported
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    # Change to backend directory
    os.chdir(backend_dir)
    
    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "9000"))
    reload = os.getenv("RELOAD", "false").lower() == "true"
    
    print(f"Starting AI Video Generator API on {host}:{port}")
    print(f"Project root: {project_root}")
    print(f"Backend directory: {backend_dir}")
    print(f"Working directory: {os.getcwd()}")
    
    # Import uvicorn
    import uvicorn
    
    # Run the app using the backend module path
    uvicorn.run(
        "backend.app:app",  # Use backend.app:app since we're running from project root
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )

if __name__ == "__main__":
    main()
