import time
import re
import hashlib
import sqlite3
import threading
import keyboard
import pyperclip
import tkinter as tk
import json
import sys
import os

from openai import OpenAI
from PIL import Image
import pystray
from pystray import MenuItem as item

# =========================
# PATH HELPERS
# =========================

def app_dir():
    if hasattr(sys, "_MEIPASS"):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(app_dir(), "config.json")
DB_FILE = os.path.join(app_dir(), "rp_translator.db")

# =========================
# GLOBAL STATE
# =========================

CONFIG = {
    "style": "strict",
    "api_key": ""
}

STYLE = "strict"
ENABLED = True
MODEL = "gpt-4o-mini"

# =========================
# CONFIG LOAD / SAVE
# =========================

def load_config():
    global STYLE, CONFIG
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            CONFIG.update(data)
    STYLE = CONFIG.get("style", "strict")

def save_config():
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(CONFIG, f, indent=2)

load_config()

# =========================
# OPENAI CLIENT (LAZY)
# =========================

def get_client():
    key = CONFIG.get("api_key", "").strip()
    if not key:
        return None
    return OpenAI(api_key=key)

# =========================
# DATABASE
# =========================

conn = sqlite3.connect(DB_FILE, check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS cache (
    hash TEXT PRIMARY KEY,
    result TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS logs (
    time TEXT,
    original TEXT,
    result TEXT,
    style TEXT
)
""")

conn.commit()

# =========================
# CACHE + LOG
# =========================

def hash_text(text):
    key = f"{STYLE}::{text}"
    return hashlib.sha256(key.encode()).hexdigest()

def clear_cache():
    c.execute("DELETE FROM cache")
    conn.commit()

def cache_get(text):
    h = hash_text(text)
    c.execute("SELECT result FROM cache WHERE hash=?", (h,))
    row = c.fetchone()
    return row[0] if row else None

def cache_set(text, result):
    c.execute(
        "INSERT OR REPLACE INTO cache VALUES (?,?)",
        (hash_text(text), result)
    )
    conn.commit()

def log_batch(orig, result):
    c.execute(
        "INSERT INTO logs VALUES (datetime('now'),?,?,?)",
        (orig, result, STYLE)
    )
    conn.commit()

# =========================
# /me LOCAL FIX
# =========================

AUX = {"is", "are", "was", "were", "am", "be", "been"}
ING = re.compile(r"\b(\w+)ing\b", re.I)

def conjugate(verb):
    verb = verb.lower()
    if verb == "have":
        return "has"
    if verb.endswith(("s", "x", "z", "ch", "sh")):
        return verb + "es"
    if verb.endswith("y") and verb[-2] not in "aeiou":
        return verb[:-1] + "ies"
    return verb + "s"

def fix_me(line):
    low = line.lower()
    if not (low.startswith("/me ") or low.startswith("/lme ")):
        return line

    cmd, *rest = line.split()
    if not rest:
        return line

    if rest[0].lower() in AUX:
        rest = rest[1:]

    if rest:
        rest[0] = conjugate(rest[0])

    text = " ".join(rest)
    text = ING.sub(r"\1", text)

    return f"{cmd} {text}"

# =========================
# PROMPT (INTENTIONALLY EMPTY / CUSTOM)
# =========================

PROMPT = """
ROLE & CONTEXT
You are an RP Translation Engine, not a conversational AI.
Your ONLY task is to translate text into English while preserving roleplay mechanics.
Translation style is defined by: {style}.
No explanations. No commentary. Output translation only.

SUPPORTED RP COMMANDS
Action commands:
- /me
- /lme

Descriptive commands:
- /do
- /ldo

Other commands (e.g. /wt, /low, /shout) are treated as dialogue commands.

COMMAND MAPPING
- /me and /lme use the same action grammar rules
- /do and /ldo use the same descriptive grammar rules
- /lme is a separate RP command with identical grammar behavior to /me
- /ldo is a separate RP command with identical grammar behavior to /do

/me & /lme RULES
- Use third-person singular present tense
- Verb must end with s / es
- NEVER use past tense
- NEVER use “is / was / are”
- Describe a clear action

/do & /ldo RULES
- Use descriptive or observational English
- Passive voice allowed
- Do NOT apply /me verb rules

PARENTHETICAL ACTION INSIDE DIALOGUE (CRITICAL)
If input is normal dialogue (does NOT start with /me, /lme, /do, or /ldo)
AND contains parentheses ( ):
- Text outside parentheses is dialogue
- Text inside parentheses is treated as an action using /me grammar rules
- Parentheses MUST be preserved
- Do NOT create new RP commands
- Do NOT move parenthetical content to a new line

Example:
Kamu (nunjuk Tadeo), dan kamu (nunjuk Vitello)
→
You (points at Tadeo), and you (points at Vitello)

NAME & ID RULES
- Preserve Proper Names exactly as written
- Preserve @number IDs
- Do NOT translate names
- Do NOT alter capitalization

STYLE RULE
{style} affects tone only:
- strict → grammatically correct English
- street → casual / slang-friendly
- broken → intentionally imperfect
Style MUST NOT affect RP structure or grammar rules.

OUTPUT
Return ONLY the translated text.
"""

# =========================
# AI TRANSLATION WITH FULL FALLBACK
# =========================

def ai_translate(line):
    # 1. Cache first
    cached = cache_get(line)
    if cached:
        return cached

    # 2. No API key → hard fallback
    client = get_client()
    if client is None:
        return line

    try:
        res = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": PROMPT.format(style=STYLE)},
                {"role": "user", "content": line}
            ],
            timeout=10
        )
        out = res.choices[0].message.content.strip()
        cache_set(line, out)
        return out

    except Exception as e:
        # 3. ANY ERROR = fallback
        # includes: rate limit, network error, invalid key, quota exceeded
        return line

# =========================
# PIPELINE
# =========================

def process_text(text):
    lines = [l for l in text.split("\n") if l.strip()]
    out = []

    for line in lines:
        fixed = fix_me(line)
        translated = ai_translate(fixed)
        out.append(translated)

    result = "\n".join(out)
    log_batch(text, result)
    return result

# =========================
# HOTKEY
# =========================

def on_f9():
    if not ENABLED:
        return

    keyboard.press_and_release("ctrl+c")
    time.sleep(0.1)

    text = pyperclip.paste()
    if not text.strip():
        return

    result = process_text(text)
    pyperclip.copy(result)
    time.sleep(0.05)
    keyboard.press_and_release("ctrl+v")

keyboard.add_hotkey("F9", on_f9)

# =========================
# TKINTER UI (ONE ROOT)
# =========================

root = tk.Tk()
root.title("RP Translator Settings")
root.geometry("350x260")
root.resizable(False, False)
root.withdraw()

tk.Label(root, text="OpenAI API Key").pack(pady=(10, 0))
api_var = tk.StringVar(value=CONFIG.get("api_key", ""))
tk.Entry(root, textvariable=api_var, show="*", width=32).pack(pady=5)

style_var = tk.StringVar(value=STYLE)
tk.Label(root, text="Translation Style").pack(pady=10)

for s in ["strict", "street", "broken"]:
    tk.Radiobutton(
        root,
        text=s.capitalize(),
        variable=style_var,
        value=s
    ).pack(anchor="w", padx=30)

def save_settings():
    global STYLE
    CONFIG["style"] = style_var.get()
    CONFIG["api_key"] = api_var.get().strip()
    STYLE = CONFIG["style"]
    clear_cache()
    save_config()
    root.withdraw()

tk.Button(root, text="Save", command=save_settings).pack(pady=15)

def show_settings():
    style_var.set(CONFIG.get("style", STYLE))
    api_var.set(CONFIG.get("api_key", ""))
    root.deiconify()
    root.lift()
    root.attributes("-topmost", True)
    root.after(300, lambda: root.attributes("-topmost", False))

# =========================
# TRAY ICON
# =========================

def toggle(icon, _):
    global ENABLED
    ENABLED = not ENABLED
    icon.title = f"RP Translator [{'ON' if ENABLED else 'OFF'}]"

def quit_app(icon, _):
    icon.stop()
    keyboard.unhook_all()
    conn.close()
    root.destroy()
    sys.exit(0)

def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(app_dir(), relative_path)

def load_tray_icon():
    try:
        img = Image.open(resource_path("icon.ico"))
        if hasattr(img, "n_frames") and img.n_frames > 1:
            img.seek(img.n_frames - 1)
        return img.convert("RGBA")
    except Exception:
        return Image.new("RGBA", (64, 64), (0, 0, 0, 255))

def tray_thread():
    image = load_tray_icon()
    menu = (
        item("Settings", lambda i, x: root.after(0, show_settings)),
        item("Toggle ON/OFF", toggle),
        item("Quit", quit_app)
    )
    icon = pystray.Icon(
        "RP Translator",
        image,
        f"RP Translator [{'ON' if ENABLED else 'OFF'}]",
        menu
    )
    icon.run()

threading.Thread(target=tray_thread, daemon=True).start()

# =========================
# MAIN LOOP
# =========================

def keyboard_loop():
    keyboard.wait()

threading.Thread(target=keyboard_loop, daemon=True).start()
root.mainloop()
