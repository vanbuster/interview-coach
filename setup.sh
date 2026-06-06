#!/bin/bash
# interview-coach — 一键安装脚本
# 适用：Linux / macOS (faster-whisper 引擎)
# 用法：bash setup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo "${GREEN}[OK]${NC} $1"; }
warn() { echo "${YELLOW}[SKIP]${NC} $1"; }
fail() { echo "${RED}[FAIL]${NC} $1"; }

echo "=== interview-coach setup ==="
echo ""

# --- 1. Platform ---
OS="$(uname)"
ARCH="$(uname -m)"
echo "Platform: $OS ($ARCH)"

# --- 2. ffmpeg ---
if command -v ffmpeg &>/dev/null; then
    ok "ffmpeg $(ffmpeg -version | head -1 | awk '{print $3}')"
else
    echo "Installing ffmpeg..."
    if command -v brew &>/dev/null; then
        brew install ffmpeg
        ok "ffmpeg installed"
    elif command -v apt-get &>/dev/null; then
        sudo apt-get update && sudo apt-get install -y ffmpeg
        ok "ffmpeg installed"
    else
        fail "No supported package manager found (brew / apt-get)"
        echo "Install ffmpeg manually: https://ffmpeg.org/download.html"
        exit 1
    fi
fi

# --- 3. Python 3.10+ ---
PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [[ "$PY_MAJOR" -ge 3 && "$PY_MINOR" -ge 10 ]]; then
    ok "Python $PY_VERSION"
else
    fail "Python 3.10+ required (found $PY_VERSION)"
    echo "Install: brew install python@3.12"
    exit 1
fi

# --- 4. pip install ---
echo ""
echo "Installing Python packages..."
pip3 install -r "$SCRIPT_DIR/requirements.txt"
ok "Python packages installed"

# --- 5. Pre-download Whisper model ---
echo ""
echo "Pre-downloading Whisper medium model (~1.5GB, one-time)..."
python3 -c "
from faster_whisper import WhisperModel
print('Downloading and caching model...')
model = WhisperModel('medium', device='cpu', compute_type='int8')
print('Model cached successfully')
" 2>/dev/null || {
    echo ""
    warn "Model pre-download failed (network issue?). Will auto-download on first transcription."
}

# --- 6. lark-cli (optional) ---
echo ""
if command -v lark-cli &>/dev/null; then
    ok "lark-cli found (Feishu output available)"
else
    warn "lark-cli not found. Feishu output unavailable, will use HTML fallback."
    echo "To enable Feishu output: npm install -g lark-cli && lark-cli auth login"
fi

# --- 7. Verify ---
echo ""
echo "=== Verification ==="

if python3 "$SCRIPT_DIR/scripts/transcribe.py" --help &>/dev/null; then
    ok "transcribe.py ready"
else
    fail "transcribe.py check failed"
fi

if python3 "$SCRIPT_DIR/scripts/split_audio.py" --help &>/dev/null; then
    ok "split_audio.py ready"
else
    fail "split_audio.py check failed"
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "Usage:"
echo "  python3 scripts/transcribe.py interview.mp3"
echo ""
echo "As Claude Code Skill:"
echo "  cp -r $SCRIPT_DIR ~/.claude/skills/interview-review-coach"
echo ""
