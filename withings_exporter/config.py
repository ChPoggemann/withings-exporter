"""Configuration management for Withings Exporter."""

import os
import logging
from pathlib import Path
from typing import Any, Dict
import yaml
from dotenv import load_dotenv


class Config:
    """Configuration manager for Withings Exporter."""

    DEFAULT_CONFIG_DIR = Path.home() / ".withings"
    DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.yaml"
    DEFAULT_ENV_FILE = DEFAULT_CONFIG_DIR / ".env"
    DEFAULT_CREDENTIALS_FILE = DEFAULT_CONFIG_DIR / "credentials.json"
    DEFAULT_DATABASE_PATH = DEFAULT_CONFIG_DIR / "health_data.db"
    DEFAULT_EXPORT_PATH = DEFAULT_CONFIG_DIR / "exports"
    DEFAULT_LOG_PATH = DEFAULT_CONFIG_DIR / "logs"

    def __init__(self, config_path: str = None):
        """Initialize configuration.

        Args:
            config_path: Path to config file. If None, uses default location.
        """
        self.config_path = Path(config_path) if config_path else self.DEFAULT_CONFIG_FILE
        self.config_data: Dict[str, Any] = {}
        self._ensure_directories()
        self._load_env()
        self._load_config()

    def _load_env(self):
        """Load environment variables from .env file."""
        # Try to load from ~/.withings/.env
        if self.DEFAULT_ENV_FILE.exists():
            load_dotenv(self.DEFAULT_ENV_FILE)
        # Also try to load from current directory (for development)
        load_dotenv()

    def _ensure_directories(self):
        """Create necessary directories if they don't exist."""
        self.DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.DEFAULT_EXPORT_PATH.mkdir(parents=True, exist_ok=True)
        self.DEFAULT_LOG_PATH.mkdir(parents=True, exist_ok=True)

    def _load_config(self):
        """Load configuration from file."""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                self.config_data = yaml.safe_load(f) or {}
        else:
            # Use default configuration
            self.config_data = self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            'withings': {
                'client_id': '',
                'client_secret': '',
                'callback_uri': 'http://localhost:8080'
            },
            'sync': {
                'interval': 3600,
                'data_types': {
                    'measurements': True,
                    'activity': True,
                    'sleep': True,
                    'heart_rate': True
                }
            },
            'storage': {
                'database_path': str(self.DEFAULT_DATABASE_PATH),
                'store_raw_data': True
            },
            'export': {
                'export_path': str(self.DEFAULT_EXPORT_PATH),
                'format': {
                    'include_metadata': True,
                    'pretty_print': True
                }
            },
            'logging': {
                'level': 'INFO',
                'log_file': str(self.DEFAULT_LOG_PATH / 'exporter.log'),
                'console': True
            }
        }

    def save(self):
        """Save current configuration to file."""
        with open(self.config_path, 'w') as f:
            yaml.safe_dump(self.config_data, f, default_flow_style=False)

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key.

        Supports nested keys using dot notation (e.g., 'withings.client_id').

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value
        """
        keys = key.split('.')
        value = self.config_data

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default

            if value is None:
                return default

        return value

    def set(self, key: str, value: Any):
        """Set configuration value by key.

        Supports nested keys using dot notation (e.g., 'withings.client_id').

        Args:
            key: Configuration key
            value: Configuration value
        """
        keys = key.split('.')
        data = self.config_data

        for k in keys[:-1]:
            if k not in data:
                data[k] = {}
            data = data[k]

        data[keys[-1]] = value

    @property
    def client_id(self) -> str:
        """Get Withings client ID from environment or config."""
        return os.getenv('WITHINGS_CLIENT_ID') or self.get('withings.client_id', '')

    @property
    def client_secret(self) -> str:
        """Get Withings client secret from environment or config."""
        return os.getenv('WITHINGS_CLIENT_SECRET') or self.get('withings.client_secret', '')

    @property
    def callback_uri(self) -> str:
        """Get OAuth callback URI from environment or config."""
        return os.getenv('WITHINGS_CALLBACK_URI') or self.get('withings.callback_uri', 'http://localhost:8080')

    @property
    def sync_interval(self) -> int:
        """Get sync interval in seconds."""
        return self.get('sync.interval', 3600)

    @property
    def database_path(self) -> Path:
        """Get database file path."""
        path = self.get('storage.database_path', str(self.DEFAULT_DATABASE_PATH))
        return Path(os.path.expanduser(path))

    @property
    def export_path(self) -> Path:
        """Get export directory path."""
        path = self.get('export.export_path', str(self.DEFAULT_EXPORT_PATH))
        return Path(os.path.expanduser(path))

    @property
    def credentials_file(self) -> Path:
        """Get credentials file path."""
        return self.DEFAULT_CREDENTIALS_FILE

    @property
    def log_level(self) -> str:
        """Get logging level."""
        return self.get('logging.level', 'INFO')

    @property
    def log_file(self) -> Path:
        """Get log file path."""
        path = self.get('logging.log_file', str(self.DEFAULT_LOG_PATH / 'exporter.log'))
        return Path(os.path.expanduser(path))

    @property
    def console_logging(self) -> bool:
        """Get console logging flag."""
        return self.get('logging.console', True)

    @property
    def enabled_data_types(self) -> Dict[str, bool]:
        """Get enabled data types."""
        return self.get('sync.data_types', {
            'measurements': True,
            'activity': True,
            'sleep': True,
            'heart_rate': True
        })

    def setup_logging(self):
        """Setup logging based on configuration."""
        log_level = getattr(logging, self.log_level.upper(), logging.INFO)

        # Create log directory if it doesn't exist
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # Configure logging
        handlers = []

        # File handler
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        handlers.append(file_handler)

        # Console handler
        if self.console_logging:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(log_level)
            console_formatter = logging.Formatter('%(levelname)s: %(message)s')
            console_handler.setFormatter(console_formatter)
            handlers.append(console_handler)

        # Configure root logger
        logging.basicConfig(
            level=log_level,
            handlers=handlers
        )


def get_config(config_path: str = None) -> Config:
    """Get configuration instance.

    Args:
        config_path: Optional path to config file

    Returns:
        Config instance
    """
    return Config(config_path)
