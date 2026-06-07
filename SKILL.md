---
name: interview-review-coach
description: AI Agent PM 面试复盘教练——从录音/笔记/JD 出发，生成结构化复盘文档，逐题提供更优解
when_to_use: |
  - 用户说"面试复盘"、"面试回顾"、"复盘这次面试"
  - 用户提供面试录音、笔记、JD 图片/文本等素材
  - 用户需要面试答面试题辅导或更优解建议
  - 触发关键词：面试、复盘、interview review、答面
---

# 面试复盘教练

> **项目主页**：`github.com/vanbuster/interview-coach`
> 所有脚本和模板在项目仓库中维护，本 Skill 为 Agent 执行指令。

## 工作流程

```
录音 → [本地转写] → 完整文本+时间戳 → [LLM 识别问答边界] → 按边界切音频
  → 生成复盘内容 → 创建飞书文档 或 HTML → 嵌入音频片段 → 交付
```

**核心原则**：先完整转写，再从文本中识别问答边界，最后按边界切音频。禁止先切音频再转写。

---

### Phase 0：环境检查 + 偏好加载

**环境检查**：

确认以下工具可用：
- `python3 scripts/transcribe.py --help` — 转写
- `python3 scripts/split_audio.py --help` — 切分
- `ffmpeg -version` — 音频处理

如缺少依赖，运行安装脚本：
- macOS / Linux：`bash setup.sh`
- Windows：`powershell -ExecutionPolicy Bypass -File setup.ps1`

**偏好加载（Reflection 机制）**：

检查项目根目录是否存在 `user_config.json`：

```bash
cat user_config.json 2>/dev/null
```

- **如果存在** → 加载已保存偏好（`output_channel` / `model` / `language` / `device` / `compute_type`），后续 Phase 跳过对应询问
- **如果不存在** → 标记为首次运行，后续流程中会询问偏好并保存

配置文件格式：
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

**偏好优先级**：用户本次输入 > user_config.json > 默认值

检测输出通道（决定 Phase 5 用哪种格式）：
- `command -v lark-cli` — 如果可用 → 飞书输出（Tier 1）
- 否则 → HTML 输出（Tier 2，零依赖降级）

---

### Phase 1：信息采集（文件夹扫描）

**核心改进**：用户只需提供素材文件夹路径，Agent 自动扫描识别所有素材。

