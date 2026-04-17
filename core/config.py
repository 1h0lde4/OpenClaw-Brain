"""
core/config.py — Single access point for all TOML config files.
Hot-reloads on file change. No restart needed for most settings.
"""
import sys
import threading
import time
from pathlib import Path
from typing import Any, Optional

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

import tomli_w

CONFIG_DIR = Path(__file__).parent.parent / "config"

class Config:
    def __init__(self):
        self._lock = threading.RLock()
        self._settings: dict = {}
        self._sources: dict = {}
        self._models: dict = {}
        self._load_all()
        self._start_watcher()

    def _load_all(self):
        with self._lock:
            self._settings = self._read(CONFIG_DIR / "settings.toml")
            self._sources  = self._read(CONFIG_DIR / "sources.toml")
            self._models   = self._read(CONFIG_DIR / "models.toml")

    def _read(self, path: Path) -> dict:
        if not path.exists():
            return {}
        with open(path, "rb") as f:
            return tomllib.load(f)

    def _start_watcher(self):
        def _watch():
            mtimes = {}
            files = [
                CONFIG_DIR / "settings.toml",
                CONFIG_DIR / "sources.toml",
                CONFIG_DIR / "models.toml",
            ]
            while True:
                for f in files:
                    try:
                        mt = f.stat().st_mtime
                        if mtimes.get(str(f)) != mt:
                            mtimes[str(f)] = mt
                            self._load_all()
                    except FileNotFoundError:
                        pass
                time.sleep(2)

        t = threading.Thread(target=_watch, daemon=True)
        t.start()

    def get(self, key: str, default: Any = None) -> Any:
        """Dot-path access: config.get('global.ollama_host')"""
        with self._lock:
            parts = key.split(".")
            obj = self._settings
            for p in parts:
                if not isinstance(obj, dict):
                    return default
                obj = obj.get(p)
                if obj is None:
                    return default
            return obj

    def set(self, key: str, value: Any):
        """Write a value back to settings.toml."""
        with self._lock:
            parts = key.split(".")
            obj = self._settings
            for p in parts[:-1]:
                obj = obj.setdefault(p, {})
            obj[parts[-1]] = value
            path = CONFIG_DIR / "settings.toml"
            with open(path, "wb") as f:
                tomli_w.dump(self._settings, f)

    def get_sources(self, module_name: str) -> list[str]:
        with self._lock:
            return self._sources.get(module_name, {}).get("sources", [])

    def get_module_state(self, module_name: str) -> dict:
        with self._lock:
            return dict(self._models.get(module_name, {}))

    def set_module_state(self, module_name: str, key: str, value: Any):
        with self._lock:
            if module_name not in self._models:
                self._models[module_name] = {}
            self._models[module_name][key] = value
            path = CONFIG_DIR / "models.toml"
            with open(path, "wb") as f:
                tomli_w.dump(self._models, f)

    def get_module_keywords(self, module_name: str) -> list[str]:
        with self._lock:
            return self._settings.get("modules", {}).get(
                module_name, {}
            ).get("keywords", [])

    def all_module_names(self) -> list[str]:
        with self._lock:
            return list(self._models.keys())

    def register_module(self, name: str, model: str, keywords: list[str], sources: list[str]):
        """Called by module_factory after scaffolding a new module."""
        with self._lock:
            # models.toml
            self._models[name] = {
                "stage": "bootstrap", "maturity_score": 0.0,
                "query_count": 0, "bootstrap_model": model,
                "base_model": "mistral:7b", "active_weights": "",
                "last_trained": "", "train_pairs": 0,
            }
            path = CONFIG_DIR / "models.toml"
            with open(path, "wb") as f:
                tomli_w.dump(self._models, f)

            # settings.toml — add module block
            self._settings.setdefault("modules", {})[name] = {
                "enabled": True, "keywords": keywords,
                "staleness_decay": True, "max_kb_size_mb": 500,
                "confidence_boost": 0.1, "pin_to_external": False,
            }
            spath = CONFIG_DIR / "settings.toml"
            with open(spath, "wb") as f:
                tomli_w.dump(self._settings, f)

            # sources.toml
            self._sources[name] = {"sources": sources}
            srpath = CONFIG_DIR / "sources.toml"
            with open(srpath, "wb") as f:
                tomli_w.dump(self._sources, f)


# Global singleton
config = Config()
