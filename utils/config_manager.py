import json
import os
from typing import Dict, Any, Optional

class ConfigManager:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self.load()

    def load(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
        else:
            self.config = {}

    def save(self):
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4)

    def set_guild_config(self, guild_id: int, channel_id: int, role_id: int, max_attempts: int):
        self.config[str(guild_id)] = {
            "verify_channel_id": channel_id,
            "verified_role_id": role_id,
            "max_attempts": max_attempts
        }
        self.save()

    def get_guild_config(self, guild_id: int) -> Optional[Dict[str, Any]]:
        return self.config.get(str(guild_id))
