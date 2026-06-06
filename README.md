# Interview Coach — AI 面试复盘教练 (Windows / Linux / macOS)

> 面试录音 → 结构化复盘文档，逐题提供更优解建议，音频与内容精确对应

## 这是什么

Interview Coach 是一个 **AI Agent Skill**，将面试录音自动转化为结构化复盘文档。它通过 Whisper 词级时间戳精确定位每个问答转折点，按内容边界切分音频，最终生成带内嵌音频播放器的交互式复盘文档——每段音频与对应的问答内容完全对应。

**本分支** (`windows`) 使用 `faster-whisper` (CTranslate2) 替代 `mlx-whisper`，支持 Windows / Linux / macOS 全平台，且支持 NVIDIA GPU 加速。

**macOS Apple Silicon 用户**：建议使用 `main` 分支（mlx-whisper 原生加速）。

## 快速开始

### 安装

```bash
git clone -b windows https://github.com/vanbuster/interview-coach.git
cd interview-coach

# Windows
powershell -ExecutionPolicy Bypass -File setup.ps1

# Linux / macOS
bash setup.sh
```

**前提条件**：Python 3.10+

### 使用

**首次运行**：选择输出渠道（飞书/HTML），偏好自动保存。

```
"面试复盘，素材在 /path/to/智科谷/"
```

Agent 自动扫描文件夹：识别音频文件、JD 图片、面试笔记，全流程自动执行。

**后续运行**：只需提供文件夹路径，不再重复询问。首次选了 HTML → 后续都用 HTML，直到你说「切换输出渠道」。

## Reflection 机制

面试复盘工具会**记住你的偏好**，越用越省事：

| 运行次数 | 用户输入 | Agent 行为 |
|---------|---------|-----------|
| **首次** | 素材文件夹路径 + 选择输出渠道 | 执行全流程，自动保存偏好到 `user_config.json` |
| **后续** | 只提供素材文件夹路径 | 自动加载偏好，全流程零询问 |

偏好存储在项目根目录的 `user_config.json`（被 `.gitignore` 排除，不上传仓库）：

```json
{
  "version": 1,
  "output_channel": "html",
  "language": "zh",
  "model": "medium",
  "device": "auto",
  "compute_type": "auto",
  "run_count": 3,
  "first_run": "2026-06-01",
  "last_run": "2026-06-06"
}
```

说「切换输出渠道」即可更改偏好，更改后自动保存。

## 使用方法

### 方式一：Clone 完整仓库（推荐）

```bash
git clone -b windows https://github.com/vanbuster/interview-coach.git
cd interview-coach
# Windows: powershell -ExecutionPolicy Bypass -File setup.ps1
# Linux:   bash setup.sh
```

### 方式二：作为 Agent Skill 使用

只需将 `SKILL.md` + `scripts/` + `templates/` 交给你的 AI Agent：

```bash
# Claude Code
cp -r . ~/.claude/skills/interview-review-coach

# 其他 Agent（Hermes、Codex、Cursor 等）
# 将 SKILL.md 作为 system prompt 或工具描述注入，脚本路径指向 scripts/ 目录即可
```

**支持任何能执行 shell 命令和读写文件的 AI Agent**。

## 交付物

复盘文档有两种输出格式：

### 飞书云文档

音频片段内嵌到飞书文档中，每个问答章节包含可播放的内联音频播放器。支持在线播放、协作评论、权限分享。

### HTML 网页（本地保存）

自包含的 HTML 文件，每题配有 `<audio>` 播放器，浏览器直接打开即可查看和播放音频。**零外部依赖，离线可用。**

## 工作流程

```
面试录音
  ↓
[Whisper 本地转写] → 完整文本 + 词级时间戳（~20ms 精度）
  ↓
[LLM 识别问答边界] → 在词级索引中搜索转折关键句，精确定位到 0.1s
  ↓
[按边界切分音频]   → segments/Q01.mp3, Q02.mp3, ...
  ↓
[LLM 生成复盘内容] → 结合 JD，逐题给出更优解建议
  ↓
[输出交付]         → 飞书云文档 或 HTML 网页
  ↓
[保存偏好]         → 自动记住输出渠道、模型、设备等选择
```

## GPU 加速

默认使用 CPU + INT8 量化。如果你有 NVIDIA GPU：

```bash
python scripts/transcribe.py interview.mp3 --device cuda --compute-type float16
```

GPU 加速可将转写速度提升 3-5 倍。

## 依赖

| 工具 | 必需 | 安装 |
|------|------|------|
| ffmpeg | ✅ | `winget install Gyan.FFmpeg` / `apt install ffmpeg` |
| Python 3.10+ | ✅ | python.org 或系统包管理器 |
| faster-whisper | ✅ | setup 脚本自动安装 |
| lark-cli | ❌ 可选 | `npm install -g lark-cli && lark-cli auth login` |

## 项目结构

```
interview-coach/
├── SKILL.md                          # Agent 执行指令（核心）
├── README.md                         # 本文件
├── setup.ps1                         # Windows 一键安装
├── setup.sh                          # Linux/macOS 一键安装
├── requirements.txt                  # Python 依赖
├── user_config.example.json          # 偏好配置参考模板
├── .gitignore
├── scripts/
│   ├── transcribe.py                 # 音频转写（faster-whisper 词级时间戳）
│   └── split_audio.py                # 按边界切分音频
├── templates/
│   ├── interview-review-template.md  # Markdown 模板
│   └── interview-review-template.html # HTML 模板（含音频播放器）
├── references/                       # 参考资料（含模型选型报告）
```

## 分支

| 分支 | 平台 | 引擎 | GPU |
|------|------|------|-----|
| **main** | macOS Apple Silicon | mlx-whisper | Metal |
| **windows** | Windows / Linux / macOS | faster-whisper (CTranslate2) | NVIDIA CUDA / CPU |

两个分支使用相同的 Whisper 模型权重，输出格式完全一致。

## License

MIT
