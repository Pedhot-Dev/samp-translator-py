
import time
import threading
from evdev import UInput, ecodes as e

class TranslatorCore:
    def __init__(self, config, cache, clipboard, openai_client):
        self.config = config
        self.cache = cache
        self.clipboard = clipboard
        self.openai = openai_client
        self.uinput = None
        self.style = config.get("style", "strict")
        
        # Determine prompt file path
        self.prompt_path = config.get("prompt_file", "prompt.txt")
        self.prompt_template = self._load_prompt()

        try:
            self.uinput = UInput()
        except Exception as ex:
            print(f"Warning: Could not create UInput device ({ex}). Key injection (Ctrl+C/V) will fail unless running as root/input group.")

    def _load_prompt(self):
        try:
            with open(self.prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            return "Translate the following text to English (Style: {style}):"

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
        translatable_text = original_text
        mode_context = "DIALOGUE" # Default mode

        # Check if first token is a command (starts with / followed by letters)
        # e.g. /me, /do, /low, /Radio
        first_space = original_text.find(" ")
        if first_space != -1:
            potential_cmd = original_text[:first_space]
            if potential_cmd.startswith("/") and len(potential_cmd) > 1 and potential_cmd[1].isalpha():
                command_token = potential_cmd
                translatable_text = original_text[first_space+1:].strip()
                
                # Determine Context for AI (Strictly Rules)
                slash_cmd = command_token.lower()
                if slash_cmd in ["/me", "/lme"]:
                    mode_context = "ACTION (User is performing an action. Use 3rd person present tense, e.g. 'runs', 'points')."
                elif slash_cmd in ["/do", "/ldo"]:
                    mode_context = "DESCRIPTION (User is describing the environment/state. Use descriptive/passive English)."
                else:
                    mode_context = f"DIALOGUE (User is speaking with command {command_token})."
        
        if not translatable_text:
            # Nothing to translate
            return

        # === STAGE 2: TRANSLATION ===
        # We perform translation on the stripped text ONLY.
        # But we inject the 'mode_context' into the style to guide neutral grammar.
        
        # 3. Check Cache (Cache key must include mode to be unique but NOT the command token itself if we want reusability, 
        # actually command token matters for mode. Let's cache based on (translatable_text, style, mode_context))
        cache_key_extra = f"{self.style}::{mode_context}"
        
        cached = self.cache.get(translatable_text, cache_key_extra)
        if cached:
            print("Cache hit!")
            translated_body = cached
        else:
            # 4. Translate via OpenAI
            # Determine Style override for RP commands
            # RP commands must ALWAYS be strict, covering the user's requirement.
            effective_style = self.style
            if slash_cmd in ["/me", "/lme", "/do", "/ldo"]:
                effective_style = "strict"

            # Inject context into the style variable passed to prompt template
            # This ensures the AI sees the rule without seeing the token
            augmented_style = f"{effective_style}\n[SYSTEM CONTEXT]: {mode_context}"
            
            # Update cache key to include the EFFECTIVE style, not just the global style
            # This ensures strict RP translations are cached separately or correctly
            cache_key_extra = f"{effective_style}::{mode_context}"
            
            # Check cache again with specific key if needed, or just rely on the flow
            # (Simplification: We checked cache above with self.style. If we switch to strict, we should check cache with strict.)
            # Let's do a quick re-check for cache if style changed
            if effective_style != self.style:
                 cached_strict = self.cache.get(translatable_text, cache_key_extra)
                 if cached_strict:
                     print("Cache hit (Strict RP)!")
                     translated_body = cached_strict
                     # Skip API call
                     final_text = f"{command_token} {translated_body}"
                     self.clipboard.set_text(final_text)
                     time.sleep(0.1)
                     self._sim_key_combo("ctrl", "v")
                     print("Done.")
                     return

            translated_body = self.openai.translate_text(
                translatable_text, 
                self.prompt_template, 
                augmented_style
            )
            
            # Cache the BODY (without command)
            if translated_body != translatable_text:
                self.cache.set(translatable_text, cache_key_extra, translated_body)
                self.cache.log(original_text, translated_body, effective_style)

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
