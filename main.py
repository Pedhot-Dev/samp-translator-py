
import sys
import time
import signal
from src.config_loader import load_config
from src.cache_layer import CacheLayer
from src.clipboard_handler import ClipboardHandler
from src.openai_client import OpenAIClient
from src.input_listener import InputListener
from src.translator_core import TranslatorCore

def main():
    print("Starting Arch Translator Tool...")
    
    # 1. Load Config
    config = load_config()
    
    # 2. Initialize Components
    cache = CacheLayer(db_path=config["cache"]["db_path"])
    clipboard = ClipboardHandler()
    openai = OpenAIClient(config)
    
    # 3. Initialize Core Logic
    core = TranslatorCore(config, cache, clipboard, openai)
    
    # 4. Initialize Input Listener
    def hotkey_callback():
        core.process_selection()

    listener = InputListener(config, hotkey_callback)
    listener.start()

    print("\nRunning. Press Ctrl+C to exit.")
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
        listener.stop()
        core.close()
        cache.close()
        sys.exit(0)

if __name__ == "__main__":
    main()
