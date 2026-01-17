import time
import threading
import os
from evdev import UInput, ecodes as e

class TranslatorCore:
    def __init__(self, config, cache, clipboard, openai_client):
        self.config = config
        self.cache = cache
        self.clipboard = clipboard
        self.openai = openai_client
        self.uinput = None
        self.style = config.get("style", "strict")
        
        # Determine prompt file paths
        app_dir = os.path.dirname(os.path.abspath(__file__))
        # Assuming prompt files are in the parent directory or same logical root
        # If running from main.py, they are in CWD or near config
        # Use simple relative pathing or config based lookup.
        self.prompt_action_path = "action-desc-prompt.txt"
        self.prompt_dialog_path = "dialog-prompt.txt"
        
        self.prompt_action = self._load_file(self.prompt_action_path)
        self.prompt_dialog = self._load_file(self.prompt_dialog_path)

        try:
            self.uinput = UInput()
        except Exception as ex:
            print(f"Warning: Could not create UInput device ({ex}). Key injection (Ctrl+C/V) will fail unless running as root/input group.")

    def _load_file(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            print(f"Warning: Could not load {path}. Using fallback.")
            return "Translate to English (Style: {style})"

    def _sim_key_combo(self, modifier, key):
        """Simulates a key combination (e.g. Ctrl+C)."""
        if not self.uinput:
            print("Error: UInput not initialized. Cannot simulate keys.")
            return

        # Press Modifier
        if modifier == "ctrl":
            self.uinput.write(e.EV_KEY, e.KEY_LEFTCTRL, 1)
        
        # Press Key
        if key == "c":
            self.uinput.write(e.EV_KEY, e.KEY_C, 1)
        elif key == "v":
            self.uinput.write(e.EV_KEY, e.KEY_V, 1)
            
        self.uinput.syn()
        time.sleep(0.05)
        
        # Release Key
        if key == "c":
            self.uinput.write(e.EV_KEY, e.KEY_C, 0)
        elif key == "v":
            self.uinput.write(e.EV_KEY, e.KEY_V, 0)
            
        # Release Modifier
        if modifier == "ctrl":
            self.uinput.write(e.EV_KEY, e.KEY_LEFTCTRL, 0)
            
        self.uinput.syn()

    def process_selection(self):
        """Main workflow: Copy -> Parse -> Translate -> Paste"""
        print("Processing selection...")
        
        # 1. Simulate Copy (Ctrl+C)
        self._sim_key_combo("ctrl", "c")
        time.sleep(0.1) 
        
        # 2. Get Text
        original_text = self.clipboard.get_text()
        if not original_text:
            print("No text in clipboard.")
            return

        print(f"Original: {original_text[:50]}...")
        
        # === STAGE 1: COMMAND PARSING ===
        command_token = ""
        slash_cmd = ""
        translatable_text = original_text
        
        # Check if first token is a command (starts with / followed by letters)
        first_space = original_text.find(" ")
        if first_space != -1:
            potential_cmd = original_text[:first_space]
            if potential_cmd.startswith("/") and len(potential_cmd) > 1 and potential_cmd[1].isalpha():
                command_token = potential_cmd
                slash_cmd = command_token.lower()
                translatable_text = original_text[first_space+1:].strip()
        
        if not translatable_text:
            # Nothing to translate
            return

        # === STAGE 2: TRANSLATION ===
        # Select Prompt based on Method (Routing)
        if slash_cmd in ["/me", "/lme", "/do", "/ldo"]:
            prompt_template = self.prompt_action
        else:
            prompt_template = self.prompt_dialog

        # 3. Check Cache
        # Cache key must include style AND command type (action vs dialog) to be unique
        # We can just use the prompt_template content hash or a simple ID
        prompt_type = "action" if prompt_template == self.prompt_action else "dialog"
        cache_key_extra = f"{self.style}::{prompt_type}"
        
        cached = self.cache.get(translatable_text, cache_key_extra)
        if cached:
            print("Cache hit!")
            translated_body = cached
        else:
            # 4. Translate via OpenAI
            print(f"Requesting translation (Type: {prompt_type})...")
            
            translated_body = self.openai.translate_text(
                translatable_text, 
                prompt_template, 
                self.style
            )
            
            # Cache the BODY (without command)
            if translated_body != translatable_text:
                self.cache.set(translatable_text, cache_key_extra, translated_body)
                self.cache.log(original_text, translated_body, self.style)

        # === FINAL OUTPUT ASSEMBLY ===
        if command_token:
            final_text = f"{command_token} {translated_body}"
        else:
            final_text = translated_body

        # 5. Set Clipboard
        self.clipboard.set_text(final_text)
        time.sleep(0.1)
        
        # 6. Simulate Paste (Ctrl+V)
        self._sim_key_combo("ctrl", "v")
        print("Done.")

    def close(self):
        if self.uinput:
            self.uinput.close()
