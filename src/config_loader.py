
import yaml
import os
import sys

# Default configuration to fallback on if config.yml is missing or incomplete
DEFAULT_CONFIG = {
    "openai": {
        "api_key": "",
        "model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1"
    },
    "hotkey": "KEY_F9",
    "style": "strict",
    "cache": {
        "enabled": True,
        "db_path": "rp_translator.db"
    },
    "prompt_file": "prompt.txt"
}

def load_config(config_path="config.yml"):
    """
    Loads configuration from a YAML file.
    Returns a dictionary with configuration values, merged with defaults.
    """
    config = DEFAULT_CONFIG.copy()
    
    if not os.path.exists(config_path):
        print(f"Warning: Configuration file '{config_path}' not found. Using defaults.")
        return config

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            user_config = yaml.safe_load(f)
            if user_config:
                # Deep merge for nested keys like 'openai'
                for key, value in user_config.items():
                    if isinstance(value, dict) and key in config and isinstance(config[key], dict):
                        config[key].update(value)
                    else:
                        config[key] = value
    except Exception as e:
        print(f"Error loading config file: {e}")
        # Continue with defaults or partial config
        
    return config

def get_config_value(config, key_path, default=None):
    """
    Helper to get nested config values safely.
    key_path example: "openai.api_key"
    """
    keys = key_path.split('.')
    value = config
    for k in keys:
        if isinstance(value, dict):
            value = value.get(k)
        else:
            return default
    return value if value is not None else default
