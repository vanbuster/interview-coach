#!/usr/bin/env python3
"""
interview-coach: 音频转写脚本 — 跨平台 (macOS / Linux / Windows)

将面试录音转写为带时间戳的文本，自动选择最佳引擎：
  - auto (默认): macOS 优先 mlx-whisper (Metal)，其余平台用 faster-whisper
  - mlx:         mlx-whisper，macOS Metal 加速
  - faster-whisper: CTranslate2 后端，全平台 (CPU + NVIDIA CUDA)
  - sensevoice:  SenseVoiceSmall，macOS 可选，无词级时间戳

用法:
  python3 scripts/transcribe.py interview.mp3
  python3 scripts/transcribe.py interview.mp3 --model large-v3-turbo
  python3 scripts/transcribe.py interview.mp3 --device cuda --compute-type float16
"""

import argparse
import json
import os
import subprocess
import sys
import time


def get_audio_duration(audio_path: str) -> float:
    """用 ffprobe 获取音频时长（秒）。"""
    cmd = [
        "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
        "-of", "csv=p=0", audio_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return float(result.stdout.strip())


def split_audio_chunks(audio_path: str, chunk_duration: int, overlap: int, output_dir: str):
    """将音频切成重叠片段，返回片段信息列表。"""
    os.makedirs(output_dir, exist_ok=True)
    duration = get_audio_duration(audio_path)
    chunks = []
    start = 0
    idx = 0
    while start < duration:
        end = min(start + chunk_duration, duration)
        chunk_path = os.path.join(output_dir, f"chunk_{idx:03d}.wav")
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-i", audio_path,
            "-ss", str(start), "-to", str(end),
            "-ar", "16000", "-ac", "1",
            "-f", "wav", chunk_path,
        ]
        subprocess.run(ffmpeg_cmd, capture_output=True)
        chunks.append({"index": idx, "path": chunk_path, "start": start, "end": end})
        idx += 1
        start += chunk_duration - overlap
    return chunks, duration


# ---------------------------------------------------------------------------
# Engine: mlx-whisper (macOS Metal)
# ---------------------------------------------------------------------------

def transcribe_whisper_mlx(audio_path: str, model: str = "medium", language: str = "zh"):
    """Whisper 转写（mlx-whisper，macOS Metal 加速）。"""
    import mlx_whisper

    hf_repo = f"mlx-community/whisper-{model}"
    print(f"Engine: mlx-whisper (Metal)", flush=True)
    print(f"Model: {hf_repo}", flush=True)
    print(f"Language: {language}", flush=True)

    start_t = time.time()
    result = mlx_whisper.transcribe(
        audio_path,
        path_or_hf_repo=hf_repo,
        language=language,
        word_timestamps=True,
        verbose=False,
    )
    elapsed = time.time() - start_t
    return result, elapsed


# ---------------------------------------------------------------------------
# Engine: faster-whisper (CTranslate2, cross-platform)
# ---------------------------------------------------------------------------

def transcribe_whisper_faster(
    audio_path: str,
    model: str = "medium",
    language: str = "zh",
    device: str = "auto",
    compute_type: str = "auto",
):
    """Whisper 转写（faster-whisper / CTranslate2，全平台）。"""
    from faster_whisper import WhisperModel

    if device == "auto":
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"

    if compute_type == "auto":
        compute_type = "float16" if device == "cuda" else "int8"

    print(f"Engine: faster-whisper (CTranslate2)", flush=True)
    print(f"Model: {model}", flush=True)
    print(f"Device: {device} | Compute: {compute_type}", flush=True)
    print(f"Language: {language}", flush=True)

    start_t = time.time()
    fw_model = WhisperModel(model, device=device, compute_type=compute_type)
    segments_iter, info = fw_model.transcribe(
        audio_path,
        language=language,
        word_timestamps=True,
        vad_filter=True,
    )

    segments = []
    all_text_parts = []
    for seg in segments_iter:
        words = []
        for w in seg.words:
            words.append({
                "word": w.word,
                "start": w.start,
                "end": w.end,
                "probability": w.probability,
            })
        segments.append({
            "id": seg.id,
            "start": seg.start,
            "end": seg.end,
            "text": seg.text,
            "words": words,
        })
        all_text_parts.append(seg.text)

    elapsed = time.time() - start_t
    result = {"text": "".join(all_text_parts), "segments": segments}
    return result, elapsed


# ---------------------------------------------------------------------------
# Engine: SenseVoice (macOS, optional)
# ---------------------------------------------------------------------------

