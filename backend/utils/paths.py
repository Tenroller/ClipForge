"""
Centralized path resolution utilities.

This module provides standardized path resolution and management
functions used throughout the VideoHelper application.
"""

import os
from pathlib import Path
from typing import Optional, Union, List, Dict, Any
try:
    from backend.logging_config import get_logger
except ImportError:
    # Fallback for when running from backend directory
    from logging_config import get_logger

logger = get_logger("path_utils")


class PathManager:
    """Centralized path management system."""

    def __init__(self):
        import os
        
        self.project_root: Path = self._find_project_root()
        self.backend_root: Path = self.project_root / "backend"
        self.frontend_root: Path = self.project_root / "frontend"
        
        # Use environment variables if available, otherwise fall back to project structure
        self.output_root: Path = Path(os.getenv("VIDEOHELPER_OUTPUT_DIR", str(self.project_root / "output")))
        self.temp_root: Path = Path(os.getenv("VIDEOHELPER_TEMP_DIR", str(self.project_root / "temp")))
        self.logs_root: Path = Path(os.getenv("VIDEOHELPER_LOGS_DIR", str(self.project_root / "logs")))

        # Create directories if they don't exist
        self._ensure_directories()

    def _find_project_root(self) -> Path:
        """Find the project root directory."""
        # Start from the current file's directory
        current = Path(__file__).resolve().parent

        # Go up until we find .git directory (most reliable marker)
        for parent in [current] + list(current.parents):
            if (parent / '.git').exists():
                return parent

        # Fallback: look for README.md at project root
        for parent in [current] + list(current.parents):
            if (parent / 'README.md').exists():
                return parent

        # Last resort fallback to current directory's parent (assumes we're in backend/)
        if current.name == 'utils' and current.parent.name == 'backend':
            return current.parent.parent

        return Path.cwd()

    def _ensure_directories(self):
        """Ensure all required directories exist."""
        directories = [
            self.output_root,
            self.temp_root,
            self.logs_root,
            self.temp_root / "videos",
            self.temp_root / "audio",
            self.temp_root / "subtitles",
            self.temp_root / "streaming"
        ]

        for directory in directories:
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.warning(f"Failed to create directory {directory}: {e}")

    def resolve_output_path(self, relative_path: Union[str, Path]) -> Path:
        """
        Resolve a path relative to the output directory.

        Args:
            relative_path: Relative path within output directory

        Returns:
            Absolute path within output directory
        """
        return (self.output_root / relative_path).resolve()

    def resolve_temp_path(self, relative_path: Union[str, Path]) -> Path:
        """
        Resolve a path relative to the temp directory.

        Args:
            relative_path: Relative path within temp directory

        Returns:
            Absolute path within temp directory
        """
        return (self.temp_root / relative_path).resolve()

    def resolve_backend_path(self, relative_path: Union[str, Path]) -> Path:
        """
        Resolve a path relative to the backend directory.

        Args:
            relative_path: Relative path within backend directory

        Returns:
            Absolute path within backend directory
        """
        return (self.backend_root / relative_path).resolve()

    def resolve_frontend_path(self, relative_path: Union[str, Path]) -> Path:
        """
        Resolve a path relative to the frontend directory.

        Args:
            relative_path: Relative path within frontend directory

        Returns:
            Absolute path within frontend directory
        """
        return (self.frontend_root / relative_path).resolve()

    def get_safe_path(self, requested_path: Union[str, Path], base_dir: Path) -> Optional[Path]:
        """
        Get a safe path within the allowed base directory.

        Args:
            requested_path: Requested path
            base_dir: Base directory that the path must be within

        Returns:
            Safe absolute path or None if outside allowed directory
        """
        try:
            path = Path(requested_path).resolve()

            # Check if path is within base directory
            try:
                path.relative_to(base_dir)
                return path
            except ValueError:
                # Path is outside base directory
                logger.warning(f"Unsafe path requested: {requested_path} (outside {base_dir})")
                return None

        except Exception as e:
            logger.error(f"Error resolving safe path {requested_path}: {e}")
            return None

    def is_path_allowed(self, path: Union[str, Path], allowed_dirs: List[Path]) -> bool:
        """
        Check if a path is within any of the allowed directories.

        Args:
            path: Path to check
            allowed_dirs: List of allowed base directories

        Returns:
            True if path is within any allowed directory
        """
        try:
            resolved_path = Path(path).resolve()

            for allowed_dir in allowed_dirs:
                try:
                    resolved_path.relative_to(allowed_dir)
                    return True
                except ValueError:
                    continue

            return False

        except Exception:
            return False

    def get_temp_file_path(self, prefix: str = "tmp", suffix: str = "", subdir: str = "") -> Path:
        """
        Generate a unique temporary file path.

        Args:
            prefix: File prefix
            suffix: File suffix (e.g., ".mp4")
            subdir: Subdirectory within temp directory

        Returns:
            Unique temporary file path
        """
        import uuid
        import time

        timestamp = int(time.time())
        unique_id = uuid.uuid4().hex[:8]

        filename = f"{prefix}_{timestamp}_{unique_id}{suffix}"

        if subdir:
            temp_dir = self.temp_root / subdir
            temp_dir.mkdir(parents=True, exist_ok=True)
            return temp_dir / filename
        else:
            return self.temp_root / filename

    def cleanup_old_files(self, directory: Path, max_age_hours: int = 24) -> int:
        """
        Clean up old files in a directory.

        Args:
            directory: Directory to clean
            max_age_hours: Maximum age of files to keep (hours)

        Returns:
            Number of files removed
        """
        import time

        if not directory.exists():
            return 0

        cutoff_time = time.time() - (max_age_hours * 3600)
        removed_count = 0

        try:
            for file_path in directory.rglob("*"):
                if file_path.is_file():
                    try:
                        if file_path.stat().st_mtime < cutoff_time:
                            file_path.unlink()
                            removed_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to remove old file {file_path}: {e}")

        except Exception as e:
            logger.error(f"Error cleaning directory {directory}: {e}")

        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} old files in {directory}")

        return removed_count

    def get_directory_stats(self, directory: Path) -> Dict[str, Any]:
        """
        Get statistics about a directory.

        Args:
            directory: Directory to analyze

        Returns:
            Dictionary with directory statistics
        """
        if not directory.exists():
            return {
                'exists': False,
                'path': str(directory),
                'file_count': 0,
                'total_size_bytes': 0,
                'total_size_mb': 0
            }

        try:
            files = list(directory.rglob("*"))
            file_paths = [f for f in files if f.is_file()]

            total_size = sum(f.stat().st_size for f in file_paths if f.exists())

            return {
                'exists': True,
                'path': str(directory),
                'file_count': len(file_paths),
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2)
            }

        except Exception as e:
            return {
                'exists': True,
                'path': str(directory),
                'error': str(e)
            }

    def get_project_info(self) -> Dict[str, Any]:
        """
        Get information about the project structure.

        Returns:
            Dictionary with project information
        """
        return {
            'project_root': str(self.project_root),
            'backend_root': str(self.backend_root),
            'frontend_root': str(self.frontend_root),
            'output_root': str(self.output_root),
            'temp_root': str(self.temp_root),
            'logs_root': str(self.logs_root),
            'directories_exist': {
                'backend': self.backend_root.exists(),
                'frontend': self.frontend_root.exists(),
                'output': self.output_root.exists(),
                'temp': self.temp_root.exists(),
                'logs': self.logs_root.exists()
            }
        }


