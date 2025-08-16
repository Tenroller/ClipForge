"""
Backend initialization module.
Applies patches and sets up the environment.
"""

# Apply MoviePy patches early
try:
    from .moviepy_patch import apply_moviepy_patches
    apply_moviepy_patches()
except ImportError:
    pass  # Patch not available
