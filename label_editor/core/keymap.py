#!/usr/bin/env python3

import json
from pathlib import Path
from typing import Dict, List, Any
from gi.repository import Gdk


class KeymapManager:
    """Manages keyboard shortcuts from keymap.json configuration"""
    
    def __init__(self, keymap_file: str = None):
        if keymap_file is None:
            # Default to keymap.json in the project root
            keymap_file = Path(__file__).parent.parent.parent / 'keymap.json'
        
        self.keymap_file = Path(keymap_file)
        
        # Validate that keymap file exists
        if not self.keymap_file.exists():
            raise FileNotFoundError(f"Keymap configuration file not found: {self.keymap_file}")
        
        self.keymap = self.load_keymap()
        self.key_to_action = self._build_key_to_action_map()
    
    def load_keymap(self) -> Dict[str, Any]:
        """Load keymap from JSON file"""
        try:
            if self.keymap_file.exists():
                with open(self.keymap_file, 'r') as f:
                    keymap_data = json.load(f)
                    # Filter out comment keys (starting with //)
                    filtered_keymap = {k: v for k, v in keymap_data.items() if not k.startswith('//')}
                    return filtered_keymap
            else:
                raise FileNotFoundError(f"Keymap file not found: {self.keymap_file}")
        except Exception as e:
            print(f"Error loading keymap: {e}")
            raise
    
    
    def _build_key_to_action_map(self) -> Dict[str, str]:
        """Build reverse mapping from key combinations to actions"""
        key_to_action = {}
        
        for category, actions in self.keymap.items():
            for action, keys in actions.items():
                for key in keys:
                    key_to_action[key] = f"{category}.{action}"
        
        return key_to_action
    
    def get_action_for_key(self, keyval: int, state: int = 0) -> str:
        """Get action for a key press"""
        # Check for modifier keys
        ctrl_pressed = (state & Gdk.ModifierType.CONTROL_MASK) != 0
        
        # Convert keyval to string representation
        key_name = Gdk.keyval_name(keyval)
        
        if ctrl_pressed:
            key_combination = f"Ctrl+{key_name.lower()}"
        else:
            key_combination = key_name
        
        return self.key_to_action.get(key_combination, None)
    
    def get_keys_for_action(self, action: str) -> List[str]:
        """Get key combinations for an action"""
        category, action_name = action.split('.', 1)
        return self.keymap.get(category, {}).get(action_name, [])
    
    def is_navigation_key(self, keyval: int, state: int = 0) -> bool:
        """Check if key is a navigation key"""
        action = self.get_action_for_key(keyval, state)
        return action and action.startswith('navigation.')
    
    def save_keymap(self):
        """Save current keymap to file"""
        try:
            with open(self.keymap_file, 'w') as f:
                json.dump(self.keymap, f, indent=2)
        except Exception as e:
            print(f"Error saving keymap: {e}")