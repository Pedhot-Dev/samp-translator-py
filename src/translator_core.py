
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
        hardcoded = """ABSOLUTE PARSING RULE (HIGHEST PRIORITY)
Before translating:
1. If the input starts with "/" followed by letters:
   - Treat the first token (until first space) as a FIXED COMMAND TOKEN
   - DO NOT translate, replace, infer, or correct it
   - Copy it to output verbatim
2. Translation is applied ONLY to the remaining text after the first space
3. Under NO circumstances may a command token be altered
4. Violating this rule is considered a fatal error

ROLE & CONTEXT
You are an RP Translation Engine, not a conversational AI.
Your ONLY task is to translate text into English while preserving roleplay mechanics.
Translation style is defined by: {style}.
No explanations. No commentary. Output translation only.

"""
        try:
            with open(self.prompt_path, 'r', encoding='utf-8') as f:
                return hardcoded + f.read()
        except Exception:
            return hardcoded + "Translate the following text to English (Style: {style}):"

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
        """Main workflow: Copy -> Translate -> Paste"""
        print("Processing selection...")
        
        # 1. Simulate Copy (Ctrl+C)
        self._sim_key_combo("ctrl", "c")
        time.sleep(0.1) # Wait for clipboard to update
        
        # 2. Get Text
        original_text = self.clipboard.get_text()
        if not original_text:
            print("No text in clipboard.")
            return

        print(f"Original: {original_text[:50]}...")
        
        # 3. Check Cache
        cached = self.cache.get(original_text, self.style)
        if cached:
            print("Cache hit!")
            final_text = cached
        else:
            # 4. Translate via OpenAI
            print("Requesting translation...")
            final_text = self.openai.translate_text(
                original_text, 
                self.prompt_template, 
                self.style
            )
            # Cache result (only if different or valid)
            if final_text != original_text:
                self.cache.set(original_text, self.style, final_text)
                self.cache.log(original_text, final_text, self.style)

        # 5. Set Clipboard
        self.clipboard.set_text(final_text)
        time.sleep(0.1) # Wait for clipboard write
        
        # 6. Simulate Paste (Ctrl+V)
        self._sim_key_combo("ctrl", "v")
        print("Done.")

    def close(self):
        if self.uinput:
            self.uinput.close()
