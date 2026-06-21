# Interview Coach — AI 面试复盘教练

> 面试录音 → 结构化复盘文档，逐题提供更优解建议，音频与内容精确对应
>
> **v0.1.0** · MIT License · 跨平台（macOS / Linux / Windows）

## 这是什么

Interview Coach 是一个 **AI Agent Skill**，把面试录音自动转化为结构化复盘文档。通过 Whisper 词级时间戳精确定位每个问答转折点，按内容边界切分音频，最终生成带内嵌音频播放器的交互式复盘文档——每段音频与对应问答完全对应。

**核心价值**：告别手动听录音做笔记，30 分钟面试 5 分钟出复盘。

---

## 🚀 复制即用（两步到位）

### Step 1 · 安装 Skill（仅首次）

复制以下命令到终端，一行完成克隆 + 装依赖：

```bash
git clone https://github.com/vanbuster/interview-coach.git ~/.claude/skills/interview-coach && \
  cd ~/.claude/skills/interview-coach && \
  bash setup.sh
```

> Windows 用户把最后一行换成：`powershell -ExecutionPolicy Bypass -File setup.ps1`

**前提条件**：Python 3.10+。`setup.sh` 会自动安装 ffmpeg、Whisper 引擎、首次下载模型缓存。macOS 自动启用 mlx-whisper（Metal 加速）。

### Step 2 · 把下面这段话粘贴给你的 AI Agent

> **替换路径为你的面试素材文件夹**（支持音频 / JD 图片 / 笔记 PDF 混合放置），Agent 会自动完成全流程：

```
用 interview-coach skill 帮我处理这次面试复盘。

素材文件夹：/path/to/智科谷面试/

执行完整流程：
1. 自动扫描文件夹里的所有素材（音频 .mp3/.m4a/.wav、JD 图片、面试笔记 PDF/TXT）
2. 用 Whisper 本地转写音频，生成完整文本 + 词级时间戳（不消耗 LLM Token）
3. 识别每个问答的边界关键句，在词级索引中精确定位到 0.1s
4. 按边界切分音频，输出 segments/Q01.mp3, Q02.mp3, ...
5. 结合 JD 要求，逐题生成「我的回答 + 评估 + 更优解」结构化复盘
6. 输出交互式复盘文档：每个 Q&A 章节内嵌可播放的录音片段
   - 飞书云文档（需 lark-cli 已登录）：在线协作 + 公开链接分享
   - HTML 网页（零依赖）：本地浏览器打开，可 zip 打包分享

全流程零打断，遇到决策点主动询问；首次运行后自动记住偏好（输出渠道/模型/语言），下次只需提供文件夹路径即可。
```

**就这么简单。** Agent 会按 [SKILL.md](./SKILL.md) 的协议自动执行。

---

## 使用方法（详细版）

### 首次运行

把 Step 2 的提示词粘贴给 Agent，并替换路径。Agent 会问你输出渠道（飞书/HTML），完成后自动保存偏好到 `user_config.json`。

### 后续运行

只需提供素材文件夹路径：

```
面试复盘，素材在 /path/to/恒聚愿景面试/
```

Agent 自动加载偏好（首次选了 HTML → 后续都用 HTML，直到你说「切换输出渠道」）。

### 任何 AI Agent 都能用

只要 Agent 能执行 shell 命令 + 读写文件，就可以使用本 Skill：

- **Claude Code**：clone 到 `~/.claude/skills/interview-coach` 即自动识别
- **其他 Agent**（Hermes、Codex、Cursor、Cline 等）：把 [SKILL.md](./SKILL.md) 作为 system prompt 或工具描述注入，脚本路径指向 `scripts/` 即可

---

## Reflection 机制（偏好记忆）

| 运行次数 | 用户输入 | Agent 行为 |
|---------|---------|-----------|
| **首次** | 素材文件夹路径 + 选择输出渠道 | 执行全流程，自动保存偏好到 `user_config.json` |
| **后续** | 只提供素材文件夹路径 | 自动加载偏好，全流程零询问 |

偏好存储在 skill 目录的 `user_config.json`（被 `.gitignore` 排除，不上传仓库）：

```json
{
  "version": 1,
  "output_channel": "html",
  "language": "zh",
  "model": "medium",
  "device": "auto",
  "compute_type": "auto",
  "feishu_folder_token": "",
  "local_archive_dir": "",
  "ammo_doc_id": "",
  "run_count": 3,
  "first_run": "2026-06-01",
  "last_run": "2026-06-06"
}
```

说「切换输出渠道」即可更改，自动保存。

---

## 交付物

### 飞书云文档

音频片段内嵌到飞书文档中，每个问答章节包含可播放的内联音频播放器。支持在线播放、协作评论、权限分享。

**前置**：`npm install -g lark-cli && lark-cli auth login`

### HTML 网页（零依赖，离线可用）

自包含的 HTML 文件，每题配有 `<audio>` 播放器，浏览器直接打开即可查看和播放。分享时 zip 打包 `HTML + segments/` 文件夹即可。

### 产物归档

首次运行会询问两个归档位置并写入 `user_config.json`，之后自动复用：

