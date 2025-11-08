"""Configuration management for queuectl."""

import json
import os
from typing import Dict, Any
from pathlib import Path


class Config:
    """Configuration manager with file-based persistence."""
    
    DEFAULT_CONFIG = {
        "max_retries": 3,
        "backoff_base": 2,
        "worker_poll_interval": 1.0,
        "db_path": "queuectl.db"
    }
    
    def __init__(self, config_path: str = "queuectl_config.json"):
        """Initialize configuration."""
        self.config_path = Path(config_path)
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or return defaults."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    merged = self.DEFAULT_CONFIG.copy()
                    merged.update(config)
                    return merged
            except (json.JSONDecodeError, IOError):
                return self.DEFAULT_CONFIG.copy()
        return self.DEFAULT_CONFIG.copy()
    
    def _save_config(self):
        """Save configuration to file."""
        with open(self.config_path, 'w') as f:
            json.dump(self._config, f, indent=2)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set a configuration value."""
        if key in self.DEFAULT_CONFIG:
            self._config[key] = value
            self._save_config()
        else:
            raise ValueError(f"Unknown configuration key: {key}")
    
    def get_all(self) -> Dict[str, Any]:
        """Get all configuration values."""
        return self._config.copy()

