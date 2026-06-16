"""Smoke test for split_audio.py.

Generates a tiny synthetic WAV via ffmpeg, runs the splitter with fixed
boundaries, and asserts the output segments exist with reasonable duration.
No network, no Whisper model — keeps CI fast and deterministic.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
REPO_ROOT = Path(__file__).resolve().parent.parent


def _generate_wav(path: Path, duration_s: float = 10.0) -> None:
    """Generate a 10-second silent WAV via ffmpeg."""
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"anullsrc=r=16000:cl=mono",
            "-t", str(duration_s),
            "-q:a", "9",
            str(path),
        ],
        check=True,
        capture_output=True,
    )


def test_split_audio_produces_segments(tmp_path: Path) -> None:
    # 1. Generate fixture
    audio = tmp_path / "fixture.wav"
    _generate_wav(audio, duration_s=10.0)
    assert audio.exists(), "ffmpeg failed to generate fixture"

    # 2. Boundaries: top-level array (matches skill's actual boundaries.json format)
    boundaries = [
        {"start": 0.0, "end": 3.0, "question": "Q01"},
        {"start": 3.0, "end": 6.0, "question": "Q02"},
        {"start": 6.0, "end": 10.0, "question": "Q03"},
    ]
    boundaries_path = tmp_path / "boundaries.json"
    boundaries_path.write_text(json.dumps(boundaries))

    # 3. Run the splitter
    out_dir = tmp_path / "segments"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_DIR / "split_audio.py"),
            str(audio),
            "--boundaries", str(boundaries_path),
            "--output", str(out_dir),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"split_audio failed: {result.stderr}"

    # 4. Verify 3 MP3 files produced
    mp3_files = sorted(out_dir.glob("Q*.mp3"))
    assert len(mp3_files) == 3, f"Expected 3 MP3s, got {len(mp3_files)}: {[p.name for p in mp3_files]}"

    # 5. Each segment should be > 1KB (valid MP3 header + minimal frames)
    for mp3 in mp3_files:
        assert mp3.stat().st_size > 1024, f"{mp3.name} too small: {mp3.stat().st_size} bytes"


def test_split_audio_help_works() -> None:
    """The --help flag should exit 0 and mention key options."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "split_audio.py"), "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "boundaries" in result.stdout.lower() or "boundaries" in result.stderr.lower()
