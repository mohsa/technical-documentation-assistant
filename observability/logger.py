import json
import logging
import time
from pathlib import Path
from typing import Optional
from datetime import datetime
from contextlib import contextmanager

class StructuredLogger:
    """JSON structured logging for observability"""
    
    def __init__(self, name: str, log_file: Optional[Path] = None, level: str = "INFO"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level))
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(self._json_formatter())
        self.logger.addHandler(console_handler)
        
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(self._json_formatter())
            self.logger.addHandler(file_handler)
    
    def _json_formatter(self):
        """Create JSON formatter"""
        class JSONFormatter(logging.Formatter):
            def format(self, record):
                log_data = {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                }
                
                if hasattr(record, "extra"):
                    log_data.update(record.extra)
                
                return json.dumps(log_data)
        
        return JSONFormatter()
    
    def info(self, message: str, **kwargs):
        """Log info with extra fields"""
        extra = {"extra": kwargs} if kwargs else {}
        self.logger.info(message, extra=extra)
    
    def error(self, message: str, **kwargs):
        """Log error with extra fields"""
        extra = {"extra": kwargs} if kwargs else {}
        self.logger.error(message, extra=extra)
    
    def warning(self, message: str, **kwargs):
        """Log warning with extra fields"""
        extra = {"extra": kwargs} if kwargs else {}
        self.logger.warning(message, extra=extra)
    
    @contextmanager
    def operation(self, operation_name: str, **context):
        """Context manager for timing operations"""
        start_time = time.time()
        op_id = f"{operation_name}_{int(start_time * 1000)}"
        
        self.info(
            f"Starting {operation_name}",
            operation=operation_name,
            operation_id=op_id,
            **context
        )
        
        try:
            yield op_id
            duration = time.time() - start_time
            self.info(
                f"Completed {operation_name}",
                operation=operation_name,
                operation_id=op_id,
                duration_seconds=round(duration, 3),
                status="success",
                **context
            )
        except Exception as e:
            duration = time.time() - start_time
            self.error(
                f"Failed {operation_name}",
                operation=operation_name,
                operation_id=op_id,
                duration_seconds=round(duration, 3),
                status="error",
                error_type=type(e).__name__,
                error_message=str(e),
                **context
            )
            raise

logger = StructuredLogger("docs_assistant")