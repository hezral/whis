import os
import tomllib
import logging

class ConfigManager:
    def __init__(self):
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config:
            self.config_path = os.path.join(xdg_config, "hyprvoice", "config.toml")
        else:
            # Fallback (though XDG_CONFIG_HOME usually exists in flatpak)
            self.config_path = os.path.expanduser("~/.config/hyprvoice/config.toml")
            
        logging.info(f"Config manager: initializing configuration system...")
        logging.debug(f"ConfigManager initialized with path: {self.config_path}")

    def get_config(self):
        if not os.path.exists(self.config_path):
            return {}
        
        try:
            with open(self.config_path, "rb") as f:
                data = tomllib.load(f) # Changed 'return data' to 'data = tomllib.load(f)' to match user's snippet
                return data
        except Exception as e:
            logging.error(f"Error loading config: {e}")
            return {}

    def save_config(self, updates):
        """
        Updates config with a dictionary of section -> key -> value.
        Example:
        {
            "transcription": {"api_key": "...", "model": "..."},
            "recording": {"timeout": "5m"},
            "notifications": {"enabled": True}
        }
        """
        if not os.path.exists(self.config_path):
            logging.error(f"Config file not found at {self.config_path}, cannot update.")
            return

        try:
            with open(self.config_path, "r") as f:
                lines = f.readlines()

            new_lines = []
            
            current_section = None
            
            # We will consume updates as we go.
            # This is a simple line-based updater that preserves comments.
            # It assumes keys mostly exist. If new keys are needed, this simple parser might miss them if not careful.
            # But the default config has all keys.
            
            for line in lines:
                stripped = line.strip()
                
                # Detect section
                if stripped.startswith("[") and stripped.endswith("]"):
                    current_section = stripped[1:-1]
                    new_lines.append(line)
                    continue
                
                # If we are in a section that has updates
                if current_section and current_section in updates:
                    section_updates = updates[current_section]
                    updated_line = False
                    
                    for key, val in section_updates.items():
                        # robust check for "key ="
                        if stripped.startswith(f"{key} =") or stripped.startswith(f"{key}="):
                            # Formulate new line preserving indentation? 
                            # Basic string formatting for now.
                            # Handle different types
                            if isinstance(val, bool):
                                val_str = "true" if val else "false"
                            elif isinstance(val, (int, float)):
                                val_str = str(val)
                            else:
                                val_str = f'"{val}"'
                                
                            # Try to preserve comments if any (after #)
                            comment = ""
                            if "#" in line:
                                comment = " " + line[line.find("#"):]
                            else:
                                comment = "\n" # add newline
                                
                            new_lines.append(f'{key} = {val_str}{comment}')
                            updated_line = True
                            break
                    
                    if not updated_line:
                        new_lines.append(line)
                else:
                    new_lines.append(line)

            with open(self.config_path, "w") as f:
                f.writelines(new_lines)
                
            logging.info("Config updated successfully.")
            
        except Exception as e:
            logging.error(f"Error saving config: {e}")
