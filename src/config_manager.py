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
            processed_updates = {sec: set() for sec in updates}
            
            for line in lines:
                original_line = line
                stripped = line.strip()
                
                if stripped.startswith("[") and stripped.endswith("]"):
                    # Before switching section, check if we missed any keys in the previous one
                    if current_section in updates:
                        for key, val in updates[current_section].items():
                            if key not in processed_updates[current_section]:
                                val_str = self._format_val(val)
                                new_lines.append(f"{key} = {val_str}\n")
                                processed_updates[current_section].add(key)

                    current_section = stripped[1:-1]
                    new_lines.append(line)
                    continue
                
                updated_line = False
                if current_section and current_section in updates:
                    section_updates = updates[current_section]
                    for key, val in section_updates.items():
                        if stripped.startswith(f"{key} =") or stripped.startswith(f"{key}="):
                            val_str = self._format_val(val)
                            comment = line[line.find("#"):] if "#" in line else "\n"
                            new_lines.append(f"{key} = {val_str}{comment}")
                            processed_updates[current_section].add(key)
                            updated_line = True
                            break
                
                if not updated_line:
                    new_lines.append(line)

            # Check for remaining keys in the last section
            if current_section in updates:
                for key, val in updates[current_section].items():
                    if key not in processed_updates[current_section]:
                        val_str = self._format_val(val)
                        new_lines.append(f"{key} = {val_str}\n")
                        processed_updates[current_section].add(key)

            # Add completely new sections
            for section, section_updates in updates.items():
                if section not in processed_updates or not any(line.strip() == f"[{section}]" for line in lines):
                    if section not in [l.strip()[1:-1] for l in lines if l.strip().startswith("[")]:
                        new_lines.append(f"\n[{section}]\n")
                        for key, val in section_updates.items():
                            val_str = self._format_val(val)
                            new_lines.append(f"  {key} = {val_str}\n")

            with open(self.config_path, "w") as f:
                f.writelines(new_lines)
                
            logging.info("Config updated successfully.")
            
        except Exception as e:
            logging.error(f"Error saving config: {e}")

    def _format_val(self, val):
        if isinstance(val, bool):
            return "true" if val else "false"
        elif isinstance(val, (int, float)):
            return str(val)
        else:
            return f'"{val}"'
