# DailyRead Markdown Specification

Version: 1.0  
Last Updated: 2026-07-12

本文档是生成器、人工导入和 GitHub Pages 构建共同遵循的格式契约。关键词、标题、标点、空行和章节顺序均属于协议的一部分，不是排版建议。生成文件不符合本规范时不得写入或发布。

## 1. 文件与编码

- Markdown 保存到 `outputs/generated/YYYY-MM-DD.md`，结构化原始数据保存到同目录同名 `.json`。
- 文件使用 UTF-8、LF 换行，末尾保留一个换行符，不使用 YAML front matter。
- 文件名日期、正文元数据日期和生成日期必须一致，日期格式只能是 `YYYY-MM-DD`。
- 英文单词数只统计 `Reading Passage` 中的英文词；千位使用英文逗号，例如 `1,142 words`。
- 标准水平分隔线固定写作六个半角连字符 `------`，其前后各留一个空行。
- 一级标题后必须写可见版本行 ``规范版本：`1.0` ``。解析器必须先读取版本，再选择对应规则。

### 1.1 MUST NOT（禁止项）

生成文件不得包含以下内容；任一项出现即视为无效：

- 禁止 fenced code block（以三个反引号开头的代码块）。
- 禁止 YAML front matter 或任何独立的 `---` 行。
- 禁止 HTML 注释 `<!-- ... -->`。
- 禁止 Markdown Table。
- 除规范列出的一级、二级和四个词汇三级标题外，禁止新增任何标题。
- 禁止以“好的”“当然”“以下是”开头的寒暄、解释或引导语。
- 禁止“作为 AI”“我生成了”等 AI 自述。
- 禁止在标准文档骨架前后输出解释、免责声明或完成提示。

## 2. 固定章节顺序

正文只能按以下顺序出现七个二级标题。标题文字、大小写和空格必须完全一致；不得漏项、改名、重复或插入其他二级标题。

1. `## 文章摘要`
2. `## Reading Passage`
3. `## 单词卡片`
4. `## 长难句理解`
5. `## 习语与地道表达`
6. `## 阅读理解`
7. `## 数据源`

除 `## 数据源` 之前外，各主体章节之间使用 `------` 分隔。正文模式说明如存在，只能放在顶部信息区与文章摘要之间，并使用 Markdown 引用行。

## 3. 顶部信息区

### 3.1 双语标题

首行固定为：

```markdown
# English Title｜中文标题

规范版本：`1.0`
```

- 英文标题在前，中文标题在后，中间只能使用全角竖线 `｜`，两侧不加空格。
- 英文标题采用自然的标题式大小写；中文标题简洁、准确，不在末尾加句号。
- 标题必须概括正文主题，不使用“每日阅读”“英语学习”等模板性措辞。

### 3.2 元数据行

标题后空一行，随后整行固定为：

```markdown
日期： `2026-07-10`｜词汇量：`1,142 words`｜预计阅读时间：`9 分钟`｜CEFR：`C1`｜来源：`BBC News`
```

- 字段顺序必须是日期、词汇量、预计阅读时间、CEFR、来源。
- 冒号均使用全角 `：`；字段之间均使用 `｜`；每个字段值均用一对反引号包裹。
- 阅读时间按每分钟 130 词四舍五入，最少 1 分钟。
- 多来源使用 ` · ` 连接并去重，不写 URL。

### 3.3 主题与难度

元数据后依次写两行，每行前后各空一行：

```markdown
🏷 主题：`Medicine · Public Health`

⭐ 难度：★★★★☆
```

- 主题为 1–3 个简短英文标签，使用 ` · ` 分隔，整体只用一对反引号。
- 难度由实心 `★` 和空心 `☆` 构成，实心星在前。
- 难度后空一行并写 `------`。

## 4. 文章摘要

```markdown
## 文章摘要

一段中文事实摘要。
```

- 只写一个中文自然段，建议 120–220 个汉字，不使用列表或小标题。
- 必须说明发生了什么、涉及谁以及事件为何重要；多事件文章还需点明共同主线。
- 不得出现“适合学习者”“本文帮助读者”“词汇/句型学习”等教学评价。
- 不添加正文或来源中没有的人名、数字、因果关系、预测和立场。

## 5. Reading Passage

```markdown
## Reading Passage

First paragraph...

Second paragraph...
```

- 只包含英文正文，不加内部标题、项目符号、图片、脚注或答案提示。
- 每段之间空一行，段首不缩进；直引号使用英文弯引号或半角引号并保持一致。
- 正文必须与选定难度的词数、CEFR 和受众要求一致；原文模式不得改写正文。
- 各难度词数范围属于编辑目标（SHOULD）而非有效性条件；例如 `college` 建议为 900–1,200 词。偏离目标不得触发重试或阻止发布。
- 人名、机构、数字、引语和事实必须能由数据源支持。
- 正文建议（SHOULD）包含 4–8 个自然段；建议每个自然段不超过 220 个英文词。
- 全文平均句长建议（SHOULD）保持在 18–30 个英文词。缩写中的句点不得被误判为句末。
- 以上均为编辑质量建议，不是有效性条件，不得因偏离建议而拒绝生成、触发重试或阻止发布。
- 建议避免由单个自然段承载整篇文章，并按背景、主要事实、影响/解释和结论组织。

