#!/usr/bin/env python3
"""
Modular settings management system with profile support
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from copy import deepcopy


class SettingsManager:
    """Manages application settings with profile support and modular configuration"""
    
    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize settings manager
        
        Args:
            base_dir: Base directory for settings files. If None, uses app directory
        """
        if base_dir is None:
            base_dir = Path(__file__).parent.parent.parent
        
        self.base_dir = Path(base_dir)
        self.settings_dir = self.base_dir / "settings"
        self.settings_dir.mkdir(exist_ok=True)
        
        # File paths
        self.base_settings_file = self.settings_dir / "base.json"
        self.profiles_dir = self.settings_dir / "profiles"
        self.profiles_dir.mkdir(exist_ok=True)
        
        # Current configuration
        self.active_profile: Optional[str] = None
        self.settings: Dict[str, Any] = {}
        self.base_settings: Dict[str, Any] = {}
        
        # Load base settings
        self._load_base_settings()
    
    def _load_base_settings(self):
        """Load base settings that all profiles inherit from"""
        if self.base_settings_file.exists():
            try:
                with open(self.base_settings_file, 'r') as f:
                    self.base_settings = json.load(f)
            except Exception as e:
                print(f"Error loading base settings: {e}")
                self.base_settings = self._get_default_base_settings()
        else:
            self.base_settings = self._get_default_base_settings()
            self._save_base_settings()
    
    def _save_base_settings(self):
        """Save base settings to file"""
        try:
            with open(self.base_settings_file, 'w') as f:
                json.dump(self.base_settings, f, indent=2)
        except Exception as e:
            print(f"Error saving base settings: {e}")
    
    def _get_default_base_settings(self) -> Dict[str, Any]:
        """Get default base settings"""
        return {
            "app": {
                "name": "Label Editor",
                "version": "1.0.0",
                "auto_save_interval": 60,
                "max_recent_files": 10
            },
            "ui": {
                "theme": "default",
                "show_toolbar": True,
                "show_statusbar": True,
                "default_window_width": 1200,
                "default_window_height": 800
            },
            "performance": {
                "max_workers": 10,
                "cache_size_mb": 100,
                "enable_threading": True
            },
            "file_types": {
                "image_extensions": [".jpg", ".jpeg", ".png", ".bmp"],
                "data_extension": ".dat"
            }
        }
    
    def load_profile(self, profile_name: str) -> bool:
        """
        Load a specific profile
        
        Args:
            profile_name: Name of the profile to load
            
        Returns:
            True if successful, False otherwise
        """
        profile_file = self.profiles_dir / f"{profile_name}.json"
        
        if not profile_file.exists():
            print(f"Profile '{profile_name}' not found")
            return False
        
        try:
            with open(profile_file, 'r') as f:
                profile_settings = json.load(f)
            
            # Merge with base settings (profile overrides base)
            self.settings = self._deep_merge(
                deepcopy(self.base_settings), 
                profile_settings
            )
            
            self.active_profile = profile_name
            return True
            
        except Exception as e:
            print(f"Error loading profile '{profile_name}': {e}")
            return False
    
    def save_profile(self, profile_name: str, settings: Optional[Dict[str, Any]] = None) -> bool:
        """
        Save settings to a profile
        
        Args:
            profile_name: Name of the profile
            settings: Settings to save. If None, saves current settings
            
        Returns:
            True if successful, False otherwise
        """
        profile_file = self.profiles_dir / f"{profile_name}.json"
        
        if settings is None:
            settings = self.settings
        
        try:
            # Only save differences from base settings
            profile_settings = self._get_differences(self.base_settings, settings)
            
            with open(profile_file, 'w') as f:
                json.dump(profile_settings, f, indent=2)
            
            return True
            
        except Exception as e:
            print(f"Error saving profile '{profile_name}': {e}")
            return False
    
    def create_profile(self, profile_name: str, base_on: Optional[str] = None) -> bool:
        """
        Create a new profile
        
        Args:
            profile_name: Name of the new profile
            base_on: Optional profile to base the new one on
            
        Returns:
            True if successful, False otherwise
        """
        profile_file = self.profiles_dir / f"{profile_name}.json"
        
        if profile_file.exists():
            print(f"Profile '{profile_name}' already exists")
            return False
        
        if base_on:
            # Copy from existing profile
            base_file = self.profiles_dir / f"{base_on}.json"
            if base_file.exists():
                try:
                    with open(base_file, 'r') as f:
                        settings = json.load(f)
                    return self.save_profile(profile_name, settings)
                except Exception:
                    pass
        
        # Create empty profile (will use base settings)
        return self.save_profile(profile_name, {})
    
    def list_profiles(self) -> List[str]:
        """Get list of available profiles"""
        profiles = []
        for file in self.profiles_dir.glob("*.json"):
            profiles.append(file.stem)
        return sorted(profiles)
    
    def delete_profile(self, profile_name: str) -> bool:
        """Delete a profile"""
        profile_file = self.profiles_dir / f"{profile_name}.json"
        
        if not profile_file.exists():
            return False
        
        try:
            profile_file.unlink()
            if self.active_profile == profile_name:
                self.active_profile = None
                self.settings = deepcopy(self.base_settings)
            return True
        except Exception:
            return False
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get a setting value using dot notation
        
        Args:
            key_path: Dot-separated path to the setting (e.g., "ui.theme")
            default: Default value if key not found
            
        Returns:
            Setting value or default
        """
        keys = key_path.split('.')
        value = self.settings
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def set(self, key_path: str, value: Any) -> bool:
        """
        Set a setting value using dot notation
        
        Args:
            key_path: Dot-separated path to the setting
            value: Value to set
            
        Returns:
            True if successful, False otherwise
        """
        keys = key_path.split('.')
        target = self.settings
        
        # Navigate to the parent of the target key
        for key in keys[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]
        
        # Set the value
        target[keys[-1]] = value
        
        # Save to active profile if one is loaded
        if self.active_profile:
            return self.save_profile(self.active_profile)
        
        return True
    
    def update(self, updates: Dict[str, Any]) -> bool:
        """
        Update multiple settings at once
        
        Args:
            updates: Dictionary of settings to update
            
        Returns:
            True if successful, False otherwise
        """
        self.settings = self._deep_merge(self.settings, updates)
        
        if self.active_profile:
            return self.save_profile(self.active_profile)
        
        return True
    
    def reset_to_base(self):
        """Reset current settings to base settings"""
        self.settings = deepcopy(self.base_settings)
        self.active_profile = None
    
    def export_profile(self, profile_name: str, export_path: Union[str, Path]) -> bool:
        """Export a profile to a file"""
        profile_file = self.profiles_dir / f"{profile_name}.json"
        
        if not profile_file.exists():
            return False
        
        try:
            export_path = Path(export_path)
            with open(profile_file, 'r') as f:
                settings = json.load(f)
            
            # Include metadata
            export_data = {
                "metadata": {
                    "profile_name": profile_name,
                    "exported_from": "Label Editor",
                    "version": self.base_settings.get("app", {}).get("version", "1.0.0")
                },
                "settings": settings
            }
            
            with open(export_path, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            return True
            
        except Exception:
            return False
    
    def import_profile(self, import_path: Union[str, Path], profile_name: Optional[str] = None) -> bool:
        """Import a profile from a file"""
        try:
            import_path = Path(import_path)
            
            with open(import_path, 'r') as f:
                data = json.load(f)
            
            # Handle both direct settings and exported format
            if "settings" in data and "metadata" in data:
                settings = data["settings"]
                if not profile_name:
                    profile_name = data["metadata"].get("profile_name", import_path.stem)
            else:
                settings = data
                if not profile_name:
                    profile_name = import_path.stem
            
            return self.save_profile(profile_name, settings)
            
        except Exception:
            return False
    
    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries"""
        result = deepcopy(base)
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = deepcopy(value)
        
        return result
    
    def _get_differences(self, base: Dict, current: Dict) -> Dict:
        """Get only the differences between base and current settings"""
        diff = {}
        
        for key, value in current.items():
            if key not in base:
                diff[key] = deepcopy(value)
            elif isinstance(value, dict) and isinstance(base.get(key), dict):
                nested_diff = self._get_differences(base[key], value)
                if nested_diff:
                    diff[key] = nested_diff
            elif value != base.get(key):
                diff[key] = deepcopy(value)
        
        return diff
    
    def migrate_from_single_file(self, old_settings_path: Union[str, Path]) -> bool:
        """
        Migrate from old single settings.json to new modular system
        
        Args:
            old_settings_path: Path to old settings.json file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            old_path = Path(old_settings_path)
            if not old_path.exists():
                return False
            
            with open(old_path, 'r') as f:
                old_settings = json.load(f)
            
            # Create default profile with old settings
            profile_settings = {
                "window": {
                    "width": old_settings.get("window_width", 1200),
                    "height": old_settings.get("window_height", 800)
                },
                "default_directory": old_settings.get("default_directory", ""),
                "classes": old_settings.get("classes", {})
            }
            
            # Save as default profile
            self.save_profile("default", profile_settings)
            
            # Keep old file as backup
            backup_path = old_path.with_suffix('.json.bak')
            old_path.rename(backup_path)
            
            return True
            
        except Exception as e:
            print(f"Error migrating settings: {e}")
            return False