# Arch Linux RP Translator

A Python-based global text translation tool optimized for Arch Linux (X11/Wayland).

## Features
- **Global Hotkey (F9)**: Works in fullscreen applications via `evdev`.
- **In-place Translation**: Simulates Ctrl+C → Translate → Ctrl+V.
- **Configurable**: All settings in `config.yml`.
- **Persistent Cache**: Reduces API calls by storing results locally.
- **Hard Fallback**: Returns original text on any network/API error.
- **Custom Prompts**: External `prompt.txt` file.

## Why the Refactor?
The original Windows-based version relied on `keyboard` hooks and `tkinter` which are unreliable on Arch Linux, especially under Wayland or strict X11 setups. This version uses:
- **`evdev`**: For low-level input handling (listening to F9) and output simulation (uinput for Ctrl+C/V).
- **Native Clipboard Tools**: `wl-copy`/`wl-paste` (Wayland) and `xclip`/`xsel` (X11).
- **Headless Design**: Runs as a CLI/Daemon, no GUI dependencies.

## Installation

### 1. Requirements
Ensure you have the following system tools:
- **X11**: `xclip` or `xsel`
- **Wayland**: `wl-clipboard`
- **Python**: 3.x

### 2. Setup
```bash
# Clone/Download
cd samp-translator-py

# Install dependencies
pip install -r requirements.txt
```

### 3. Permissions (Critical)
The tool uses `evdev` to listen to keyboard events and inject keys. This requires access to `/dev/input/*` and `/dev/uinput`.

**Option A: Run as Root (Easiest)**
```bash
# Run with sudo using the virtual environment python
sudo .venv/bin/python main.py
```

*Note: I have already created the `.venv` and installed dependencies for you.*

**Option B: Add user to input group**
```bash
sudo usermod -aG input $USER
# You may also need to create a udev rule for uinput if not accessible
# Log out and back in for changes to take effect
```

## Configuration
Edit `config.yml` to set your API key and preferences:
```yaml
openai:
  api_key: "sk-..."
  model: "gpt-4o-mini"

hotkey: "KEY_F9"  # evdev key code
style: "strict"   # Translation style
```

## Known Limitations
- **Wayland**: Key injection via `uinput` works generally, but some Wayland compositors might intercept or block virtual input in secure contexts.
- **Fullscreen Games**: `evdev` usually works fine, but anti-cheat systems might flag synthetic input.

## Troubleshooting
- **Permission Denied**: Run with `sudo`.
- **No Translation**: Check `config.yml` API key and ensure you have internet access. If API fails, it pastes original text.
- **Clipboard Error**: Install `xclip` (X11) or `wl-clipboard` (Wayland).