def transcribe_sensevoice_chunk(chunk_path: str, chunk_start: float, chunk_end: float):
    """转写单个 SenseVoice 切片。"""
    from mlx_audio.stt.generate import generate_transcription

    result = generate_transcription(model="mlx-community/SenseVoiceSmall", audio=chunk_path)
    text = ""
    if hasattr(result, "text") and result.text:
        text = result.text
    elif hasattr(result, "segments") and result.segments:
        text = " ".join(s.get("text", "") for s in result.segments if s.get("text"))
    return [{"start": chunk_start, "end": chunk_end, "text": text}]


def merge_chunk_texts(chunks_with_text, overlap_seconds: int = 30):
    """合并重叠切片文本。"""
    if not chunks_with_text:
        return [], ""
    ratio_skip = overlap_seconds / (chunks_with_text[0]["end"] - chunks_with_text[0]["start"]) if chunks_with_text else 0
    all_segments = []
    text_parts = []
    for i, chunk in enumerate(chunks_with_text):
        txt = chunk.get("text", "").strip()
        if not txt:
            continue
        if i == 0:
            clean = txt
        else:
            skip = int(len(txt) * ratio_skip)
            clean = txt[skip:]
        if clean.strip():
            text_parts.append(clean.strip())
            all_segments.append({"start": chunk["start"], "end": chunk["end"], "text": clean.strip()})
    full_text = " ".join(text_parts)
    return all_segments, full_text


def transcribe_sensevoice(audio_path: str):
    """SenseVoice 转写：短音频直接转，长音频自动 overlap 切片。"""
    from mlx_audio.stt.generate import generate_transcription

    duration = get_audio_duration(audio_path)
    chunk_duration = 240
    overlap = 30

    print(f"Engine: SenseVoice (MLX)", flush=True)
    print(f"Model: mlx-community/SenseVoiceSmall", flush=True)
    print(f"Audio duration: {duration:.0f}s", flush=True)

    if duration <= chunk_duration:
        print("Short audio — direct transcription", flush=True)
        start_t = time.time()
        result = generate_transcription(model="mlx-community/SenseVoiceSmall", audio=audio_path)
        elapsed = time.time() - start_t
        print(f"Completed in {elapsed:.1f}s", flush=True)
        segments = []
        if hasattr(result, "segments") and result.segments:
            for seg in result.segments:
                segments.append({"start": seg.get("start", 0), "end": seg.get("end", 0), "text": seg.get("text", "")})
        if not segments and hasattr(result, "text") and result.text:
            segments.append({"start": 0, "end": duration, "text": result.text})
        return {"text": result.text if hasattr(result, "text") else "", "segments": segments}, elapsed

    print(f"Long audio — chunking ({chunk_duration}s windows, {overlap}s overlap)", flush=True)
    tmp_dir = os.path.join(os.path.dirname(audio_path), f".transcribe_chunks_{int(time.time())}")
    try:
        chunks, _ = split_audio_chunks(audio_path, chunk_duration, overlap, tmp_dir)
        print(f"Split into {len(chunks)} chunks", flush=True)
        chunks_with_text = []
        total_elapsed = 0
        for i, chunk in enumerate(chunks):
            print(f"  Chunk {i+1}/{len(chunks)} ({chunk['start']:.0f}s-{chunk['end']:.0f}s)...", flush=True, end="")
            start_t = time.time()
            segs = transcribe_sensevoice_chunk(chunk["path"], chunk["start"], chunk["end"])
            chunk_elapsed = time.time() - start_t
            total_elapsed += chunk_elapsed
            for s in segs:
                chunks_with_text.append(s)
            print(f" {chunk_elapsed:.1f}s", flush=True)
        print(f"\nMerging overlapped chunks...", flush=True)
        merged_segments, full_text = merge_chunk_texts(chunks_with_text, overlap)
        print(f"Merged: {len(merged_segments)} segments, {len(full_text)} chars", flush=True)
        return {"text": full_text, "segments": merged_segments}, total_elapsed
    finally:
        for chunk in chunks:
            if os.path.exists(chunk["path"]):
                os.remove(chunk["path"])
        if os.path.isdir(tmp_dir):
            os.rmdir(tmp_dir)


# ---------------------------------------------------------------------------
# Auto-detect & dispatch
# ---------------------------------------------------------------------------

