#!/usr/bin/env python3
"""
interview-coach: 按时间戳列表切分音频片段

用法:
  # 从 JSON 边界文件切分
  python3 scripts/split_audio.py audio.mp3 --boundaries boundaries.json

  # 手动指定边界（每个片段 start end label）
  python3 scripts/split_audio.py audio.mp3 --pairs "0:00-2:30 Q1" "2:30-5:45 Q2" "5:45-10:00 Q3"

  # 查看边界文件格式后手动编辑
  python3 scripts/split_audio.py audio.mp3 --boundaries boundaries.json --dry-run
"""

import argparse
import json
import os
import subprocess
import sys
import re


def parse_timestamp(ts: str) -> float:
    """将 MM:SS 或 H:MM:SS 转为秒数。"""
    parts = ts.split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    elif len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    raise ValueError(f"Invalid timestamp: {ts}")


def format_timestamp(seconds: float) -> str:
    """将秒数格式化为 MM:SS。"""
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def split_audio(audio_path: str, segments: list, output_dir: str):
    """按 segments 列表切分音频，返回片段信息。

    segments: [{"start": float, "end": float, "label": str, "title": str}]
    """
    os.makedirs(output_dir, exist_ok=True)
    results = []

    for i, seg in enumerate(segments):
        start = seg["start"]
        end = seg["end"]
        label = seg.get("label", f"segment_{i:02d}")
        title = seg.get("title", "")

        # 校验
        if end <= start:
            print(f"  Warning: skipping {label} (end <= start)", flush=True)
            continue

        duration = end - start
        output_path = os.path.join(output_dir, f"{label}.mp3")

        # 统一输出 MP3（libmp3lame，通用性最好）
        cmd = [
            "ffmpeg", "-y", "-i", audio_path,
            "-ss", str(start), "-to", str(end),
            "-c:a", "libmp3lame", "-b:a", "128k",
            "-ar", "44100", "-ac", "1",
            output_path,
        ]
        subprocess.run(cmd, capture_output=True)

        info = {
            "label": label,
            "title": title,
            "start": start,
            "end": end,
            "duration": round(duration, 1),
            "start_ts": format_timestamp(start),
            "end_ts": format_timestamp(end),
            "path": output_path,
        }
        results.append(info)
        print(f"  [{i+1}/{len(segments)}] {label}: {format_timestamp(start)} - {format_timestamp(end)} ({duration:.0f}s) -> {output_path}", flush=True)

    # 保存切分清单
    manifest_path = os.path.join(output_dir, "segments_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nManifest: {manifest_path}", flush=True)

    return results


def parse_cli_pairs(pairs: list) -> list:
    """解析命令行传入的边界对。"""
    segments = []
    for i, pair in enumerate(pairs):
        match = re.match(r"(\d+:\d+(?::\d+)?)-(\d+:\d+(?::\d+)?)\s+(.+)", pair)
        if not match:
            print(f"Warning: skipping invalid pair: {pair}", file=sys.stderr)
            continue
        start = parse_timestamp(match.group(1))
        end = parse_timestamp(match.group(2))
        label = f"Q{i+1:02d}"
        title = match.group(3).strip()
        segments.append({"start": start, "end": end, "label": label, "title": title})
    return segments


def load_boundaries_file(path: str) -> list:
    """加载边界 JSON 文件。

    格式:
    [
      {"start": 0.0, "end": 150.0, "question": "自我介绍"},
      {"start": 150.0, "end": 480.0, "question": "项目经验"}
    ]
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    segments = []
    for i, item in enumerate(data):
        segments.append({
            "start": item["start"],
            "end": item["end"],
            "label": item.get("label", f"Q{i+1:02d}"),
            "title": item.get("question", item.get("title", "")),
        })
    return segments


def generate_boundaries_template(audio_path: str):
    """生成边界 JSON 模板，供用户手动编辑。"""
    duration_cmd = [
        "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
        "-of", "csv=p=0", audio_path,
    ]
    duration = float(subprocess.run(duration_cmd, capture_output=True, text=True).stdout.strip())

    total_m = int(duration) // 60
    template = [
        {"start": 0, "end": duration / 3, "question": "Q1 问题标题"},
        {"start": duration / 3, "end": duration * 2 / 3, "question": "Q2 问题标题"},
        {"start": duration * 2 / 3, "end": duration, "question": "Q3 问题标题"},
    ]
    return template


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="interview-coach: 按时间戳切分音频")
    parser.add_argument("audio_file", help="音频文件路径")
    parser.add_argument("--boundaries", help="边界 JSON 文件")
    parser.add_argument("--pairs", nargs="+", help='边界对: "MM:SS-MM:SS 标题"')
    parser.add_argument("--output", default="segments", help="输出目录 (默认 segments)")
    parser.add_argument("--dry-run", action="store_true", help="预览边界，不切分")
    args = parser.parse_args()

    if not os.path.exists(args.audio_file):
        print(f"Error: file not found: {args.audio_file}", file=sys.stderr)
        sys.exit(1)

    # 确定边界来源
    if args.boundaries:
        segments = load_boundaries_file(args.boundaries)
    elif args.pairs:
        segments = parse_cli_pairs(args.pairs)
    else:
        # 生成模板
        template = generate_boundaries_template(args.audio_file)
        template_path = "boundaries_template.json"
        with open(template_path, "w", encoding="utf-8") as f:
            json.dump(template, f, ensure_ascii=False, indent=2)
        print(f"Boundaries template -> {template_path}")
        print("Edit it, then re-run with: --boundaries boundaries_template.json")
        sys.exit(0)

    if args.dry_run:
        print("=== Boundary Preview ===")
        total_duration = 0
        for seg in segments:
            dur = seg["end"] - seg["start"]
            total_duration += dur
            print(f"  {seg.get('label', '?')} | {format_timestamp(seg['start'])} - {format_timestamp(seg['end'])} ({dur:.0f}s) | {seg.get('title', '')}")
        print(f"Total: {len(segments)} segments, {total_duration:.0f}s")
        sys.exit(0)

    output_dir = os.path.join(os.path.dirname(os.path.abspath(args.audio_file)), args.output)
    split_audio(args.audio_file, segments, output_dir)
