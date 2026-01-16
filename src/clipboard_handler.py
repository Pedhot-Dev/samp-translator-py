
import os
import subprocess
import shutil

class ClipboardHandler:
    def __init__(self):
        self.session_type = os.environ.get("XDG_SESSION_TYPE", "x11").lower()
        self.wayland = "wayland" in self.session_type
        
        # Check for tools
        self.wl_copy = shutil.which("wl-copy")
        self.wl_paste = shutil.which("wl-paste")
        self.xclip = shutil.which("xclip")
        self.xsel = shutil.which("xsel")
        
        if self.wayland:
            if not self.wl_copy or not self.wl_paste:
                print("Warning: Wayland detected but wl-clipboard not found. Clipboard may fail.")
        else:
            if not self.xclip and not self.xsel:
                print("Warning: X11 detected but xclip/xsel not found. Clipboard may fail.")

    def get_text(self):
        """Reads text from the primary clipboard."""
        try:
            if self.wayland and self.wl_paste:
                return subprocess.check_output([self.wl_paste], text=True).strip()
            elif self.xclip:
                return subprocess.check_output(
                    [self.xclip, "-selection", "clipboard", "-o"], 
                    text=True, stderr=subprocess.DEVNULL
                ).strip()
            elif self.xsel:
                return subprocess.check_output(
                    [self.xsel, "--clipboard", "--output"], 
                    text=True, stderr=subprocess.DEVNULL
                ).strip()
            else:
                # Fallback to pure python solution if binary missing (might be flaky on Linux)
                import tkinter as tk
                root = tk.Tk()
                root.withdraw()
                return root.clipboard_get()
        except Exception as e:
            print(f"Clipboard read error: {e}")
            return ""

    def set_text(self, text):
        """Writes text to the primary clipboard."""
        try:
            if self.wayland and self.wl_copy:
                p = subprocess.Popen([self.wl_copy], stdin=subprocess.PIPE)
                p.communicate(input=text.encode('utf-8'))
            elif self.xclip:
                p = subprocess.Popen(
                    [self.xclip, "-selection", "clipboard", "-i"], 
                    stdin=subprocess.PIPE
                )
                p.communicate(input=text.encode('utf-8'))
            elif self.xsel:
                p = subprocess.Popen(
                    [self.xsel, "--clipboard", "--input"], 
                    stdin=subprocess.PIPE
                )
                p.communicate(input=text.encode('utf-8'))
            else:
                # Fallback
                import tkinter as tk
                root = tk.Tk()
                root.withdraw()
                root.clipboard_clear()
                root.clipboard_append(text)
                root.update()
                root.destroy()
        except Exception as e:
            print(f"Clipboard write error: {e}")