def detect_best_engine() -> str:
    """Auto-detect best available engine for this platform."""
    if sys.platform == "darwin":
        try:
            import mlx_whisper
            return "mlx"
        except ImportError:
            pass
    try:
        from faster_whisper import WhisperModel
        return "faster-whisper"
    except ImportError:
        pass
    # macOS without faster-whisper — try mlx as last resort
    if sys.platform == "darwin":
        try:
            import mlx_whisper
            return "mlx"
        except ImportError:
            pass
    print("No Whisper engine found. Install one of:", file=sys.stderr)
    print("  pip install faster-whisper       (all platforms)", file=sys.stderr)
    print("  pip install mlx-whisper           (macOS Apple Silicon)", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Save results
# ---------------------------------------------------------------------------

def save_results(result, elapsed: float, audio_path: str):
    """保存转写结果为 JSON 和带时间戳的文本。"""
    text = result.get("text", "")
    segments = result.get("segments", [])
    duration = get_audio_duration(audio_path)

    print(f"\nCompleted: {len(segments)} segments, {len(text)} chars, {elapsed:.1f}s", flush=True)

    output_dir = os.path.dirname(os.path.abspath(audio_path))

    json_path = os.path.join(output_dir, "transcript_full.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    txt_path = os.path.join(output_dir, "transcript_timestamped.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"[Audio Duration: {duration:.0f}s]\n\n")
        for seg in segments:
            start_t = seg.get("start", 0)
            end_t = seg.get("end", 0)
            seg_text = seg.get("text", "").strip()
            if seg_text:
                start_m, start_s = int(start_t) // 60, int(start_t) % 60
                end_m, end_s = int(end_t) // 60, int(end_t) % 60
                f.write(f"[{start_m:02d}:{start_s:02d} - {end_m:02d}:{end_s:02d}] {seg_text}\n")

    print(f"Saved: {json_path}", flush=True)
    print(f"Saved: {txt_path}", flush=True)

    summary_path = os.path.join(output_dir, "transcript_timeline.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        for seg in segments:
            start_t = seg.get("start", 0)
            seg_text = seg.get("text", "").strip()
            if seg_text:
                start_m, start_s = int(start_t) // 60, int(start_t) % 60
                preview = seg_text[:60] + ("..." if len(seg_text) > 60 else "")
                f.write(f"[{start_m:02d}:{start_s:02d}] {preview}\n")

    print(f"Saved: {summary_path}", flush=True)

    words_path = os.path.join(output_dir, "transcript_words.json")
    all_words = []
    for seg in segments:
        for w in seg.get("words", []):
            all_words.append({
                "word": w.get("word", ""),
                "start": round(w.get("start", 0), 2),
                "end": round(w.get("end", 0), 2),
                "probability": round(w.get("probability", 0), 3),
            })
    if all_words:
        with open(words_path, "w", encoding="utf-8") as f:
            json.dump(all_words, f, ensure_ascii=False, indent=2)
        print(f"Saved: {words_path} ({len(all_words)} words)", flush=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="interview-coach: 面试录音转写")
    parser.add_argument("audio_file", help="音频文件路径")
    parser.add_argument(
        "--engine", default="auto",
        choices=["auto", "mlx", "faster-whisper", "sensevoice"],
        help="转写引擎: auto(自动) / mlx(macOS Metal) / faster-whisper(跨平台) / sensevoice(macOS可选)",
    )
    parser.add_argument("--model", default="medium",
                        help="Whisper 模型: medium(默认) / large-v3-turbo / small / tiny")
    parser.add_argument("--language", default="zh", help="语言代码 (默认 zh)")
    parser.add_argument("--device", default="auto",
                        help="计算设备 (faster-whisper): auto / cpu / cuda")
    parser.add_argument("--compute-type", default="auto",
                        help="计算精度 (faster-whisper): auto / int8 / float16 / float32")
    args = parser.parse_args()

    if not os.path.exists(args.audio_file):
        print(f"Error: file not found: {args.audio_file}", file=sys.stderr)
        sys.exit(1)

    engine = args.engine
    if engine == "auto":
        engine = detect_best_engine()

    if engine == "mlx":
        result, elapsed = transcribe_whisper_mlx(args.audio_file, args.model, args.language)
    elif engine == "faster-whisper":
        result, elapsed = transcribe_whisper_faster(
            args.audio_file, args.model, args.language,
            args.device, args.compute_type,
        )
    elif engine == "sensevoice":
        result, elapsed = transcribe_sensevoice(args.audio_file)
    else:
        print(f"Unknown engine: {engine}", file=sys.stderr)
        sys.exit(1)

    save_results(result, elapsed, args.audio_file)
