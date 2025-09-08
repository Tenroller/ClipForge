#!/usr/bin/env python3
"""
Logging Configuration for TikYou Video Generator

This module provides centralized logging configuration with different levels,
formatters, and handlers for various components of the video generation system.
"""

import logging
import logging.handlers
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from enum import Enum

# Fix Unicode encoding issues on Windows
if sys.platform == 'win32':
    # Set environment variable for UTF-8 encoding
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    # Try to set console code page to UTF-8
    try:
        import subprocess
        subprocess.run(['chcp', '65001'], shell=True, capture_output=True)
    except Exception:
        pass


class LogLevel(Enum):
    """Enumeration of log levels"""
    CRITICAL = logging.CRITICAL
    ERROR = logging.ERROR
    WARNING = logging.WARNING
    INFO = logging.INFO
    DEBUG = logging.DEBUG


class UnicodeStreamHandler(logging.StreamHandler):
    """Unicode-safe stream handler for Windows compatibility"""
    
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            stream.write(msg + self.terminator)
            self.flush()
        except UnicodeEncodeError:
            # Fallback: remove emojis and try again
            try:
                # Try to encode as ASCII, removing problematic characters
                safe_msg = record.msg.encode('ascii', 'ignore').decode('ascii')
                record.msg = safe_msg
                msg = self.format(record)
                stream.write(msg + self.terminator)
                self.flush()
            except Exception:
                # If that still fails, just write a basic message
                try:
                    basic_msg = f"[{record.levelname}] {record.name}: {record.msg}\n"
                    stream.write(basic_msg)
                    self.flush()
                except Exception:
                    pass
        except Exception:
            self.handleError(record)


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors and emojis for console output"""
    
    # Color codes
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'       # Reset
    }
    
    # Emoji mapping
    EMOJIS = {
        'DEBUG': '🔍',
        'INFO': '📝',
        'WARNING': '⚠️',
        'ERROR': '❌',
        'CRITICAL': '🚨'
    }
    
    def format(self, record):
        # Add color and emoji
        level_name = record.levelname
        colored_level = f"{self.COLORS.get(level_name, '')}{level_name}{self.COLORS['RESET']}"
        emoji = self.EMOJIS.get(level_name, '')
        
        # Create custom record
        record.colored_levelname = colored_level
        record.emoji = emoji
        
        return super().format(record)


class TikYouLogger:
    """Main logger class for TikYou Video Generator"""
    
    def __init__(self, name: str = "TikYou", log_level: LogLevel = LogLevel.INFO,
                 log_file: Optional[str] = None, console_output: bool = True):
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.propagate = False
        self.logger.setLevel(log_level.value)
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Setup handlers
        if console_output:
            self._setup_console_handler()
        
        if log_file:
            self._setup_file_handler(log_file)
        
        # Create specialized loggers
        self.video_logger = self._create_specialized_logger("video", "📹")
        self.processing_logger = self._create_specialized_logger("processing", "⚙️")
        self.encoding_logger = self._create_specialized_logger("encoding", "🎬")
        self.memory_logger = self._create_specialized_logger("memory", "💾")
        self.system_logger = self._create_specialized_logger("system", "💻")
        self.progress_logger = self._create_specialized_logger("progress", "📊")
        
    def _setup_console_handler(self):
        """Setup console handler with colored output"""
        # Always use Unicode-safe handler on Windows
        if sys.platform == 'win32':
            console_handler = UnicodeStreamHandler(sys.stdout)
        else:
            console_handler = logging.StreamHandler(sys.stdout)
        
        console_handler.setLevel(logging.DEBUG)
        
        # Custom format for console
        console_format = "{emoji} {colored_levelname} [{name}] {message}"
        console_formatter = ColoredFormatter(console_format, style='{')
        console_handler.setFormatter(console_formatter)
        
        self.logger.addHandler(console_handler)
    
    def _setup_file_handler(self, log_file: str):
        """Setup file handler with detailed logging"""
        # Create log directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Use rotating file handler
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10*1024*1024, backupCount=5  # 10MB per file, 5 backups
        )
        file_handler.setLevel(logging.DEBUG)
        
        # Detailed format for file
        file_format = "{asctime} | {levelname:8} | {name:12} | {funcName:20} | {message}"
        file_formatter = logging.Formatter(file_format, style='{')
        file_handler.setFormatter(file_formatter)
        
        self.logger.addHandler(file_handler)
    
    def _create_specialized_logger(self, category: str, emoji: str) -> logging.LoggerAdapter:
        """Create a specialized logger for a specific category"""
        logger_name = f"{self.name}.{category}"
        specialized_logger = logging.getLogger(logger_name)
        specialized_logger.propagate = False
        
        # Clear any existing handlers to avoid duplicates
        specialized_logger.handlers.clear()
        
        # Always use Unicode-safe handler on Windows, regular handler on other platforms
        if sys.platform == 'win32':
            handler = UnicodeStreamHandler(sys.stdout)
        else:
            handler = logging.StreamHandler(sys.stdout)
        
        handler.setLevel(logging.DEBUG)
        console_format = "{emoji} {colored_levelname} [{name}] {message}"
        console_formatter = ColoredFormatter(console_format, style='{')
        handler.setFormatter(console_formatter)
        specialized_logger.addHandler(handler)
        
        # Create a custom adapter that adds emoji
        class EmojiAdapter(logging.LoggerAdapter):
            def process(self, msg, kwargs):
                return f"{emoji} {msg}", kwargs
        
        return EmojiAdapter(specialized_logger, {})
    
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self.logger.debug(message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message"""
        self.logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self.logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message"""
        self.logger.error(message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message"""
        self.logger.critical(message, **kwargs)
    
    def exception(self, message: str, **kwargs):
        """Log exception with traceback"""
        self.logger.exception(message, **kwargs)
    
    def video_processing(self, message: str, **kwargs):
        """Log video processing message"""
        self.video_logger.info(message, **kwargs)
    
    def processing_step(self, message: str, **kwargs):
        """Log processing step message"""
        self.processing_logger.info(message, **kwargs)
    
    def encoding_info(self, message: str, **kwargs):
        """Log encoding information"""
        self.encoding_logger.info(message, **kwargs)
    
    def memory_usage(self, message: str, **kwargs):
        """Log memory usage information"""
        self.memory_logger.info(message, **kwargs)
    
    def system_info(self, message: str, **kwargs):
        """Log system information"""
        self.system_logger.info(message, **kwargs)
    
    def progress_update(self, message: str, **kwargs):
        """Log progress update"""
        self.progress_logger.info(message, **kwargs)
    
    def log_performance_stats(self, stats: Dict[str, Any]):
        """Log performance statistics"""
        self.info("Performance Statistics:")
        for key, value in stats.items():
            if isinstance(value, float):
                self.info(f"   {key}: {value:.2f}")
            else:
                self.info(f"   {key}: {value}")
    
    def log_system_resources(self, cpu_percent: float, memory_percent: float, 
                           available_memory_gb: float, disk_space_gb: float):
        """Log current system resources"""
        self.system_info(f"System Resources:")
        self.system_info(f"   CPU Usage: {cpu_percent:.1f}%")
        self.system_info(f"   Memory Usage: {memory_percent:.1f}%")
        self.system_info(f"   Available Memory: {available_memory_gb:.1f}GB")
        self.system_info(f"   Available Disk: {disk_space_gb:.1f}GB")
    
    def log_encoding_params(self, params: Dict[str, Any]):
        """Log encoding parameters"""
        self.encoding_info("Encoding Parameters:")
        for key, value in params.items():
            if key != 'ffmpeg_params':  # Skip complex parameters
                self.encoding_info(f"   {key}: {value}")
    
    def log_clip_info(self, clip_path: str, duration: float, orientation: str, 
                     resolution: tuple):
        """Log clip information"""
        self.video_processing(f"Clip: {os.path.basename(clip_path)}")
        self.video_processing(f"   Duration: {duration:.1f}s")
        self.video_processing(f"   Orientation: {orientation}")
        self.video_processing(f"   Resolution: {resolution[0]}x{resolution[1]}")
    
    def log_phase_start(self, phase_name: str, details: str = ""):
        """Log the start of a processing phase"""
        separator = "=" * 50
        self.info(separator)
        self.info(f"PHASE: {phase_name}")
        if details:
            self.info(f"Details: {details}")
        self.info(separator)
    
    def log_phase_end(self, phase_name: str, duration: float, success: bool = True):
        """Log the end of a processing phase"""
        status = "COMPLETED" if success else "FAILED"
        self.info(f"PHASE {status}: {phase_name} (Duration: {duration:.1f}s)")
    
    def log_compilation_summary(self, compilation_num: int, clips_count: int, 
                              total_duration: float, variations: Dict[str, bool]):
        """Log compilation summary"""
        self.info(f"Compilation #{compilation_num} Summary:")
        self.info(f"   Clips used: {clips_count}")
        self.info(f"   Total duration: {total_duration:.1f}s")
        
        successful_variations = []
        failed_variations = []
        
        for variation, success in variations.items():
            if success:
                successful_variations.append(variation)
            else:
                failed_variations.append(variation)
        
        if successful_variations:
            self.info(f"   Successful variations: {', '.join(successful_variations)}")
        if failed_variations:
            self.warning(f"   Failed variations: {', '.join(failed_variations)}")
    
    def log_final_summary(self, total_time: float, successful_compilations: int,
                         failed_compilations: int, total_variations: int,
                         total_size_mb: float):
        """Log final processing summary"""
        separator = "=" * 60
        self.info(separator)
        self.info("🎉 PROCESSING COMPLETE!")
        self.info(separator)
        self.info(f"✅ Successful compilations: {successful_compilations}")
        self.info(f"❌ Failed compilations: {failed_compilations}")
        self.info(f"🎬 Total variations created: {total_variations}")
        self.info(f"📦 Total output size: {total_size_mb:.1f}MB")
        self.info(f"⏱️ Total processing time: {total_time:.1f}s")
        
        if successful_compilations > 0:
            avg_time = total_time / successful_compilations
            avg_size = total_size_mb / successful_compilations
            self.info(f"📈 Average time per compilation: {avg_time:.1f}s")
            self.info(f"📈 Average size per compilation: {avg_size:.1f}MB")
        
        success_rate = (successful_compilations / (successful_compilations + failed_compilations)) * 100 if (successful_compilations + failed_compilations) > 0 else 0
        self.info(f"✅ Success rate: {success_rate:.1f}%")


