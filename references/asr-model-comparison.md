# ASR 引擎选型指南（面试复盘场景）

> 适用场景：面试录音 → 结构化复盘文档（含音频切分）
> 硬件：macOS Apple Silicon (M-series)
> 更新日期：2026-06-06
> 基于：33 分钟中文面试音频实测数据

## 1. 当前最佳实践

| 项目 | 值 |
|---|---|
| 引擎 | **MLX Whisper medium**（4-bit 量化） |
| 框架 | mlx-whisper |
| 模型大小 | ~489MB（缓存于 `~/.cache/huggingface/hub/`） |
| 转写速度 | **1.5 min / 30 min 音频**（21.8x 实时） |
| 时间戳精度 | **词级 ~20ms**（每个词有独立 start/end） |
| 中文质量 | 优（9370 字转写，7263 词带时间戳） |

**核心能力**：`word_timestamps=True` 为每个词提供精确起止时间，使 LLM 能在词级索引中搜索问答转折关键句，边界精度 <0.1s。

## 2. 为什么不用其他方案

### SenseVoice（不推荐用于面试复盘）

- 无内部时间戳，只返回整段文本
- 长音频需要手动切片 + 重叠拼接，边界只能靠字符比例估算（误差 ±100s）
- 适合：短音频快速转写，不需要精确边界定位的场景

### FunASR Paraformer + CAM++（不推荐）

实测问题清单：

| 问题 | 详情 | 影响 |
|------|------|------|
| **前 48 秒音频丢失** | FSMN-VAD 对开场轻声寒暄检测失败 | 面试开场全部丢失 |
| 4x 慢于 Whisper | 6.1 min vs 1.5 min（PyTorch MPS 非原生） | 总流程超 10 分钟 |
| 内存 5-10x 高 | PyTorch 多模型加载（VAD+ASR+标点+分离） | 影响并发任务 |
| 无词级时间戳 | 只有句子级 start/end（~100ms） | 无法精确定位转折点 |

前 48 秒丢失是致命问题（VAD 阈值调优不具备生产稳定性），且无词级时间戳无法满足精确边界切分需求。

### Whisper large-v3-turbo（不推荐）

- 中文开头易出现幻觉循环（重复乱码）
- 速度提升有限（76.9s vs 90.4s），质量下降明显

## 3. 实测数据对比（33 分钟中文面试）

| 引擎 | 转写耗时 | 倍速 | 词级时间戳 | 标点 | 说话人分离 | 首句完整性 |
|------|---------|------|-----------|------|-----------|-----------|
| **MLX Whisper medium** | **90.4s** | **21.8x** | **✅ ~20ms** | ❌ | ❌（LLM 推断） | **✅ 完整** |
| MLX Whisper large-v3-turbo | 76.9s | 25.6x | ✅ ~20ms | ❌ | ❌ | ❌ 开头幻觉 |
| FunASR Paraformer + CAM++ | 367.5s | 5.4x | ❌ 句级 ~100ms | ✅ | ✅ | ❌ 前 48s 丢失 |
| SenseVoice | ~120s（估） | ~16x | ❌ 无 | ❌ | ❌ | ✅ |

## 4. 说话人分离：为什么不需要

面试复盘的核心诉求是**音频拆分精准**，不是自动识别说话人。

- Whisper 转写后，LLM 根据对话内容即可判断面试官/候选人角色
- 面试对话中角色切换模式清晰（提问→回答→追问→回答）
- 实测验证：LLM 推断说话人角色准确率足够满足复盘文档需求

如未来需要升级说话人分离能力，可选方案：Whisper + pyannote 3.1（DER ~10%，需 HF token）。

## 5. 安装与使用

```bash
# 安装
pip install mlx-whisper

# 转写（首次运行自动下载模型 ~489MB）
python3 scripts/transcribe.py interview.mp3

# 输出文件：
#   transcript_full.json      — 完整 JSON（含 word-level timestamps）
#   transcript_timestamped.txt — [MM:SS - MM:SS] 格式文本
#   transcript_timeline.txt   — 时间轴摘要
#   transcript_words.json     — 词级时间戳索引（用于精确边界定位）
```

## 6. 参考链接

- [mlx-whisper](https://github.com/ml-explore/mlx-whisper) — MLX Whisper 框架
- [mlx-community/whisper-medium](https://huggingface.co/mlx-community/whisper-medium) — 模型仓库
- [FunASR](https://github.com/modelscope/FunASR) — 阿里巴巴 FunASR（不推荐用于此场景）
- [pyannote speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1) — 可选说话人分离升级方案