## 6. 单词卡片

标题后固定写提示语：

```markdown
## 单词卡片

> 点开卡片查看词义、搭配和例句。
```

### 6.1 分组与数量

卡片必须依次放在以下四个三级标题下，不得改变顺序：

1. `### 核心单词`
2. `### 固定搭配`
3. `### 短语动词`
4. `### 学术词`

各难度的总数和分布由 `DIFFICULTY_PROFILES[*].vocab_distribution` 决定。默认 `college` 为 10 张：核心单词 4、固定搭配 3、短语动词 2、学术词 1。不得用人名、地名、品牌名或简单词形变化凑数。

### 6.2 单卡字面格式

每张卡片必须完整使用 Appendix A 的 Word Card Template。模板中的标签名、类名、字段顺序、空格和换行属于 v1.0 协议；正文不另行复制模板定义。

- 正面必须依次显示词条、IPA 和词性。IPA 只保留一层 `/.../`。
- 词性使用 `n.`、`v.`、`adj.`、`adv.`、`phr.`、`prep.`、`conj.`、`pron.`、`det.`、`int.`、`num.` 或 `abbr.`；固定搭配和短语动词统一使用 `phr.`。
- 释义为与正文语境一致的简洁中文含义，不罗列无关义项。
- 常见搭配必须有 2–3 个，每个用反引号包裹，之间使用 ` · `。
- 例句必须是完整、自然、原创的英文句子，以句末标点结束；不得直接复制正文句子。
- HTML 属性值和文本必须正确转义；卡片之间空一行，不在卡片内插入 Markdown 列表。
- 禁止选择停用词或过于宽泛、缺乏学习价值的词，包括 `the`、`and`、`government`、`company`。
- 若词条已经出现在“习语与地道表达”，不得再次出现在单词卡片；比较时忽略大小写、标点和多余空格。

## 7. 长难句理解

每项严格使用四段结构：

```markdown
> 原文中的完整英文句子。

**语法要点：**语法点一；语法点二

**分析：**中文结构分析。

**翻译：**完整中文翻译。
```

- 句子必须逐字出现在 `Reading Passage`，保留原标点，不得由模型改写或拼接。
- 数量由难度配置决定；默认 `college` 为 4 句。
- 语法要点写结构名称，用中文分号分隔；分析必须指出主句、从句、非谓语或关键搭配的具体作用。
- 翻译应完整准确，不遗漏逻辑关系；每项之间保留两个空行。
- 建议（SHOULD）每个自然段最多抽取一个长难句，避免全部集中在同一段；该分布要求不作为拒绝生成或发布的条件。

## 8. 习语与地道表达

每项严格使用三段结构：

```markdown
**stage a comeback** 卷土重来，东山再起

用于描述衰落后重新流行或成功。

例句：After years of low sales, the brand staged a comeback.
```

- 每篇 3–5 项，表达必须来自正文或直接由正文中的自然搭配构成。
- 第一行只含加粗英文表达和中文释义；第二段说明语域、场景或搭配限制；第三段为原创英文例句。
- 不与单词卡片机械重复，不收录专有名词或只有字面意义的普通短语。

## 9. 阅读理解

每题固定写作：

```markdown
1. **Question text?**

A. Option A

B. Option B

C. Option C

D. Option D

------
```

- 题号从 1 连续递增；题干加粗，A–D 选项不加粗；题干和每个选项后均空一行。
- 每题必须恰有四个选项且只有一个最佳答案。干扰项须可由正文排除，不能依赖外部知识。
- 题型和顺序由难度配置决定。默认 `college` 依次为主旨、细节、推断、语境词义、作者态度、篇章结构、标题。
- 每题后写 `------`；最后一题的分隔线后写答案串，例如 `（答案：BCADCBA）`。
- 答案必须只含连续的大写 `A`–`D`，数量与题数一致，并逐题匹配结构化 JSON。
- JSON 中每题必须包含指向实际段落、从 1 开始的整数 `evidence_paragraph`。整套题建议（SHOULD）覆盖第 1、2、3、4 段和结论段；覆盖不足只记录为质量提示，不得拒绝生成或发布。

## 10. 数据源

答案后空两行，使用：

```markdown
## 数据源

[BBC News] Article title (https://example.com/article)
```

- 每个实际使用的来源占一行，来源之间空一行；顺序与正文事实使用顺序一致。
- 方括号中为媒体名，随后为原始英文标题，圆括号内为完整 HTTPS URL。
- 不使用 Markdown 的 `[标题](URL)` 链接形式，不添加未用于生成正文的候选来源。
- URL 应使用 HTTPS。允许整合多篇文章，也允许同一 URL 因不同来源记录或引用关系重复出现；URL 唯一性不是有效性条件。

## 11. Markdown 与 JSON 一致性

