#!/usr/bin/env python3
"""
interview-coach: 音频转写脚本 — Windows / Linux / macOS (faster-whisper)

将面试录音转写为带时间戳的文本：
  - whisper (默认): faster-whisper (CTranslate2)，词级时间戳 (~20ms 精度)
  - 支持 CPU (INT8) 和 NVIDIA GPU (CUDA)

用法:
  python scripts/transcribe.py <audio_file>
  python scripts/transcribe.py <audio_file> --model large-v3-turbo
  python scripts/transcribe.py <audio_file> --device cuda --compute-type float16
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


def transcribe_whisper(
    audio_path: str,
    model: str = "medium",
    language: str = "zh",
    device: str = "auto",
    compute_type: str = "auto",
):
    """Whisper 转写（faster-whisper / CTranslate2 后端，跨平台）。"""
    from faster_whisper import WhisperModel

    # 自动选择设备和精度
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

    # Collect segments into same format as mlx-whisper output
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


def save_results(result, elapsed: float, audio_path: str):
    """保存转写结果为 JSON 和带时间戳的文本。"""
    text = result.get("text", "")
    segments = result.get("segments", [])
    duration = get_audio_duration(audio_path)

    print(f"\nCompleted: {len(segments)} segments, {len(text)} chars, {elapsed:.1f}s", flush=True)

    output_dir = os.path.dirname(os.path.abspath(audio_path))

    # 完整 JSON
    json_path = os.path.join(output_dir, "transcript_full.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 带时间戳文本
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

    # 时间轴摘要
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

    # 词级时间戳索引（Whisper word_timestamps 输出）
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="interview-coach: 面试录音转写 (faster-whisper)")
    parser.add_argument("audio_file", help="音频文件路径")
    parser.add_argument("--model", default="medium",
                        help="Whisper 模型: medium(默认,中文质量好) / large-v3-turbo / small / tiny")
    parser.add_argument("--language", default="zh", help="Whisper 语言代码 (默认 zh)")
    parser.add_argument("--device", default="auto",
                        help="计算设备: auto(自动检测) / cpu / cuda")
    parser.add_argument("--compute-type", default="auto",
                        help="计算精度: auto / int8(cpu) / float16(cuda) / float32")
    args = parser.parse_args()

    if not os.path.exists(args.audio_file):
        print(f"Error: file not found: {args.audio_file}", file=sys.stderr)
        sys.exit(1)

    result, elapsed = transcribe_whisper(
        args.audio_file, args.model, args.language,
        args.device, args.compute_type,
    )
    save_results(result, elapsed, args.audio_file)