1. **接受输入**：
   - 文件夹路径（如 `/path/to/智科谷/` 或 `C:\Users\...\智科谷\`）
   - 或逐个文件路径（向后兼容）

2. **自动扫描文件夹**（如果提供了文件夹路径）：

   ```bash
   # 扫描音频文件
   ls /path/to/folder/*.{mp3,m4a,wav,qta} 2>/dev/null
   # 扫描 JD 图片
   ls /path/to/folder/*.{png,jpg,jpeg} 2>/dev/null
   # 扫描面试笔记
   ls /path/to/folder/*.{pdf,txt,md} 2>/dev/null
   ```

   **扫描规则**：
   - **音频**（必须）：
     - 恰好 1 个 → 自动选择，无需询问
     - 多个 → 用 `AskUserQuestion` 让用户选
     - 0 个 → 提示用户提供录音文件路径
   - **JD 图片**（可选）：
     - 找到 → 用 `analyze_image` MCP 工具提取
     - 没找到 → 不阻塞，可后续让用户提供
   - **面试笔记**（可选）：
     - PDF → 用 PyPDF2 提取文本
     - TXT/MD → 直接读取
     - 没找到 → 不阻塞

3. **转码**（如需要）：
   ```bash
   ffmpeg -i "input.{ext}" -map 0:0 -acodec libmp3lame -ab 128k "output.mp3"
   ```

---

### Phase 2：音频转写（本地执行，零 Token 消耗）

```bash
# 自动选择最佳引擎（macOS→mlx-whisper Metal，其余→faster-whisper）
python3 scripts/transcribe.py output.mp3

# NVIDIA GPU 加速（速度提升 3-5x）
python3 scripts/transcribe.py output.mp3 --device cuda --compute-type float16

# 速度优先：large-v3-turbo
python3 scripts/transcribe.py output.mp3 --model large-v3-turbo

# 强制使用 faster-whisper
python3 scripts/transcribe.py output.mp3 --engine faster-whisper

# macOS 可选：SenseVoice（无词级时间戳）
python3 scripts/transcribe.py output.mp3 --engine sensevoice
```

**引擎选择**：`--engine auto`（默认）自动检测最佳引擎。macOS 使用 **mlx-whisper**（Metal 加速，必选最佳实践），Linux/Windows 用 faster-whisper（CTranslate2，CPU + NVIDIA CUDA）。所有 Whisper 引擎提供词级时间戳（~20ms 精度）。

**输出**（与录音同目录）：
- `transcript_full.json` — 完整 JSON（segments 内含 word-level timestamps）
- `transcript_timestamped.txt` — `[MM:SS - MM:SS] 内容` 格式文本
- `transcript_timeline.txt` — 时间轴摘要
- `transcript_words.json` — 词级时间戳索引（用于精确边界定位）

---

### Phase 3：识别问答边界（LLM + 词级时间戳精确定位）

**核心**：LLM 识别问答转换文本 → 词级时间戳精确定位到秒。

1. 读取 `transcript_timestamped.txt` 通读全文，理解对话内容

2. 识别每个问答轮次的**转换关键句**（面试官的新提问），例如：
   - "这个产品的话可以具体讲一下你在这里边主要做什么工作吗"
   - "那你可以说一下产品经理完整的工作流程"
   - "你这边到岗时间是怎么样的"

3. 用 `transcript_words.json` 精确定位每句的时间戳：
   ```python
   # 在词级索引中搜索关键句，返回精确起始秒数
   python3 -c "
   import json
   words = json.load(open('transcript_words.json'))
   query = '这个产品的话可以具体讲一下'
   text_all = ''.join(w['word'] for w in words)
   pos = text_all.find(query)
   if pos >= 0:
       char_count = 0
       for w in words:
           char_count += len(w['word'])
           if char_count > pos:
               print(f'Transition at {w[\"start\"]:.1f}s')
               break
   "
   ```

4. **输出 `boundaries.json`**：
   ```json
   [
     {"start": 0, "end": 116.3, "question": "自我介绍"},
     {"start": 116.3, "end": 338.5, "question": "项目经验"}
   ]
   ```
   - `start`/`end` 单位为秒，精度到 0.1 秒
   - 每段 start = 上一段面试官新提问的起始时间

---

### Phase 4：按边界切分音频

```bash
python3 scripts/split_audio.py output.mp3 --boundaries boundaries.json --output segments
```

输出 `segments/Q01.mp3`, `segments/Q02.mp3`, ... + `segments_manifest.json`

---

### Phase 5：生成复盘文档 + 输出

> **最终交付物必须是可交互的文档（含可播放音频），禁止仅输出纯文本。**

#### 5.1 生成内容

1. 加载 `boundaries.json` + `transcript_timestamped.txt`
2. 按边界时间戳提取每题对应的回答文本
3. 结合 JD 要求，逐题给出更优解建议
4. 按以下模板生成 Markdown 内容：

```
# {公司名} {岗位名} 面试复盘

## 一、面试基本信息
## 二、公司 & 岗位画像
## 三、面试问答逐题复盘
  Q{N}：{问题标题}
  - 面试官提问 / 我的回答 / 评估 / 更优解
## 四、面试官评价总结
## 五、备战 Checklist
```

注意：Markdown 中**不写**"录音片段"占位符（音频通过 5.3a 或 5.3b 嵌入）。

#### 5.2 选择输出渠道（偏好驱动）

**如果有已保存的偏好**（`user_config.json` 中 `output_channel` 存在）：
- 直接使用已保存的渠道，**不询问**
- 告知用户："使用已保存的输出渠道：{html/feishu}，如需更改请说「切换输出渠道」"

**如果是首次运行或无偏好**：

用 `AskUserQuestion` 让用户选择生成渠道：

```
问题：选择复盘文档的输出渠道：
选项：
  - 飞书云文档（在线协作，需 lark-cli 已登录）
  - HTML 网页（本地保存，浏览器直接打开）
```

根据用户选择进入对应通道。无论哪种通道，都保留本地 Markdown 备份。

---

#### 5.3a 飞书通道（需 lark-cli）

**创建飞书文档**

```bash
cd "<录音文件所在目录>"  # lark-cli @file 只接受相对路径

lark-cli docs +create \
  --title "{公司名} · {岗位名} 面试复盘" \
  --content @复盘文档.md \
  --doc-format markdown \
  --api-version v2
```

记录返回的 `document_id` 和 `url`。

> 如果遇到代理警告，加 `LARK_CLI_NO_PROXY=1` 前缀。

**嵌入音频片段**

```bash
cd "<录音文件所在目录>"

lark-cli docs +media-insert \
  --doc "<document_id>" \
  --file "./segments/Q01.mp3" \
  --type file \
  --file-view preview \
  --selection-with-ellipsis "Q01：{问题标题关键词}"
```

参数说明：
- `--type file`：作为文件附件插入（支持音频播放）
- `--file-view preview`：渲染为内联播放器，非下载卡片
- `--selection-with-ellipsis`：用每个 Q 标题的**唯一前缀文本**定位插入位置
- `--file`：**必须用相对路径**（`./segments/Q01.mp3`），lark-cli 不接受绝对路径

音频片段**必须串行插入**（每个之间间隔 3 秒），禁止并行。并行插入会导致飞书 API 竞争条件，产生幽灵 block 和重复音频，且无法通过 CLI 清理，只能重建文档。

**设置公开读权限**

```bash
lark-cli drive permission.public patch \
  --params '{"token":"<document_id>","type":"docx"}' \
  --data '{"external_access_entity":"open","link_share_entity":"tenant_readable","comment_entity":"anyone_can_view"}' \
  --yes
```

注意：`comment_entity` 只接受 `anyone_can_view` 或 `anyone_can_edit`，不接受 `anyone_can_comment`。

**交付**：飞书文档 URL。

---

#### 5.3b HTML 通道（本地保存）

根据 `templates/interview-review-template.html` 生成 HTML 文件。每个 Q 章节内嵌 `<audio>` 播放器：

```html
<div class="qa-card">
  <h3>Q01：{问题标题}</h3>
  <audio controls preload="metadata">
    <source src="segments/Q01.mp3" type="audio/mpeg">
  </audio>
  <p class="label">面试官提问</p>
  <p class="content">{提问内容}</p>
  <!-- ... 回答 / 评估 / 更优解 ... -->
</div>
```

输出文件：`复盘文档.html`，放在录音文件同目录下（与 `segments/` 文件夹同级）。

用户打开方式：
- 直接浏览器打开 `复盘文档.html`
- 或 zip 打包 `{HTML + segments/}` 分享

**交付**：告知用户 HTML 文件路径，提示浏览器打开即可查看。

---

### Phase 6：保存偏好（Reflection 沉淀）

在交付完成后，保存/更新 `user_config.json`：

1. 读取已有 `user_config.json`（如果存在）
2. 更新字段：
   ```json
   {
     "version": 1,
     "output_channel": "<本次使用的输出渠道>",
     "language": "<本次使用的语言>",
     "model": "<本次使用的模型>",
     "device": "<本次使用的设备>",
     "compute_type": "<本次使用的精度>",
     "run_count": <累计次数 +1>,
     "first_run": "<首次运行日期，不变>",
     "last_run": "<当前日期>"
   }
   ```
3. 写入项目根目录的 `user_config.json`

**写入规则**：
- 每次运行完成后**必须保存**（即使用户未更改偏好，也更新 `last_run` 和 `run_count`）
- 只保存偏好字段，不保存面试内容
- 用户主动说"切换输出渠道"时，也更新此文件

---

## 约束

- **禁止**先用 ffmpeg 按固定时长切分音频再转写。必须完整转写 → 文本分析 → 按内容边界切分
- **禁止**仅输出纯文本/Markdown 作为最终交付。必须包含可播放音频的交互式文档（飞书或 HTML）
- **禁止**在文档中用文字链接代替音频嵌入。每个 Q&A 章节必须包含可播放的内联音频
- **禁止**并行插入音频到飞书文档。必须串行（3s 间隔），避免竞争条件
- 音频转写在本地执行，不消耗 LLM Token
- 更优解必须结合 JD、面试官评价、用户回答，具体可执行
- 所有输出文件整理到专用目录
- lark-cli 的 `@file` 参数必须用相对路径，先 cd 到目标目录再执行
- 飞书文档创建使用 `--api-version v2`，内容格式用 `--doc-format markdown`

## 依赖

| 工具 | 必需 | 用途 | 安装 |
|------|------|------|------|
| ffmpeg | ✅ | 音频转码/切分 | `brew install ffmpeg` / `apt install ffmpeg` |
| Python 3.10+ | ✅ | 转写脚本 | 系统包管理器 |
| mlx-whisper | ✅ macOS | Whisper 引擎（Metal 加速，最佳实践） | `pip install mlx-whisper` |
| faster-whisper | ✅ Linux/Win | Whisper 引擎 (CTranslate2) | `pip install faster-whisper` |
| mlx-audio | ❌ macOS | SenseVoice 引擎（备选） | `pip install mlx-audio` |
| lark-cli | ❌ 可选 | 飞书文档输出 | `npm install -g lark-cli` |

> 一键安装：`bash setup.sh`（macOS/Linux）或 `powershell -ExecutionPolicy Bypass -File setup.ps1`（Windows）
> macOS 最佳实践：mlx-whisper Metal 加速，33 分钟面试 1.5 分钟转写。
> Linux/Windows：faster-whisper CTranslate2，支持 NVIDIA GPU（`--device cuda`）。
> Reflection 机制：首次运行建立偏好，后续只需提供素材文件夹路径即可自动执行全流程。
