---
name: koreader-reading-calendar
description: 从 KOReader 的 statistics.sqlite3 阅读统计数据库生成「阅读日历 + 阅读时长排行」单文件 HTML 可视化。日历用书籍封面填充日期格，排行用封面带出阅读时长并按 sqrt 缩放。适用于用户给出阅读统计数据库路径与 epub 书籍/封面目录路径，希望剔除短时长书籍、按封面可视化阅读习惯、生成可离线打开的漂亮页面时。触发词：阅读统计、阅读日历、reading calendar、KOReader 统计、阅读时长排行、封面日历。
agent_created: true
---

# KOReader 阅读日历与时长排行

## 用途

把 KOReader 的阅读统计数据库转成一张「纸上年轮」式的可视化页面：上半部分是 GitHub 风格的阅读日历（每个阅读日的格子里贴当天所读书籍的封面），下半部分是按总阅读时长从多到少排列的封面榜单。最终产出**一个自包含 HTML 文件**（数据/封面全部内嵌、零网络依赖、`file://` 双击即可打开）。

## 何时使用

- 用户提供 `statistics.sqlite3`（KOReader 阅读统计库）路径 + epub 书籍目录（含封面）路径。
- 需求形如：「剔除阅读不足 N 分钟的书籍，用封面做一个阅读日历和时长排序图」。
- 需要可复用产出（同一套流程跑不同用户/不同时间段的数据）。

## 开始前：向用户索取三项输入

1. **阅读数据库路径**（必需）：`statistics.sqlite3` 的完整路径。
2. **epub 书籍目录**（必需）：递归扫描其中 epub 提取封面；若某本书不在其中，需用户提供其封面图或允许生成的排版封面。
3. **可选参数**：时长阈值（默认 5 分钟）、需要合并的同书不同版本（给出 id 映射）、书名短名/配色覆盖。

若用户未明确阈值，默认 300 秒（5 分钟）并在交付时说明。

## 工作流

所有脚本位于本 skill 的 `scripts/`，Python 3 + Pillow（若缺 Pillow：`pip install pillow`）。路径含空格时用引号包裹。

### 步骤 1：探查数据（确认库结构与候选书）
```bash
python <skill>/scripts/inspect_db.py --db "<statistics.sqlite3>" --threshold 300
```
打印书籍/时长/日期范围/候选清单，据此与用户确认阈值、是否合并重复版本。schema 细节见 `references/data_structure.md`。

### 步骤 2：构建数据 JSON
```bash
python <skill>/scripts/build_data.py \
  --db "<statistics.sqlite3>" \
  --epub-root "<epub目录>" \
  --out "<工作目录>/reading_data.json" \
  --threshold 300 \
  --merge '{"1":6}' \
  --covers '{"13":"/path/to/cover.jpg"}'
```
- `--merge` 合并同书不同版本（alias id → canonical id）。
- `--covers` 为自动匹配失败的书显式指定封面（值可为 epub 文件名、图片绝对路径或 `--fallback-dir` 中的文件名）。
- 脚本会打印每本书的封面匹配情况与警告；对匹配失败且无封面的书，用步骤 2b 生成。

**步骤 2b（可选）：为无封面的书生成排版封面**
```bash
python <skill>/scripts/gen_cover.py --title "The Martian" --author "Andy Weir" \
  --out "<工作目录>/fallback/the_martian.jpg" --theme auto
```
然后用 `--fallback-dir "<工作目录>/fallback"` 或 `--covers` 让 build_data 使用它。

### 步骤 3：渲染 HTML
```bash
python <skill>/scripts/render_html.py \
  --data "<工作目录>/reading_data.json" \
  --template "<skill>/assets/template.html" \
  --out "<工作目录>/index.html"
```
模板中 header/KPI/页脚文案均由 JS 从数据动态填充，无需手工改字。

### 步骤 4：验证并交付
```bash
python <skill>/scripts/verify.py \
  --html "<工作目录>/index.html" \
  --data "<工作目录>/reading_data.json" \
  --screenshot "<工作目录>/preview.png"
```
验证内嵌数据一致性、封面内嵌、无外部依赖、id 映射完整；`--screenshot` 用无头 Chrome 渲染截图（**注意 `--virtual-time-budget=5000` 已在脚本内设置，否则入场动画未完成会截成空白**）。最后用 present_files 展示 index.html。

## 关键约束（务必遵守）

- **时长单位是秒**，阈值 5 分钟 = 300。
- **书籍 id 非连续**：所有 id→book 关联按 id 映射，不可用数组下标（否则跨视图联动静默失效）。
- **同书不同版本**先问用户是否合并，再决定是否用 `--merge`。
- 阅读数据里的 `total_read_time` 应等于按天聚合之和（允许个位秒误差），不等则说明数据异常。
- 页面必须自包含：不要引用外部字体/CDN/网络图片；封面 base64 内嵌。
- 视觉与交互契约详见 `references/data_structure.md` 第四节；一切以 `assets/template.html` 为唯一版式来源，不要重写样式。
- 交付后提醒用户：页面可离线打开，封面/数据已内嵌；若换数据只需重跑步骤 2-3。

## 资源

- `scripts/inspect_db.py` — 探查数据库、列出候选书与统计概览
- `scripts/build_data.py` — 从 DB + epub 目录构建数据 JSON（封面提取/匹配/合并）
- `scripts/gen_cover.py` — 为缺封面的书生成排版封面
- `scripts/render_html.py` — 把数据注入模板生成单文件 HTML
- `scripts/verify.py` — 结构校验 + 无头浏览器截图
- `assets/template.html` — 数据驱动的阅读日历/排行 HTML 模板（纸上年轮风格）
- `references/data_structure.md` — KOReader 表结构、epub 封面提取流程、数据契约、视觉/交互约束
