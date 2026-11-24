# KOReader 统计数据结构与可视化数据契约

## 一、KOReader statistics.sqlite3 数据库结构

KOReader 阅读器生成的 `statistics.sqlite3` 关键表：

### `book` 表
| 字段 | 含义 |
|---|---|
| `id` | 书籍数字 id（**注意：不一定连续**，如 6/20/25） |
| `title` | 书名（可能含 `(Z-Library)`、`套装共X册` 等冗余后缀） |
| `authors` | 作者 |
| `total_read_time` | **总阅读时长，单位秒** —— 筛选阈值依据 |
| `total_read_pages` | 累计阅读页数 |
| `pages` | 书总页数 |
| `last_open` | 最后打开时间（Unix 时间戳） |
| `md5` | KOReader 内部哈希（≠文件 MD5，无法直接匹配 epub 文件） |

### `page_stat_data` 表（逐次阅读记录）
| 字段 | 含义 |
|---|---|
| `id_book` | 对应 `book.id` |
| `page` | 页码 |
| `start_time` | 阅读开始时间（Unix 时间戳）→ 用于按天聚合 |
| `duration` | 本次阅读时长（秒） |
| `total_pages` | 总页数 |

### `page_stat` 视图
对 `page_stat_data` 做了跨页缩放展开，**日常聚合用 `page_stat_data` 原始表即可**，不要用该视图，否则重复计数。

### 关键事实与陷阱
- 时长单位是**秒**，不是分钟（5 分钟 = 300 秒）。
- `book.total_read_time` 与按天聚合 `SUM(page_stat_data.duration)` 基本 1:1 吻合（允许个位秒误差），可交叉校验。
- 同一作品可能有多个 id（不同版本/来源），需要时用 `--merge '{"alias_id":canonical_id}'` 合并。
- 书名相同但作者/封面不同时，按 id 区分，不要用书名当 key。

## 二、epub 封面提取

epub 是 zip 包，封面定位流程：
1. 读 `META-INF/container.xml` → 找 `rootfile` 的 `full-path`（如 `content.opf` 或 `OEBPS/content.opf`）
2. 读 opf → `<metadata>` 里 `<meta name="cover" content="cover-id">`
3. 在 `<manifest>` 找 `id=cover-id` 的 `<item href="...">`
4. 兜底：manifest 中 `properties` 含 `cover-image` 或 id 含 `cover` 的图片项；再兜底文件名 `cover.jpg/jpeg/png`、`images/cover.jpg`
5. Pillow 打开 → 缩放到宽 210px → JPEG quality 82 → base64 data URI 内嵌

`build_data.py` 已实现上述流程；封面与书的匹配优先级：
`--covers` 显式映射 > 按书名/作者模糊匹配 epub 元数据 > 灰底占位（会警告，此时用 `gen_cover.py` 生成后通过 `--covers`/`--fallback-dir` 指定）。

## 三、可视化数据契约（reading_data.json）

`build_data.py` 产出，`render_html.py` 消费：

```json
{
  "meta": {
    "source": "KOReader statistics.sqlite3",
    "generated": "2026-11-24",
    "thresholdSeconds": 300,
    "firstDay": "2026-07-15", "lastDay": "2026-11-24",
    "excludedBooks": 18, "mergedEditions": 1
  },
  "stats": {
    "bookCount": 11, "totalSeconds": 707144, "totalMinutes": 11786,
    "totalHours": 196.4, "activeDays": 125, "spanDays": 133
  },
  "books": [{
    "id": 6, "title": "完整书名", "shortTitle": "短名",
    "author": "作者", "seconds": 365040, "minutes": 6084,
    "pages": 26761, "readPages": 7249, "language": "zh",
    "firstDay": "...", "lastDay": "...", "activeDays": 89,
    "cover": "data:image/jpeg;base64,...", "color": "#8B5E3C",
    "mergedFrom": [6, 1]
  }],
  "calendar": {
    "2026-10-02": [{"bookId":6,"seconds":...,"minutes":...}, ...]
  }
}
```

- `books` 按 `seconds` 降序；`calendar` 每个日期的书也按时长降序。
- **英文书保留英文原名（用户明确要求，勿自动翻译）**：`build_data.py` 的 `display_title()` 对英文书（language 以 en 开头，或标题为纯拉丁字母）忽略含中文字符的 `--names` 短名覆盖，改用原版英文书名；`title` 字段始终为数据库原始书名。前端展示 `shortTitle` 即为英文原名。
- `calendar` 只含有阅读的日期，前端按 `firstDay~lastDay` 补齐空格。
- **id 非连续**：前端所有 `calendar[date].bookId → books[].id` 关联必须按 id 映射，不可用数组下标。

## 四、交互/视觉契约（template.html 已实现）

- 单文件自包含：CSS/JS 内嵌，数据以 `const DATA = {...};` 单行内嵌，封面 base64，零外部网络依赖，`file://` 可直接打开。
- 视觉概念「纸上年轮」：暖纸白 `#F7F5F0` 底、白卡片、墨绿强调 `#2E4A43`、暖色阴影；封面是唯一高饱和元素；字号 12/14/15/18/20/32/36 七档。
- 日历：20 周×7 天 GitHub 式网格，30×42px 竖版封面，按当日时长三档 opacity（<.45/.72/1）；单日多书叠加小封面/色点。
- 排行：封面带出时长，条长 `sqrt(minutes)` 缩放至 8%–100%（避免长尾消失），右侧显示真实时长；三档排序（时长/天数/书名）。
- 双向软高亮：点日历某天→排行中当日书高亮；点排行某行→日历中该书所有日期描边。焦点互斥，焦点芯片「正在看：XX」。
- 关键实现约束（静默失效点）：
  - 蒙版 `::after` 必须 `pointer-events:none`（否则格子不能点）
  - 选中描边画在外层 `box-shadow:0 0 0 2px --accent`（画在封面上会被蒙版盖住）
  - 排行软高亮用 `box-shadow:inset 3px 0 0 --accent`（非真 border，避免行宽跳动）
  - 封面解码失败降级为书色首字块
-  header/KPI/页脚文案由 JS 从 `DATA.meta`/`DATA.stats` 动态填充，模板可复用于任意数据集。
