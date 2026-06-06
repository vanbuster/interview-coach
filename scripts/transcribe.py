#!/usr/bin/env python3
"""
interview-coach: 音频转写脚本 — Apple Silicon 原生 (MLX)

将面试录音转写为带时间戳的文本，支持两种引擎：
  - whisper (默认): mlx-whisper，词级时间戳 (~20ms 精度)，原生支持长音频
  - sensevoice: SenseVoiceSmall，中文语音识别，无内部时间戳

用法:
  python3 scripts/transcribe.py <audio_file>
  python3 scripts/transcribe.py <audio_file> --model large-v3-turbo
  python3 scripts/transcribe.py <audio_file> --engine sensevoice
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
        start += chunk_duration - overlap  # overlap window
    return chunks, duration


def transcribe_sensevoice_chunk(chunk_path: str, chunk_start: float, chunk_end: float):
    """转写单个 SenseVoice 切片，返回带时间戳的片段。"""
    from mlx_audio.stt.generate import generate_transcription

    result = generate_transcription(model="mlx-community/SenseVoiceSmall", audio=chunk_path)

    text = ""
    if hasattr(result, "text") and result.text:
        text = result.text
    elif hasattr(result, "segments") and result.segments:
        text = " ".join(s.get("text", "") for s in result.segments if s.get("text"))

    # SenseVoice 返回整段无内部时间戳，我们用 chunk 边界作为时间戳
    return [{"start": chunk_start, "end": chunk_end, "text": text}]


def merge_chunk_texts(chunks_with_text, overlap_seconds: int = 30):
    """合并重叠切片文本。

    SenseVoice 每个切片返回整段文本（无内部时间戳），
    简单策略：每个切片取非重叠部分的文本比例，拼接。
    重叠比例 = overlap_seconds / chunk_duration ≈ 12.5%
    """
    if not chunks_with_text:
        return [], ""

    ratio_skip = overlap_seconds / (chunks_with_text[0]["end"] - chunks_with_text[0]["start"]) if chunks_with_text else 0

    all_segments = []
    text_parts = []

    for i, chunk in enumerate(chunks_with_text):
        txt = chunk.get("text", "").strip()
        if not txt:
            continue

        # 第一个切片取全文，后续切片跳过重叠部分
        if i == 0:
            clean = txt
        else:
            # 跳过开头 ~12.5% 字符（对应重叠区）
            skip = int(len(txt) * ratio_skip)
            clean = txt[skip:]

        if clean.strip():
            text_parts.append(clean.strip())
            all_segments.append({
                "start": chunk["start"],
                "end": chunk["end"],
                "text": clean.strip(),
            })

    full_text = " ".join(text_parts)
    return all_segments, full_text


def transcribe_sensevoice(audio_path: str):
    """SenseVoice 转写：短音频直接转，长音频自动 overlap 切片。"""
    from mlx_audio.stt.generate import generate_transcription

    duration = get_audio_duration(audio_path)
    chunk_duration = 240  # 4 分钟切片（安全 Metal 内存）
    overlap = 30  # 30 秒重叠

    print(f"Audio duration: {duration:.0f}s", flush=True)
    print(f"Engine: SenseVoice (MLX)", flush=True)
    print(f"Model: mlx-community/SenseVoiceSmall", flush=True)

    if duration <= chunk_duration:
        print("Short audio — direct transcription", flush=True)
        start_t = time.time()
        result = generate_transcription(model="mlx-community/SenseVoiceSmall", audio=audio_path)
        elapsed = time.time() - start_t
        print(f"Completed in {elapsed:.1f}s", flush=True)

        segments = []
        if hasattr(result, "segments") and result.segments:
            for seg in result.segments:
                segments.append({
                    "start": seg.get("start", 0),
                    "end": seg.get("end", 0),
                    "text": seg.get("text", ""),
                })
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
        # 清理临时切片
        for chunk in chunks:
            if os.path.exists(chunk["path"]):
                os.remove(chunk["path"])
        if os.path.isdir(tmp_dir):
            os.rmdir(tmp_dir)


def transcribe_whisper(audio_path: str, model: str = "medium", language: str = "zh"):
    """Whisper 转写（原生支持长音频，无需切片）。"""
    import mlx_whisper

    # 支持 4bit 后缀自动映射到量化仓库
    if model.endswith("-4bit"):
        hf_repo = f"mlx-community/whisper-{model}"
    else:
        hf_repo = f"mlx-community/whisper-{model}"
    print(f"Engine: mlx-whisper", flush=True)
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
    parser = argparse.ArgumentParser(description="interview-coach: 面试录音转写 (Apple Silicon)")
    parser.add_argument("audio_file", help="音频文件路径")
    parser.add_argument(
        "--engine", default="whisper", choices=["whisper", "sensevoice"],
        help="转写引擎: whisper(默认,词级时间戳) / sensevoice(无时间戳)",
    )
    parser.add_argument("--model", default=None,
                        help="Whisper 模型: medium(默认,中文质量好) / large-v3-turbo(更快) / small / tiny")
    parser.add_argument("--language", default="zh", help="Whisper 语言代码 (默认 zh)")
    args = parser.parse_args()

    if not os.path.exists(args.audio_file):
        print(f"Error: file not found: {args.audio_file}", file=sys.stderr)
        sys.exit(1)

    if args.engine == "sensevoice":
        result, elapsed = transcribe_sensevoice(args.audio_file)
    else:
        model = args.model or "medium"
        result, elapsed = transcribe_whisper(args.audio_file, model, args.language)

    save_results(result, elapsed, args.audio_file)