class LogManager:
    """Manager for multiple loggers across the application"""
    
    def __init__(self, log_level: LogLevel = LogLevel.INFO, 
                 log_directory: str = "logs"):
        self.log_level = log_level
        self.log_directory = Path(log_directory)
        self.log_directory.mkdir(parents=True, exist_ok=True)
        
        # Create timestamp for log files
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Main application logger
        self.main_log_file = self.log_directory / f"tikyou_main_{timestamp}.log"
        self.main_logger = TikYouLogger(
            name="TikYou.Main",
            log_level=log_level,
            log_file=str(self.main_log_file),
            console_output=True
        )
        
        # Performance logger (separate file)
        self.performance_log_file = self.log_directory / f"tikyou_performance_{timestamp}.log"
        self.performance_logger = TikYouLogger(
            name="TikYou.Performance",
            log_level=log_level,
            log_file=str(self.performance_log_file),
            console_output=False
        )
        
        # Error logger (separate file)
        self.error_log_file = self.log_directory / f"tikyou_errors_{timestamp}.log"
        self.error_logger = TikYouLogger(
            name="TikYou.Errors",
            log_level=LogLevel.ERROR,
            log_file=str(self.error_log_file),
            console_output=False
        )
    
    def get_logger(self, component: str = "main") -> TikYouLogger:
        """Get a logger for a specific component"""
        if component == "main":
            return self.main_logger
        elif component == "performance":
            return self.performance_logger
        elif component == "errors":
            return self.error_logger
        else:
            # Create specialized logger
            log_file = self.log_directory / f"tikyou_{component}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            return TikYouLogger(
                name=f"TikYou.{component.title()}",
                log_level=self.log_level,
                log_file=str(log_file),
                console_output=False
            )
    
    def log_startup_info(self, config_info: Dict[str, Any]):
        """Log startup information"""
        self.main_logger.info("🚀 TikYou Video Generator Starting Up")
        self.main_logger.info(f"Log Level: {self.log_level.name}")
        self.main_logger.info(f"Log Directory: {self.log_directory}")
        self.main_logger.info("Configuration:")
        for key, value in config_info.items():
            self.main_logger.info(f"   {key}: {value}")
    
    def cleanup_old_logs(self, max_age_days: int = 7):
        """Clean up old log files"""
        import time
        current_time = time.time()
        
        for log_file in self.log_directory.glob("tikyou_*.log"):
            file_age = current_time - log_file.stat().st_mtime
            if file_age > (max_age_days * 24 * 60 * 60):  # Convert days to seconds
                try:
                    log_file.unlink()
                    self.main_logger.info(f"Cleaned up old log file: {log_file.name}")
                except OSError as e:
                    self.main_logger.warning(f"Failed to cleanup log file {log_file.name}: {e}")


# Global log manager instance
log_manager = LogManager()

# Convenience function to get the main logger
def get_logger() -> TikYouLogger:
    """Get the main application logger"""
    return log_manager.get_logger("main")

# Convenience function to get performance logger
def get_performance_logger() -> TikYouLogger:
    """Get the performance logger"""
    return log_manager.get_logger("performance")

# Convenience function to get error logger
def get_error_logger() -> TikYouLogger:
    """Get the error logger"""
    return log_manager.get_logger("errors") 