# THRESHOLD — an ever-changing medieval text RPG

A Zork-style text adventure where an AI is the Game Master, so the map, items,
monsters and quests are invented fresh every playthrough.

## Run it (2 steps)

1. Open a terminal in this folder and start the server:

   ```
   cd "zork remake"
   python3 server.py
   ```

   Your browser opens automatically at **http://localhost:8000**.

2. On the start screen, choose an **engine**, paste a key if needed, and play.

## Free engines

Pick any of these in the **Engine** dropdown — all free:

| Engine | Cost | Key? | Get started |
|--------|------|------|-------------|
| **Ollama** (local) | Free, unlimited, private | none | Install [ollama.com](https://ollama.com), run `ollama pull llama3.2`, keep it running |
| **Groq** (cloud) | Free tier (~30 req/min) | yes | Key at [console.groq.com/keys](https://console.groq.com/keys) |
| **Google Gemini** (cloud) | Free tier (1,500/day) | yes | Key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| **Hugging Face** | Your Pro credits | yes | Token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) |

**Recommended:** Groq for a no-install, fast start; **Ollama** if you want truly
unlimited, private play and don't mind a one-time model download.

> Prefer not to type the key each time? Preset it:
> `export LLM_BASE_URL=https://api.groq.com/openai/v1 LLM_TOKEN=gsk_xxxx` then `python3 server.py`.

## Why a local server?

These providers are OpenAI-compatible but block direct browser calls (CORS), and
you should never ship an API key in client-side code. `server.py` runs only on
your machine: it serves the page and proxies each turn to your chosen engine,
keeping your key private. No third party ever sees it. (Ollama needs no key at
all — it runs entirely on your computer.)

## Files

- `index.html` — the game (UI + engine + canonical game state).
- `server.py` — zero-dependency local server + HF proxy.

## Offline demo

No token? Click **Play offline demo** for a small procedural world that shows the
mechanics (movement, loot, combat, resting). The live HF game is far richer.

## Models

Each engine shows a menu of good models. The "Custom model id" box lets you type
any exact model id the chosen engine supports. Bigger models follow the game's
rules better; smaller local ones are free and fast but less clever.

## How the engine stays consistent

The browser holds the authoritative state (HP, gold, inventory, location, exits)
and sends it back to the model every turn. The model replies with strict JSON —
narration plus state changes — which the game applies. So the world improvises
endlessly but never contradicts itself.
