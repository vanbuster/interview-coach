# interview-coach — Windows 一键安装脚本
# 适用：Windows 10/11 (x64)
# 用法：powershell -ExecutionPolicy Bypass -File setup.ps1

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

function Ok($msg)   { Write-Host "[OK] $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "[SKIP] $msg" -ForegroundColor Yellow }
function Fail($msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red }

Write-Host "=== interview-coach setup (Windows) ===" ""
Write-Host ""

# --- 1. ffmpeg ---
$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
if ($ffmpeg) {
    $ver = (ffmpeg -version 2>$null | Select-Object -First 1) -replace "ffmpeg version ", ""
    Ok "ffmpeg $ver"
} else {
    Write-Host "Installing ffmpeg via winget..."
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        winget install Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
        Ok "ffmpeg installed"
    } else {
        # Fallback: choco or manual
        $choco = Get-Command choco -ErrorAction SilentlyContinue
        if ($choco) {
            choco install ffmpeg -y
            Ok "ffmpeg installed via chocolatey"
        } else {
            Fail "winget and chocolatey not found."
            Write-Host "Install ffmpeg manually: https://ffmpeg.org/download.html"
            Write-Host "Or install winget: https://learn.microsoft.com/en-us/windows/apps/manage-app-provisioning"
            exit 1
        }
    }
}

# --- 2. Python 3.10+ ---
$pyVersion = python --version 2>$null
if ($pyVersion -match "Python (\d+)\.(\d+)") {
    $major = [int]$Matches[1]
    $minor = [int]$Matches[2]
    if ($major -ge 3 -and $minor -ge 10) {
        Ok "Python $major.$minor"
    } else {
        Fail "Python 3.10+ required (found $major.$minor)"
        Write-Host "Download: https://www.python.org/downloads/"
        exit 1
    }
} else {
    Fail "Python not found"
    Write-Host "Download: https://www.python.org/downloads/"
    exit 1
}

# --- 3. pip install ---
Write-Host ""
Write-Host "Installing Python packages..."
pip install -r "$ScriptDir\requirements.txt"
Ok "Python packages installed"

# --- 4. Pre-download Whisper model ---
Write-Host ""
Write-Host "Pre-downloading Whisper medium model (~1.5GB, one-time)..."
python -c "
from faster_whisper import WhisperModel
print('Downloading and caching model...')
model = WhisperModel('medium', device='cpu', compute_type='int8')
print('Model cached successfully')
" 2>$null
if ($LASTEXITCODE -eq 0) {
    Ok "Whisper medium model cached"
} else {
    Write-Host ""
    Warn "Model pre-download failed (network issue?). Will auto-download on first transcription."
}

# --- 5. CUDA check (optional) ---
Write-Host ""
$nvidia = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if ($nvidia) {
    $gpu = nvidia-smi --query-gpu=name --format=csv,noheader 2>$null
    Ok "NVIDIA GPU detected: $gpu (CUDA acceleration available)"
    Write-Host "  Use --device cuda for GPU acceleration"
} else {
    Warn "No NVIDIA GPU detected. Will use CPU (INT8 quantization)."
    Write-Host "  Install CUDA toolkit for GPU support: https://developer.nvidia.com/cuda-downloads"
}

# --- 6. Verify ---
Write-Host ""
Write-Host "=== Verification ==="

python "$ScriptDir\scripts\transcribe.py" --help 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
    Ok "transcribe.py ready"
} else {
    Fail "transcribe.py check failed"
}

python "$ScriptDir\scripts\split_audio.py" --help 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
    Ok "split_audio.py ready"
} else {
    Fail "split_audio.py check failed"
}

Write-Host ""
Write-Host "=== Setup complete ==="
Write-Host ""
Write-Host "Usage:"
Write-Host "  python scripts\transcribe.py interview.mp3"
Write-Host "  python scripts\transcribe.py interview.mp3 --device cuda   (GPU)"
Write-Host ""
Write-Host "As Claude Code Skill:"
Write-Host "  Copy this folder to ~/.claude/skills/interview-review-coach"
Write-Host ""