- **`feishu_folder_token`**：飞书归档文件夹。飞书文档不再散落云盘根目录，统一创建在该文件夹下（`docs +create --folder-token`）。
- **`local_archive_dir`**：本地产物归档根目录。流程末尾把 `segments/`、转写、复盘、录音移入 `<local_archive_dir>/<公司_岗位_日期>/` 子目录（不打包 zip）。
- **`ammo_doc_id`**：面试弹药库飞书文档 token。配置后，每次复盘末尾 **Phase 7** 自动检测新亮点（新数据 / 新话术 / 新问题类型）→ 询问用户确认 → 智能追加到对应弹药或数据卡，让话术库随实战持续进化。为空则跳过。

---

## 工作流程

```
面试录音
  ↓
[Whisper 本地转写]   → 完整文本 + 词级时间戳（~20ms 精度）
  ↓
[LLM 识别问答边界]   → 在词级索引中搜索转折关键句，精确定位到 0.1s
  ↓
[按边界切分音频]     → segments/Q01.mp3, Q02.mp3, ...
  ↓
[LLM 生成复盘内容]   → 结合 JD，逐题给出更优解建议
  ↓
[输出交付]           → 飞书云文档 或 HTML 网页
  ↓
[保存偏好]           → 自动记住输出渠道、模型等选择
```

**核心优势**：Whisper 的词级时间戳（~20ms 精度）让问答边界定位精确到秒。实测 33 分钟中文面试，9 个转折点全部精确定位，误差 <0.1s。

---

## 引擎自动选择

`transcribe.py` 自动检测最佳引擎，无需手动配置：

| 平台 | 引擎 | 加速 | 安装方式 |
|------|------|------|---------|
| **macOS Apple Silicon** | **mlx-whisper（必选）** | **Metal GPU** | `setup.sh` 自动安装 |
| Linux | faster-whisper (CTranslate2) | CPU INT8 | `setup.sh` 自动安装 |
| Linux (NVIDIA GPU) | faster-whisper (CTranslate2) | CUDA FP16 | 加 `--device cuda --compute-type float16` |
| Windows | faster-whisper (CTranslate2) | CPU INT8 | `setup.ps1` 自动安装 |

macOS 上 mlx-whisper 是经过实测的最佳实践：33 分钟面试仅需 1.5 分钟转写，词级时间戳精度 ~20ms。

也可以手动指定引擎：

```bash
python3 scripts/transcribe.py audio.mp3 --engine mlx              # 强制 mlx-whisper
python3 scripts/transcribe.py audio.mp3 --engine faster-whisper   # 强制 faster-whisper
python3 scripts/transcribe.py audio.mp3 --engine sensevoice       # SenseVoice（macOS，无词级时间戳）
```

---

## 依赖

| 工具 | 必需 | 安装 |
|------|------|------|
| ffmpeg | ✅ | `brew install ffmpeg` / `apt install ffmpeg` / `winget install Gyan.FFmpeg` |
| Python 3.10+ | ✅ | 系统包管理器 |
| mlx-whisper | ✅ macOS | `setup.sh` 自动安装（Metal 加速，最佳实践） |
| faster-whisper | ✅ Linux/Win | `setup.sh` / `setup.ps1` 自动安装 |
| mlx-audio | ❌ macOS | `setup.sh` 自动安装（SenseVoice 备选） |
| lark-cli | ❌ 可选 | `npm install -g lark-cli && lark-cli auth login` |

---

## 项目结构

```
interview-coach/
├── SKILL.md                          # Agent 执行指令（核心，Agent 必读）
├── README.md                         # 本文件
├── LICENSE                           # MIT
├── CHANGELOG.md                      # 版本变更记录
├── setup.sh                          # macOS / Linux 一键安装
├── setup.ps1                         # Windows 一键安装
├── requirements.txt                  # Python 依赖（已锁版本）
├── user_config.example.json          # 偏好配置参考模板
├── .gitignore
├── .github/
│   └── workflows/ci.yml              # CI：macOS + Linux 冒烟测试
├── tests/
│   └── test_split_audio.py           # split_audio.py 冒烟测试
├── scripts/
│   ├── transcribe.py                 # 音频转写（自动引擎检测）
│   └── split_audio.py                # 按边界切分音频
├── templates/
│   ├── interview-review-template.md  # Markdown 模板
│   └── interview-review-template.html # HTML 模板（含音频播放器）
└── references/                       # 参考资料（含模型选型报告）
    ├── asr-model-comparison.md
    └── skill-writing-methodology.md
```

---

## 模型选型

经过 33 分钟中文面试音频实测（完整报告见 [references/asr-model-comparison.md](./references/asr-model-comparison.md)）：

| 模型 | 转写耗时 | 时间戳精度 | 中文质量 |
|------|---------|-----------|---------|
| **MLX Whisper medium** | **1.5 min** | **词级 ~20ms** | **优** |
| MLX Whisper large-v3-turbo | 1.3 min | 词级 ~20ms | 开头幻觉 |
| FunASR Paraformer + CAM++ | 6.1 min | 句级 ~100ms | 优（但前 48s 丢失） |

MLX Whisper medium 是当前最佳实践：速度最快、时间戳最精确、中文质量最优。

---

## 开发

```bash
# 跑冒烟测试
python -m pip install pytest
python -m pytest tests/ -v

# 升级依赖后更新锁版本
pip install --upgrade faster-whisper
pip show faster-whisper | grep Version  # 用这个版本号更新 requirements.txt
```

提交规范遵循 [Conventional Commits](https://www.conventionalcommits.org/)（`feat:` / `fix:` / `docs:` 等），见 [CHANGELOG.md](./CHANGELOG.md)。

---

## License

[MIT](./LICENSE) © 2026 vanbuster
