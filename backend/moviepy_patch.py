"""
Patch for MoviePy 2.2.1 FFMPEG_AudioReader AttributeError issue.

This fixes the common error:
AttributeError: 'FFMPEG_AudioReader' object has no attribute 'proc'
"""

import warnings
import logging

# Suppress the specific MoviePy cleanup warning
warnings.filterwarnings("ignore", message="Exception ignored in: <function FFMPEG_AudioReader.__del__")

def patch_moviepy_audioreader():
    """
    Patch MoviePy's FFMPEG_AudioReader to prevent AttributeError during cleanup.
    """
    try:
        from moviepy.audio.io.readers import FFMPEG_AudioReader
        
        # Store original __del__ method
        original_del = FFMPEG_AudioReader.__del__
        
        def safe_del(self):
            """Safe destructor that checks for proc attribute before closing."""
            try:
                if hasattr(self, 'proc') and self.proc:
                    self.close()
            except (AttributeError, OSError) as e:
                # Log the error but don't let it propagate during cleanup
                logging.debug(f"MoviePy cleanup warning (safe to ignore): {e}")
        
        # Replace the problematic __del__ method
        FFMPEG_AudioReader.__del__ = safe_del
        
        # Also patch the close method for safety
        original_close = FFMPEG_AudioReader.close
        
        def safe_close(self):
            """Safe close method that checks for proc attribute."""
            try:
                if hasattr(self, 'proc') and self.proc:
                    original_close(self)
            except (AttributeError, OSError) as e:
                logging.debug(f"MoviePy close warning (safe to ignore): {e}")
        
        FFMPEG_AudioReader.close = safe_close
        
        logging.info("MoviePy FFMPEG_AudioReader patch applied successfully")
        
    except ImportError:
        logging.warning("MoviePy not found - patch not applied")
    except Exception as e:
        logging.error(f"Failed to apply MoviePy patch: {e}")


def apply_moviepy_patches():
    """Apply all MoviePy patches."""
    patch_moviepy_audioreader()


# Auto-apply patches when module is imported
if __name__ != "__main__":
    apply_moviepy_patches()
