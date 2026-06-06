# Interview Coach — AI 面试复盘教练

> 面试录音 → 结构化复盘文档，逐题提供更优解建议，音频与内容精确对应

## 这是什么

Interview Coach 是一个 **AI Agent Skill**，将面试录音自动转化为结构化复盘文档。它通过 Whisper 词级时间戳精确定位每个问答转折点，按内容边界切分音频，最终生成带内嵌音频播放器的交互式复盘文档——每段音频与对应的问答内容完全对应。

核心价值：**告别手动听录音做笔记，30 分钟面试 5 分钟出复盘。**

## 使用方法

### 方式一：Clone 完整仓库（推荐，含最佳模型实践）

```bash
git clone https://github.com/vanbuster/interview-coach.git
cd interview-coach
bash setup.sh
```

`setup.sh` 一键安装所有依赖：ffmpeg、Python 包、Whisper medium 模型（~489MB，首次下载缓存）。

**前提条件**：macOS Apple Silicon (M1/M2/M3/M4) + Python 3.10+

### 方式二：只下载 Skill，配合任意 Agent 使用

只需将 `SKILL.md` + `scripts/` + `templates/` 交给你的 AI Agent：

```bash
# Claude Code
cp -r . ~/.claude/skills/interview-review-coach

# 其他 Agent（Hermes、Codex 等）
# 将 SKILL.md 作为 system prompt 或工具描述注入，脚本路径指向 scripts/ 目录即可
```

然后对 Agent 说：

> "面试复盘，录音文件在 /path/to/interview.m4a"

Agent 会自动执行：转写 → 识别问答边界 → 切分音频 → 生成复盘文档。

**支持任何能执行 shell 命令和读写文件的 AI Agent**（Claude Code、Hermes、Codex、Cursor 等）。

## 交付物

复盘文档有两种输出格式，运行时由用户选择：

### 飞书云文档

音频片段内嵌到飞书文档中，每个问答章节包含可播放的内联音频播放器。支持在线播放、协作评论、权限分享。

需安装 `lark-cli` 并完成飞书登录认证。

### HTML 网页（本地保存）

自包含的 HTML 文件，每题配有 `<audio>` 播放器，浏览器直接打开即可查看和播放音频。分享时 zip 打包 HTML + segments 文件夹即可。

**零外部依赖，离线可用。**

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
```

**核心优势**：Whisper 的词级时间戳（~20ms 精度）使问答边界定位精确到秒。实测 33 分钟中文面试，9 个转折点全部精确定位，误差 <0.1s。

## 依赖

| 工具 | 必需 | 安装 |
|------|------|------|
| ffmpeg | ✅ | `brew install ffmpeg`（setup.sh 自动检测） |
| Python 3.10+ | ✅ | 系统预装 |
| mlx-whisper | ✅ | `setup.sh` 自动安装 |
| lark-cli | ❌ 可选 | `npm install -g lark-cli && lark-cli auth login` |

## 项目结构

```
interview-coach/
├── SKILL.md                          # Agent 执行指令（核心）
├── README.md                         # 本文件
├── setup.sh                          # 一键安装
├── requirements.txt                  # Python 依赖
├── .gitignore
├── scripts/
│   ├── transcribe.py                 # 音频转写（Whisper 词级时间戳）
│   └── split_audio.py                # 按边界切分音频
├── templates/
│   ├── interview-review-template.md  # Markdown 模板
│   └── interview-review-template.html # HTML 模板（含音频播放器）
├── references/                       # 参考资料
└── docs/                             # 模型选型报告
```

## 模型选型

经过 33 分钟中文面试音频实测（完整报告见 `docs/实测选型报告.md`）：

| 模型 | 转写耗时 | 时间戳精度 | 中文质量 |
|------|---------|-----------|---------|
| **MLX Whisper medium** | **1.5 min** | **词级 ~20ms** | **优** |
| MLX Whisper large-v3-turbo | 1.3 min | 词级 ~20ms | 开头幻觉 |
| FunASR Paraformer + CAM++ | 6.1 min | 句级 ~100ms | 优（但前 48s 丢失） |

MLX Whisper medium 是当前最佳实践：速度最快、时间戳最精确、中文质量最优。

## License

MIT
