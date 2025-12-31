import time
import re
import hashlib
import sqlite3
import threading
import tkinter as tk
import json
import sys
import os
import queue

from openai import OpenAI
from PIL import Image
import pystray
from pystray import MenuItem as item
from pynput import keyboard as pk
import pyperclip

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

task_queue = queue.Queue()

# =========================
# CONFIG
# =========================

def load_config():
    global STYLE
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            CONFIG.update(json.load(f))
    STYLE = CONFIG.get("style", "strict")

def save_config():
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(CONFIG, f, indent=2)

load_config()

# =========================
# OPENAI
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
    return hashlib.sha256(f"{STYLE}::{text}".encode()).hexdigest()

def cache_get(text):
    c.execute("SELECT result FROM cache WHERE hash=?", (hash_text(text),))
    r = c.fetchone()
    return r[0] if r else None

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
# /me FIX
# =========================

AUX = {"is", "are", "was", "were", "am", "be", "been"}
ING = re.compile(r"\b(\w+)ing\b", re.I)

def conjugate(v):
    v = v.lower()
    if v == "have":
        return "has"
    if v.endswith(("s", "x", "z", "ch", "sh")):
        return v + "es"
    if v.endswith("y") and v[-2] not in "aeiou":
        return v[:-1] + "ies"
    return v + "s"

def fix_me(line):
    low = line.lower()
    if not (low.startswith("/me ") or low.startswith("/lme ")):
        return line

    cmd, *rest = line.split()
    if rest and rest[0].lower() in AUX:
        rest = rest[1:]

    if rest:
        rest[0] = conjugate(rest[0])

    text = ING.sub(r"\1", " ".join(rest))
    return f"{cmd} {text}"

# =========================
# PROMPT
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
# AI TRANSLATE
# =========================

def ai_translate(line):
    cached = cache_get(line)
    if cached:
        return cached

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
            timeout=8
        )
        out = res.choices[0].message.content.strip()
        cache_set(line, out)
        return out
    except Exception:
        return line

# =========================
# PIPELINE
# =========================

def process_text(text):
    lines = [l for l in text.split("\n") if l.strip()]
    out = []
    for line in lines:
        out.append(ai_translate(fix_me(line)))
    result = "\n".join(out)
    log_batch(text, result)
    return result

# =========================
# WORKER
# =========================

def worker():
    while True:
        task_queue.get()
        if not ENABLED:
            continue

        text = pyperclip.paste()
        if not text.strip():
            continue

        result = process_text(text)
        pyperclip.copy(result)

threading.Thread(target=worker, daemon=True).start()

# =========================
# PYNPUT LISTENER (SAFE)
# =========================

def on_press(key):
    try:
        if key == pk.Key.f9:
            task_queue.put(True)
    except:
        pass

listener = pk.Listener(on_press=on_press)
listener.daemon = True
listener.start()

# =========================
# TKINTER UI
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
    tk.Radiobutton(root, text=s.capitalize(), variable=style_var, value=s)\
        .pack(anchor="w", padx=30)

def save_settings():
    global STYLE
    CONFIG["style"] = style_var.get()
    CONFIG["api_key"] = api_var.get().strip()
    STYLE = CONFIG["style"]
    save_config()
    root.withdraw()

tk.Button(root, text="Save", command=save_settings).pack(pady=15)

def show_settings():
    root.deiconify()
    root.lift()
    root.attributes("-topmost", True)
    root.after(300, lambda: root.attributes("-topmost", False))

# =========================
# TRAY
# =========================

def toggle(icon, _):
    global ENABLED
    ENABLED = not ENABLED
    icon.title = f"RP Translator [{'ON' if ENABLED else 'OFF'}]"

def quit_app(icon, _):
    icon.stop()
    conn.close()
    root.destroy()
    sys.exit(0)

def tray_thread():
    icon = pystray.Icon(
        "RP Translator",
        Image.new("RGBA", (64, 64), (0, 0, 0, 255)),
        "RP Translator [ON]",
        menu=(
            item("Settings", lambda i, x: root.after(0, show_settings)),
            item("Toggle ON/OFF", toggle),
            item("Quit", quit_app),
        )
    )
    icon.run()

threading.Thread(target=tray_thread, daemon=True).start()

# =========================
# MAIN LOOP
# =========================

root.mainloop()
