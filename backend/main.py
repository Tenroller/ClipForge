#!/usr/bin/env python3
"""
Main entry point for the AI Video Generator backend.

This script runs the FastAPI application using the reorganized backend structure.
"""

import sys
import os
from pathlib import Path

def main():
    # Get the backend directory (where this script is located)
    backend_dir = Path(__file__).parent.resolve()
    project_root = backend_dir.parent
    
    # Change working directory to project root
    os.chdir(project_root)
    
    # Add project root to Python path
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    reload = os.getenv("RELOAD", "false").lower() == "true"
    
    print(f"🚀 Starting AI Video Generator API on {host}:{port}")
    print(f"📁 Working directory: {os.getcwd()}")
    print(f"🐍 Python path includes: {project_root}")
    print(f"🔧 Using reorganized backend structure")
    
    # Import uvicorn
    import uvicorn
    
    # Run the reorganized app
    uvicorn.run(
        "backend.app:app",  # Now using the clean reorganized structure
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )

if __name__ == "__main__":
    main()
