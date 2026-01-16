
import evdev
from evdev import InputDevice, categorize, ecodes
import threading
import time
import select
import sys

class InputListener:
    def __init__(self, config, callback):
        self.hotkey_name = config.get("hotkey", "KEY_F9")
        self.callback = callback
        self.devices = []
        self.running = False
        self.thread = None

    def find_all_keyboards(self):
        """Finds all devices that look like keyboards and support the hotkey."""
        candidates = []
        target_key = ecodes.ecodes.get(self.hotkey_name)
        
        if target_key is None:
            print(f"Error: Invalid hotkey name '{self.hotkey_name}' in config.")
            return []

        try:
            paths = evdev.list_devices()
            for path in paths:
                try:
                    dev = InputDevice(path)
                    # Check if device supports EV_KEY
                    cap_keys = dev.capabilities().get(ecodes.EV_KEY)
                    if cap_keys:
                        # Check if it supports our specific hotkey (smart filtering)
                        if target_key in cap_keys:
                            candidates.append(dev)
                except Exception:
                    continue
        except Exception as e:
            print(f"Error scanning devices: {e}")
            
        return candidates

    def start(self):
        self.devices = self.find_all_keyboards()
        if not self.devices:
            print("Error: No keyboard devices found that support the configured hotkey.")
            print("Ensure you are running with sudo or have input group permissions.")
            return

        print(f"Listening for {self.hotkey_name} on {len(self.devices)} devices:")
        for d in self.devices:
            print(f" - {d.name} ({d.path})")
        
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
        target_key = ecodes.ecodes.get(self.hotkey_name)
        
        # Map file descriptors to devices for select
        fd_to_dev = {dev.fd: dev for dev in self.devices}
        
        try:
            while self.running:
                # Wait for input on any of the devices
                r, w, x = select.select(self.devices, [], [], 1.0)
                
                for dev in r:
                    try:
                        for event in dev.read():
                            if event.type == ecodes.EV_KEY:
                                if event.value == 1:  # Key Down
                                    if event.code == target_key:
                                        # print(f"Hotkey detected on {dev.name}!")
                                        # Run callback in separate thread to not block input loop
                                        threading.Thread(target=self.callback).start()
                    except OSError:
                        # Device disconnected?
                        pass
                        
        except Exception as e:
            print(f"Input listener loop error: {e}")
        finally:
            self.running = False
            for d in self.devices:
                try:
                    d.close()
                except:
                    pass

    def stop(self):
        self.running = False