同名 Markdown 和 JSON 是同一份内容的两种表示，必须由同一结构化对象渲染，不允许分别生成。以下字段必须语义及字面一致：

- `spec_version`
- `title_en`、`title_zh`
- `summary_zh`
- `cefr`、`themes`、`difficulty`
- `reading_passage`
- `vocabulary` 的顺序与所有字段
- `difficult_sentences` 和 `idioms` 的顺序与所有字段
- `reading_questions` 的题干、选项顺序、答案与 `evidence_paragraph`
- `answer_key`
- 实际使用的数据源标题与 URL

若 Markdown 的答案、词条或题目与 JSON 不同，整组文件无效，Pages 不得发布。

## 12. Validation Rules（机器可执行）

以下规则采用语言无关的断言形式。Python、Rust、Swift 或其他实现必须产生相同的通过/失败结果：

```text
spec_version == "1.0"
title_count == 1
section_count == 7
sections == REQUIRED_SECTIONS_V1_0
extra_heading_count == 0
paragraph_count recommendation 4..8 // SHOULD; non-blocking
max(paragraph_word_count) recommendation <= 220 // SHOULD; non-blocking
average_sentence_words recommendation 18..30 // SHOULD; non-blocking
word_cards == difficulty.vocabulary
word_card_groups == difficulty.vocabulary_distribution
collocations_per_card >= 2 && collocations_per_card <= 3
vocabulary_intersection_idioms == empty
difficult_sentences == difficulty.difficult_sentences
max_difficult_sentences_per_paragraph recommendation == 1 // SHOULD; non-blocking
idioms >= 3 && idioms <= 5
reading_questions == difficulty.questions
options_per_question == 4
question_evidence coverage recommendation includes {available paragraphs among 1, 2, 3, 4, last_paragraph} // SHOULD; non-blocking
answer_key.length == reading_questions
sources >= 1
source_url_uniqueness is not validated
source_number_matching is not validated
fact_audit_supported recommendation == true // SHOULD; non-blocking advisory
markdown_json_consistency == true
forbidden_construct_count == 0
```

## 13. 发布前硬性校验

生成器必须在落盘前执行第 12 节的全部断言。任何一项失败都应终止本次生成，不得把半成品提交到 GitHub Pages。

完整骨架如下；省略号仅用于说明，实际文件中不得出现：

```markdown
# English Title｜中文标题

规范版本：`1.0`

日期： `YYYY-MM-DD`｜词汇量：`N words`｜预计阅读时间：`N 分钟`｜CEFR：`LEVEL`｜来源：`OUTLET`

🏷 主题：`Theme · Topic`

⭐ 难度：星级

------

## 文章摘要

……

------

## Reading Passage

……

------

## 单词卡片

> 点开卡片查看词义、搭配和例句。

### 核心单词

……

### 固定搭配

……

### 短语动词

……

### 学术词

……

------

## 长难句理解

……

------

## 习语与地道表达

……

------

## 阅读理解

……

（答案：ABCD）


## 数据源

[Outlet] Title (https://example.com/)
```

## 14. Compatibility

### 14.1 Backward Compatibility

- v1.0 Parser 必须解析所有合法 v1.0 文档。
- 当前 Pages 可把没有版本行的历史文件标记为 `legacy` 并使用旧解析器；新生成文件不得使用 `legacy`。
- v1.1 及后续解析器必须继续接受 v1.0，除非主版本号升级并明确给出迁移工具。

### 14.2 Forward Compatibility

- 新增可选功能应提升次版本号，例如 v1.1 增加 AI Summary、v1.2 增加 Audio。
- 新字段应追加到既有结构，不得重命名或改变 v1.0 的七个章节名称及语义。
- 新增顶级章节必须在现有章节之后追加，并由新版本 Parser 显式启用；v1.0 Parser 可以拒绝未知章节，但不得静默误解析。
- 改变现有字段含义、删除字段、改变词汇卡 HTML 结构或章节顺序属于破坏性修改，必须提升主版本号。

### 14.3 Parser Dispatch

解析顺序固定为：读取 `规范版本` → 验证是否支持 → 选择对应 Parser → 执行该版本 Validation Rules。未知版本必须报告明确错误，不得猜测或回退到最新版。

## Appendix A. Word Card Template

以下是 v1.0 唯一合法的单词卡片模板。尖括号占位符必须替换为已转义内容；不得把占位符原样写入发布文件。

```html
<details class="word-card">
<summary><strong>&lt;TERM&gt;</strong> <span class="ipa">/&lt;IPA&gt;/</span> <code>&lt;POS&gt;</code></summary>
<div class="word-card-body">
<p><strong>释义</strong> &lt;MEANING_ZH&gt;</p>
<p><strong>常见搭配</strong> `&lt;COLLOCATION_1&gt;` · `&lt;COLLOCATION_2&gt;` · `&lt;OPTIONAL_COLLOCATION_3&gt;`</p>
<p><strong>例句</strong> &lt;EXAMPLE_SENTENCE&gt;</p>
</div>
</details>
```
