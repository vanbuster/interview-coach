# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- LICENSE (MIT) — clarifies reuse rights
- CHANGELOG.md — this file
- GitHub Actions CI (`/.github/workflows/ci.yml`) — smoke test on macOS + Linux
- Smoke test for `scripts/split_audio.py` (`tests/test_split_audio.py`)
- README "复制即用" 区块：一行安装 + 一段可粘贴给 Agent 的触发提示词

### Changed
- **Skill 名称统一**：`interview-review-coach` → `interview-coach`（与仓库名一致）
- **安装路径**：`cp -r` 模式 → 直接 `git clone` 到 `~/.claude/skills/interview-coach`（skill 目录即 git repo，方便 `git pull` 升级）
- `requirements.txt` 锁定兼容版本（faster-whisper ~=1.2.0）

### Removed
- 远端 `windows` 分支（已 deprecated，统一到 main）

## [0.1.0] — 2026-06-16

### 总结
首个稳定版本。跨平台（macOS / Linux / Windows）+ Reflection 偏好机制 + 文件夹扫描自动化。

### Added
- **跨平台引擎自动检测**：macOS 走 mlx-whisper（Metal 加速），Linux/Windows 走 faster-whisper（CTranslate2），NVIDIA GPU 可选 CUDA
- **Reflection 机制**：首次运行保存偏好到 `user_config.json`，后续运行零询问
- **文件夹扫描**：用户只需提供素材文件夹路径，Agent 自动识别音频/JD图片/笔记
- **逐题更优解**：结合 JD 给出可执行的优化建议
- **两种交付物**：飞书云文档（含内嵌音频播放器）+ HTML 网页（本地零依赖）
- **词级时间戳边界定位**：~20ms 精度，问答切分误差 <0.1s

### 性能基线
- 33 分钟中文面试 → 1.5 分钟转写（mlx-whisper medium，Metal 加速）
- 9 个问答转折点全部精确定位

## [Pre-release] — 2026-05

### Initial Release
- `feat: initial release of interview-coach` (commit 993c316)
- `feat: add Reflection mechanism` (commit d795837)
- `feat: unify branches — single cross-platform main branch` (commit fb9860d)
