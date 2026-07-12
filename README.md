# DailyRead

一个由 GitHub Actions、DeepSeek API 与 GitHub Pages 驱动的每日英文阅读系统。它从 RSS 新闻源选材，生成分级阅读材料、词汇卡、长难句、地道表达和动态选择题，并发布到网页。

网站：[https://ryoudyfz.github.io/DailyRead/](https://ryoudyfz.github.io/DailyRead/)

## 功能一览

- 每日定时或手动生成英文阅读材料；默认保留新闻原文，不由 AI 重写正文。
- 主题覆盖科技、AI、医学、商业、环境和教育；过滤逻辑可自行扩展。
- 五档学习难度：`middle`、`high`、`college`、`advanced`、`proficiency`。
- 固定 Markdown 教学版式，词汇按类别分区展示。
- 发布格式遵循 [DailyRead Markdown 标准模板规范](docs/MARKDOWN_FORMAT.md)，落盘前执行结构硬校验。
- GitHub Pages 网页：按日期浏览、在线作答、即时批改。

## 快速开始

### 1. 配置 GitHub Secret

仓库进入 **Settings → Secrets and variables → Actions → New repository secret**，创建：

| 名称 | 必填 | 作用 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | 是 | DeepSeek API 密钥 |

可选地，在 **Settings → Secrets and variables → Actions → Variables** 中创建：

| 名称 | 默认值 | 作用 |
| --- | --- | --- |
| `DEEPSEEK_MODEL` | `deepseek-v4-flash` | 生成和事实审校使用的模型名称 |

### 2. 启用 GitHub Pages

仓库进入 **Settings → Pages**，将发布方式设置为 **GitHub Actions**。首次推送后，部署工作流会发布网站。

### 3. 手动生成一篇文章

进入 **Actions → Daily Reading Pack → Run workflow**，按需要填写：

- `topic`：可选。填写 `technology`、`ai`、`medicine`、`business`、`environment` 或 `education`。
- `difficulty`：选择学习难度，默认 `college`。
- `content_mode`：正文模式，默认 `original-adapt`；可选择 `original-full` 或 `adapted`。
- `publish`：设为 `true` 时，生成的 Markdown 与 JSON 会提交回仓库；定时任务会自动提交。

生成结果位于 `outputs/generated/YYYY-MM-DD.md` 和 `outputs/generated/YYYY-MM-DD.json`。网页部署后，左侧栏会自动出现对应日期。

## 难度配置

`difficulty` 是最重要的自定义项。它会同时影响目标人群、CEFR、篇幅、词汇量、长难句数量、题目数量和题目类型。

| 参数 | 适用人群 | CEFR | 词数 | 词汇 | 长难句 | 题目 |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `middle` | Middle | A2–B1 | 500–700 | 8 | 2 | 5 |
| `high` | High | B1–B2 | 700–900 | 10 | 3 | 6 |
| `college` | College | B2–C1 | 900–1200 | 10 | 4 | 7 |
| `advanced` | IELTS 6.5–8.0 / TOEFL 90+ | C1–C2 | 1000–1400 | 15 | 5 | 8 |
| `proficiency` | TEM-8, GRE, GMAT Verbal, Academic Reading | C2+ | 1200–1800 | 30 | 10 | 12 |

## 正文模式

`CONTENT_MODE` 决定新闻正文是否由模型改写。无论哪种模式，摘要、词汇卡、长难句、表达和阅读题均由 DeepSeek 基于最终正文生成。

| 模式 | 默认 | 正文处理 | 难度说明 |
| --- | --- | --- | --- |
| `original-adapt` | 是 | 从一篇来源新闻中选择连续段落，逐字保留，不改写 | 仅允许 `high`、`college`、`advanced`；实际难度随原文浮动 |
| `original-full` | 否 | 使用抓取到的该篇新闻全文，逐字保留 | 可搭配五档配置；原文难度不保证与目标档位完全一致 |
| `adapted` | 否 | 根据经核查的事实清单生成改写阅读文章 | 五档难度均可精确控制 |

`original-adapt` 会选取接近所选档位目标篇幅的连续段落，默认以 `college` 的目标长度选取。它不简化词汇或句法，因此 `CEFR` 仍显示所选档位，星级则由脚本根据最终原文计算。文章顶部会明确标注“新闻原文连续节选”或“新闻原文全文”，并保留数据源链接。

在本地运行时设置：

```bash
export CONTENT_MODE="original-adapt"  # 默认；也可为 original-full 或 adapted
```

### 修改难度档位

编辑 [scripts/generate_reading_pack.py](scripts/generate_reading_pack.py) 中的 `DIFFICULTY_PROFILES`。每一档可调整：

```python
"custom": {
    "cefr": "B2-C1",
    "words": "800-1000",
    "vocab": 12,
    "sentences": 4,
    "questions": 7,
    "vocab_distribution": {
        "core_word": 5,
        "fixed_collocation": 3,
        "phrasal_verb": 2,
        "academic_word": 2,
    },
    "question_types": [...],
    "audience": "对模型的明确语言风格要求",
}
```

注意：

- `vocab_distribution` 的总数必须等于 `vocab`。
- `question_types` 的数量必须等于 `questions`。
- 每个档位都应按真实用户水平定义词汇、抽象程度、句法复杂度与题目要求。
- 新增档位后，需要同时把名称加入 Workflow 参数说明；不需要修改网页代码。

## 难度星级与 CEFR

文章顶部有两个不同概念：

- **CEFR**：由所选 `difficulty` 档位决定，例如 `college` 显示 `B2-C1`。
- **难度星级**：脚本按实际阅读文本计算，而不是直接采用 AI 返回的固定值。计算会参考平均句长、长词比例和复杂连接词密度。

文本难度算法位于 `assess_text_difficulty()`。如需调整星级阈值，编辑该函数的 `complexity` 计算公式和阈值。

## 阅读内容与版式规则

生成器要求：

- 文章只使用已抓取新闻正文中的事实。
- 摘要只总结新闻内容；不得出现“适合学习者”“可学习词汇/句型”“帮助读者”等学习效果描述。
- 中文解释中出现英语词或词组时使用 Markdown 行内代码，例如 `` `cause a backlash` ``。
- 所有英文词性使用缩写：`n.`、`v.`、`adj.`、`adv.`、`phr.`、`prep.`、`conj.` 等。
- 固定搭配与短语动词统一使用 `phr.`，不使用 `phr. n.` 或 `phr. v.`。

### 词汇卡片的分类

词汇不再连续堆叠，而是依次展示：

1. 核心单词 `core_word`
2. 固定搭配 `fixed_collocation`
3. 短语动词 `phrasal_verb`
4. 学术词 `academic_word`

每项包含词性、中文释义、常见搭配和例句。分类标题与渲染规则位于 `VOCABULARY_SECTION_TITLES` 和 `render_markdown()`。

### 修改禁止摘要用语与词性

| 目标 | 文件位置 | 配置名 |
| --- | --- | --- |
| 禁止出现在摘要中的表达 | `scripts/generate_reading_pack.py` | `SUMMARY_BANNED_PHRASES` |
| 允许的词性缩写 | 同上 | `POS_ABBREVIATIONS` |
| 词汇分区中文名称 | 同上 | `VOCABULARY_SECTION_TITLES` |

## 题目与答案

题目数量随难度动态变化，所有题目均为四选一。每道题的正确答案由当天文章动态生成；事实修订后，AI 必须重新检查题目、选项和答案串。

基础七类题型为：

`Main Idea`、`Detail`、`Inference`、`Vocabulary in Context`、`Author's Attitude`、`Organization`、`Title`。

`advanced` 与 `proficiency` 还会加入应用、证据、语气与文体、批判性评价、综合等题型。题型列表在 `DIFFICULTY_PROFILES[*]["question_types"]` 中自定义。

网页构建器支持 5–12 道题，位于 [scripts/build_site.py](scripts/build_site.py)。网页答题逻辑位于 [site/assets/app.js](site/assets/app.js)。

## 新闻源与主题

默认新闻源文件：[outputs/bbc-learning-feeds.opml](outputs/bbc-learning-feeds.opml)。每条 `<outline>` 可以配置：

`title`：在数据源中显示的名称。

`xmlUrl`：RSS 地址。

`category`：一个或多个以逗号分隔的主题标签。

默认主题映射写在 `TOPIC_KEYWORDS`：

`technology`、`ai`、`medicine`、`business`、`environment`、`education`。

### 添加 AP、Reuters、NPR 或其他 RSS

在 OPML 的 `<body>` 中新增一行，例如：

```xml
<outline
  text="Example — Technology"
  title="Example — Technology"
  type="rss"
  category="technology,ai"
  xmlUrl="https://example.com/feed.xml"
  htmlUrl="https://example.com/" />
```

## 事实审校与修订闭环

工作流采取以下流程：

```text
RSS → 抓取正文 → DeepSeek 提取事实清单 → DeepSeek 受清单约束写作 → 结构校验 → DeepSeek 事实审校
                                                ↓
                                   仅用清单事实替换，或直接删除问题句
                                                ↓
                                      通过后写入 Markdown / JSON
```

写作模型只看到事实清单，不直接看到新闻正文；清单列出允许使用的实体、数字、事实和可选引语。审校问题只允许两种修订：使用清单中的直接事实替换，或删除该句，禁止补写行业背景、法规比较、用户规模、预测或因果分析。系统不会因文章略偏离目标词数而直接失败，也不对正文数字执行机械的来源字符串匹配。核心校验仍会检查：字段完整性、词汇类别数量、词性、长难句数量与正文对应关系、题目数量、题目类型、选项结构，以及答案与答案串一致性。

可调整项：

| 目标 | 位置 |
| --- | --- |
| 事实审校提示词 | `audit_facts()` |
| 最大完整尝试次数 | `generate_with_retries(..., attempts=2)` |
| 正文抓取长度 | `fetch_article_text()` 与 `source_text[:6000]` |
| 单次选取的新闻篇数 | `main()` 中 `[:2]` |
| DeepSeek 温度与超时 | `call_deepseek()` |

## 定时任务与部署

### 每日生成

`.github/workflows/daily-reading.yml` 使用：

```yaml
cron: "10 23 * * *"
```

即每天 UTC 23:10（北京时间约 07:10）运行。修改 cron 即可调整时间；GitHub Actions 的计划任务可能存在少量延迟。

### GitHub Pages

- `Daily Reading Pack` 在生成文章后构建并部署网站。
- `Deploy GitHub Pages` 在网页文件、生成文章或站点构建脚本变化时重新部署，不调用 DeepSeek。
- 网页源代码在 `site/`；构建产物为 `public/`，该目录由构建脚本生成。

## 本地运行

```bash
python3 -m pip install -r requirements.txt
export DEEPSEEK_API_KEY="your_key"
export DIFFICULTY_LEVEL="college"
export CONTENT_MODE="original-adapt"
export TOPIC_OVERRIDE="technology"   # 可选
python3 scripts/generate_reading_pack.py
python3 scripts/build_site.py
```

常用环境变量：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | None | 必填 API 密钥 |
| `DEEPSEEK_MODEL` | `deepseek-v4-flash` | DeepSeek 模型名称 |
| `DIFFICULTY_LEVEL` | `college` | 五档学习难度之一 |
| `CONTENT_MODE` | `original-adapt` | `original-adapt`、`original-full` 或 `adapted` |
| `TOPIC_OVERRIDE` | 自动选择 | 强制指定主题 |
| `NEWS_FEEDS_FILE` | `outputs/bbc-learning-feeds.opml` | RSS 配置文件 |
| `OUTPUT_DIR` | `outputs/generated` | 生成结果目录 |

当然，欢迎帮我覆盖成本qwq
