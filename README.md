# SAMP Translator (Python)

A lightweight desktop translator for SAMP / GTA Roleplay, designed to translate RP text intelligently while respecting RP command rules.

Built for fast, hotkey-based usage with optional AI support, local caching, and safe fallback behavior.

---

## Features

- Hotkey-based translation (`F9`)
- RP-aware command handling:
  - `/me`, `/lme`
  - `/do`, `/ldo`
  - Other commands treated as dialogue
- Parenthetical action handling inside dialogue  
  `(example: "You (points at John)")`
- Translation styles:
  - **strict** – grammatically correct English
  - **street** – casual / slang-friendly
  - **broken** – intentionally imperfect English
- Local SQLite cache (reduces API usage)
- Tray icon with enable/disable toggle
- Settings UI (no restart required)
- Offline-safe fallback (no crash if AI is unavailable)
- Windows executable (no Python required)

---

## Installation

1. Go to the **Releases** page.
2. Download the latest `.exe` (x64 or x86).
3. Place it anywhere you want and run it.

No Python installation is required.

---

## Usage

1. Select any text (in-game chat, editor, browser, etc.).
2. Press **F9**.
3. The selected text is replaced with the translated result.

The application runs in the background and is accessible from the system tray.

---

## Settings & Configuration

### Opening Settings
1. Locate the tray icon (bottom-right corner of the screen).
2. Right-click the icon.
3. Click **Settings**.

---

### Available Settings

#### OpenAI API Key
- Enables AI-powered translation.
- If left empty or invalid:
  - No API calls are made.
  - Original text is returned unchanged.
- The API key is stored **locally only**.

> You must provide your own OpenAI API key.

---

#### Translation Style
Controls the tone of the translated output.

Available styles:
- **strict** – neutral, grammatically correct English
- **street** – casual, informal tone
- **broken** – intentionally imperfect English

Changing the style:
- Immediately affects new translations
- Automatically clears the translation cache

---

### Saving Settings
- Click **Save** to apply changes.
- No application restart is required.

Settings are stored in a local file:

## License
Apache-2.0

## Thanks to
- GPT as code helper and README maker
- OpenAI as AI translation API (but KIKIR ANJG)