# Global path manager instance
_path_manager: Optional[PathManager] = None


def get_path_manager() -> PathManager:
    """Get or create the global path manager."""
    global _path_manager
    if _path_manager is None:
        _path_manager = PathManager()
    return _path_manager


def init_path_manager():
    """Initialize the path manager."""
    manager = get_path_manager()
    logger.info(f"Path manager initialized for project: {manager.project_root}")


# Convenience functions for common operations
def get_project_root() -> Path:
    """Get the project root directory."""
    return get_path_manager().project_root


def get_output_path(relative_path: Union[str, Path] = "") -> Path:
    """Get path within output directory."""
    if relative_path:
        return get_path_manager().resolve_output_path(relative_path)
    return get_path_manager().output_root


def get_temp_path(relative_path: Union[str, Path] = "") -> Path:
    """Get path within temp directory."""
    if relative_path:
        return get_path_manager().resolve_temp_path(relative_path)
    return get_path_manager().temp_root


def get_backend_path(relative_path: Union[str, Path] = "") -> Path:
    """Get path within backend directory."""
    if relative_path:
        return get_path_manager().resolve_backend_path(relative_path)
    return get_path_manager().backend_root


def get_frontend_path(relative_path: Union[str, Path] = "") -> Path:
    """Get path within frontend directory."""
    if relative_path:
        return get_path_manager().resolve_frontend_path(relative_path)
    return get_path_manager().frontend_root


def is_safe_path(path: Union[str, Path]) -> bool:
    """
    Check if a path is within allowed directories.

    Args:
        path: Path to check

    Returns:
        True if path is within allowed directories
    """
    manager = get_path_manager()
    allowed_dirs = [
        manager.output_root,
        manager.temp_root,
        manager.backend_root / "debug_frames"
    ]

    return manager.is_path_allowed(path, allowed_dirs)


def get_temp_file(prefix: str = "tmp", suffix: str = "", subdir: str = "") -> Path:
    """Generate a unique temporary file path."""
    return get_path_manager().get_temp_file_path(prefix, suffix, subdir)


def pushd(path: Path):
    """
    Context manager to temporarily change working directory.

    Args:
        path: Directory to change to
    """
    import contextlib
    import os

    @contextlib.contextmanager
    def _pushd():
        prev = Path.cwd()
        os.chdir(path)
        try:
            yield
        finally:
            os.chdir(prev)

    return _pushd()


# Initialize path manager when module is imported
try:
    init_path_manager()
except Exception as e:
    logger.error(f"Failed to initialize path system: {e}")
