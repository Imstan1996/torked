#!/bin/bash
# Double-click this file to play THRESHOLD.
# It starts the local server and opens the game in your browser.
cd "$(dirname "$0")"
echo ""
echo "  Starting THRESHOLD..."
echo "  A browser tab will open at http://localhost:8000"
echo "  Keep this window open while you play."
echo "  To stop: close this window or press Ctrl+C."
echo ""
exec python3 server.py
