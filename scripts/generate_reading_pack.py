#!/usr/bin/env python3
from __future__ import annotations

import dataclasses
import datetime as dt
import html
import json
import os
import random
import re
import sys
import textwrap
import unicodedata
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import requests


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_FEEDS_FILE = BASE_DIR / "outputs" / "bbc-learning-feeds.opml"
SPEC_VERSION = "1.0"
VOCABULARY_BANNED_WORDS = {"the", "and", "government", "company"}


TOPIC_KEYWORDS = {
    "technology": ["tech", "technology", "software", "device", "chip", "internet", "startup", "digital"],
    "ai": ["ai", "artificial intelligence", "machine learning", "model", "algorithm", "chatbot", "automation"],
    "medicine": ["health", "medicine", "medical", "hospital", "drug", "vaccine", "disease", "therapy"],
    "business": ["business", "company", "market", "investor", "profit", "trade", "finance", "economy"],
    "environment": ["environment", "climate", "energy", "carbon", "renewable", "pollution", "wildfire", "nature"],
    "education": ["education", "school", "university", "college", "teacher", "student", "learning", "exam"],
}


@dataclasses.dataclass
class Feed:
    title: str
    url: str
    categories: list[str]


@dataclasses.dataclass
class Story:
    feed_title: str
    category: str
    title: str
    link: str
    published: str
    summary: str
    source_text: str = ""


class ArticleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_paragraph = False
        self.current: list[str] = []
        self.paragraphs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "p":
            self.in_paragraph = True
            self.current = []

    def handle_data(self, data: str) -> None:
        if self.in_paragraph:
            self.current.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "p" and self.in_paragraph:
            text = re.sub(r"\s+", " ", html.unescape("".join(self.current))).strip()
            if len(text.split()) >= 8:
                self.paragraphs.append(text)
            self.in_paragraph = False
            self.current = []


def fetch_article_text(story: Story) -> str:
    try:
        response = requests.get(
            story.link,
            headers={"User-Agent": "Mozilla/5.0 (compatible; DailyRead/1.0)"},
            timeout=30,
        )
        response.raise_for_status()
        parser = ArticleTextParser()
        parser.feed(response.text)
        paragraphs = list(dict.fromkeys(parser.paragraphs))
        article_text = "\n".join(paragraphs)
        if len(article_text.split()) >= 120:
            return article_text
    except (requests.RequestException, UnicodeError) as exc:
        eprint(f"Article fetch failed for {story.link}: {exc}")
    fallback = re.sub(r"<[^>]+>", " ", story.summary)
    return re.sub(r"\s+", " ", html.unescape(fallback)).strip()


def eprint(*args: Any) -> None:
    print(*args, file=sys.stderr)


def load_feeds(path: Path) -> list[Feed]:
    tree = ET.parse(path)
    root = tree.getroot()
    feeds: list[Feed] = []
    for outline in root.findall(".//outline"):
        xml_url = outline.attrib.get("xmlUrl")
        if not xml_url:
            continue
        title = outline.attrib.get("title") or outline.attrib.get("text") or xml_url
        category_raw = outline.attrib.get("category", "")
        categories = [c.strip().lower() for c in re.split(r"[,\s]+", category_raw) if c.strip()]
        feeds.append(Feed(title=title, url=xml_url, categories=categories))
    return feeds


def fetch_feed(url: str) -> list[Story]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        xml_data = resp.read()
    root = ET.fromstring(xml_data)
    channel = root.find("channel")
    feed_title = channel.findtext("title", default=url) if channel is not None else url
    stories: list[Story] = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        summary = (item.findtext("description") or "").strip()
        published = (
            item.findtext("pubDate")
            or item.findtext("{http://purl.org/dc/elements/1.1/}date")
            or ""
        ).strip()
        if title and link:
            stories.append(Story(feed_title=feed_title, category="", title=title, link=link, published=published, summary=summary))
    return stories


def infer_category(feed: Feed, story: Story) -> str:
    haystack = " ".join([feed.title, story.title, story.summary]).lower()
    scores = Counter()
    for category, keywords in TOPIC_KEYWORDS.items():
        for keyword in keywords:
            if keyword in haystack:
                scores[category] += 1
    if feed.categories:
        for category in feed.categories:
            scores[category] += 2
    if not scores:
        return (feed.categories[0] if feed.categories else "business")
    return scores.most_common(1)[0][0]


def choose_topic(stories_by_topic: dict[str, list[Story]], topic_override: str) -> str:
    if topic_override:
        normalized = topic_override.strip().lower()
        if normalized in stories_by_topic and stories_by_topic[normalized]:
            return normalized
    ranked = sorted(
        ((topic, len(stories)) for topic, stories in stories_by_topic.items() if stories),
        key=lambda x: (-x[1], x[0]),
    )
    if not ranked:
        raise SystemExit("No stories collected from any feed.")
    today_index = dt.date.today().toordinal() % len(ranked)
    return ranked[today_index][0]


QUESTION_TYPES = [
    "Main Idea", "Detail", "Inference", "Vocabulary in Context",
    "Author's Attitude", "Organization", "Title",
]

DIFFICULTY_PROFILES = {
    "middle": {
        "cefr": "A2-B1", "words": "500-700", "vocab": 8, "sentences": 2, "questions": 5,
        "vocab_distribution": {"core_word": 3, "fixed_collocation": 2, "phrasal_verb": 2, "academic_word": 1},
        "question_types": QUESTION_TYPES[:5],
        "audience": "middle-school learners; use concrete topics, common vocabulary, and short direct sentences",
    },
    "high": {
        "cefr": "B1-B2", "words": "700-900", "vocab": 10, "sentences": 3, "questions": 6,
        "vocab_distribution": {"core_word": 4, "fixed_collocation": 3, "phrasal_verb": 2, "academic_word": 1},
        "question_types": QUESTION_TYPES[:6],
        "audience": "high-school learners; use clear news prose with moderate detail and limited abstraction",
    },
    "college": {
        "cefr": "B2-C1", "words": "900-1200", "vocab": 10, "sentences": 4, "questions": 7,
        "vocab_distribution": {"core_word": 4, "fixed_collocation": 3, "phrasal_verb": 2, "academic_word": 1},
        "question_types": QUESTION_TYPES,
        "audience": "college learners; use nuanced reporting, varied sentence structures, and discipline-relevant vocabulary",
    },
    "advanced": {
        "cefr": "C1-C2", "words": "1000-1400", "vocab": 15, "sentences": 5, "questions": 8,
        "vocab_distribution": {"core_word": 6, "fixed_collocation": 4, "phrasal_verb": 3, "academic_word": 2},
        "question_types": QUESTION_TYPES + ["Application"],
        "audience": "advanced learners around IELTS 6.5-8.0 or TOEFL 90+; allow sophisticated vocabulary and complex syntax",
    },
    "proficiency": {
        "cefr": "C2+", "words": "1200-1800", "vocab": 30, "sentences": 10, "questions": 12,
        "vocab_distribution": {"core_word": 12, "fixed_collocation": 8, "phrasal_verb": 6, "academic_word": 4},
        "question_types": QUESTION_TYPES + ["Application", "Evidence", "Tone and Style", "Critical Evaluation", "Synthesis"],
        "audience": "near-native or highly proficient learners at TEM-8, GRE, GMAT Verbal, or Academic Reading level; allow academic expressions, complex syntax, and abstract argument",
    },
}

VOCABULARY_CATEGORIES = {
    "core_word": 4,
    "fixed_collocation": 3,
    "phrasal_verb": 2,
    "academic_word": 1,
}

POS_ABBREVIATIONS = {"n.", "v.", "adj.", "adv.", "phr.", "prep.", "conj.", "pron.", "det.", "int.", "num.", "abbr."}
VOCABULARY_SECTION_TITLES = {
    "core_word": "核心单词",
    "fixed_collocation": "固定搭配",
    "phrasal_verb": "短语动词",
    "academic_word": "学术词",
}
SUMMARY_BANNED_PHRASES = ("适合", "学习者", "词汇", "句型", "学习效果", "帮助读者", "阅读材料")


def build_prompt(topic: str, selected: list[Story], difficulty_name: str, profile: dict[str, Any], ledger: dict[str, list[str]] | None = None, original_passage: str | None = None) -> list[dict[str, str]]:
    original_mode = original_passage is not None
    items = []
    for idx, story in enumerate(selected, 1):
        items.append(
            f"SOURCE {idx}\n"
            f"   outlet: {story.feed_title}\n"
            f"   title: {story.title}\n"
            f"   link: {story.link}\n"
            f"   published: {story.published}"
        )
    source_references = "\n".join(items)
    source_material = (
        "LOCKED ORIGINAL PASSAGE:\n" + (original_passage or "")
        if original_mode
        else "FACT LEDGER — THE ONLY ALLOWED FACTS:\n" + json.dumps(ledger, ensure_ascii=False)
    )
    user_prompt = textwrap.dedent(
        f"""
        You are writing a publication-ready daily English reading pack for Chinese learners.
        Topic: {topic}
        Difficulty profile: {difficulty_name}
        Target learners: {profile['audience']}
        {"This is ORIGINAL-SOURCE mode. The reading passage below is locked news text. Do not rewrite, simplify, paraphrase, shorten, expand, or correct it. Generate only the learning analysis from this exact passage. Every vocabulary item, difficult sentence, idiom, question, answer, title, and summary must be grounded in it." if original_mode else "Use only the fact ledger below. It is the complete allow-list for this article. Do not invent named entities, statistics, quotations, legal context, market context, causal claims, comparisons, predictions, or claims beyond the ledger. Create a learner-friendly original article of " + str(profile['words']) + " words, with low repetition and natural journalistic style. Match the target learners' real language level. The article should be about one coherent news story or a tight cluster of stories related to the topic."}

        CONSISTENCY IS MANDATORY. The JSON will be rendered by a fixed Markdown template, so follow the schema, wording style, item order, punctuation, and counts exactly. Do not add Markdown to JSON values except ordinary paragraph breaks in reading_passage.

        EDITORIAL REQUIREMENTS:
        - Write in neutral, restrained, fact-led professional news prose. Do not use sensational, promotional, moralizing, conversational, first-person, or reader-addressing language.
        - Never include greetings, process commentary, completion notices, disclaimers, or AI self-reference such as "好的", "当然", "以下是", or "作为 AI" in any field.
        - For adapted passages, the target word range, 4-8 paragraph range, maximum 220 words per paragraph, and average sentence length of 18-30 words are editorial recommendations (SHOULD), not mandatory validity conditions. Prefer a clear background -> facts -> impact/explanation -> conclusion progression.
        - Keep vocabulary and sentence patterns varied without forcing obscure words or artificially long sentences.
        - Chinese explanations must be precise, idiomatic, concise, and specific. Avoid empty praise such as "值得学习", "表达生动", or "增强语言效果".
        - Vocabulary must be useful and transferable in the passage context. Do not select names, places, brands, trivial derivatives, basic stop words, or overly broad items such as the, and, government, or company.
        - Vocabulary examples must be original complete English sentences, not copied from the passage. Vocabulary and idiom entries must not duplicate each other after case and punctuation normalization.
        - Difficult-sentence analysis must identify the main clause, subordinate/non-finite structures, logical relationship, and useful construction where applicable; do not merely restate the translation. As a non-blocking editorial recommendation (SHOULD), select at most one sentence from any paragraph when the passage has enough paragraphs.
        - Idioms must occur in or be directly grounded in natural wording from the passage. Explain register, usage context, or restrictions; do not label arbitrary literal phrases as idioms.
        - Questions must be answerable from the passage alone. Use parallel, similarly plausible options with exactly one best answer; avoid double negatives, external knowledge, all/none-of-the-above, and answer-length clues.
        - As a non-blocking editorial recommendation (SHOULD), distribute question evidence across the passage and cover paragraphs 1, 2, 3, 4, and the conclusion when those paragraphs exist. Missing this coverage must not invalidate otherwise usable content.

        Output MUST be valid JSON with these keys:
        - title_en
        - title_zh
        - summary_zh
        - cefr
        - themes
        - difficulty
        - reading_passage
        - vocabulary
        - difficult_sentences
        - idioms
        - reading_questions
        - answer_key

        Field requirements:
        - title_en/title_zh: concise natural titles. They will appear as "English｜中文".
        - summary_zh: one factual Chinese summary paragraph only. State what happened, who was involved, and why it matters. Never mention learners, suitability, reading, vocabulary, grammar, learning outcomes, or the article's usefulness.
        - cefr: exactly "{profile['cefr']}".
        - themes: 1-3 concise English theme labels, e.g. ["Medicine", "Public Health"].
        - difficulty: integer from 1 to 5. This is provisional; the script will calculate the published star rating from the text.
        - reading_passage: {"set this field to the exact string __LOCKED_BY_SCRIPT__. The script will insert the original passage after generation; do not reproduce it in your response." if original_mode else str(profile['words']) + " English words, coherent paragraphs, no heading."}
        - vocabulary: exactly {profile['vocab']} items with category counts {json.dumps(profile['vocab_distribution'])}. Items must remain in category order. Each item contains category, word, ipa, pos, meaning_zh, collocations, example. category must be exactly one of those four labels. pos must be one of: n., v., adj., adv., phr., prep., conj. Use phr. for all fixed expressions and phrasal verbs; never use labels such as phr. n. or phr. v. collocations is a list of 2-3 common English collocations or usage patterns.
        - difficult_sentences: exactly {profile['sentences']} items, each with sentence, explanation_zh, grammar_point, translation_zh. Choose useful sentences that accurately reflect the reading passage.
        - idioms: 3-5 items, each with expression, meaning_zh, usage_note, example.
        - reading_questions: exactly {profile['questions']} multiple-choice objects in this exact type order: {', '.join(profile['question_types'])}. Each object contains type, question, options, answer, and evidence_paragraph. options is an object with exactly A, B, C, D. answer is one capital letter. evidence_paragraph is the 1-based paragraph number containing the main evidence. Across all questions, cover paragraphs 1, 2, 3, 4 and the concluding paragraph (when present).
        - answer_key: exactly {profile['questions']} answer letters as one string, with no spaces or punctuation, matching reading_questions. Correct option positions must vary naturally across A-D; do not use a fixed pattern.
        - {"If a point is absent from the locked original passage, omit it. Do not fill gaps with general knowledge or plausible analysis." if original_mode else "If a detail is absent from the fact ledger, omit it. Do not fill gaps with general knowledge or plausible analysis."}
        - Avoid sports, entertainment gossip, and political controversy.
        - Chinese prose must be idiomatic, precise, restrained, and consistent with a professional learning publication. Whenever an English word or expression appears inside Chinese explanatory prose, wrap it in Markdown inline code, for example `cause a backlash`.

        Source references:
        {source_references}

        {source_material}
        """
    ).strip()
    return [
        {"role": "system", "content": "You are a meticulous English reading-material editor. Exact schema and house-style compliance are mandatory."},
        {"role": "user", "content": user_prompt},
    ]


def call_deepseek(messages: list[dict[str, str]], temperature: float = 0.6) -> dict[str, Any]:
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("DEEPSEEK_API_KEY is required.")
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash").strip()
    url = "https://api.deepseek.com/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=180,
    )
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"].get("content", "")
    if not content:
        raise RuntimeError("DeepSeek returned empty content.")
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    return json.loads(content)


def extract_fact_ledger(sources: list[Story]) -> dict[str, list[str]]:
    source_text = "\n\n".join(
        f"SOURCE {index}: {story.title}\n{story.source_text[:6000]}"
        for index, story in enumerate(sources, 1)
    )
    messages = [
        {"role": "system", "content": "Extract facts conservatively. Use only supplied text. Return JSON only."},
        {"role": "user", "content": textwrap.dedent(f"""
            Build a fact ledger for a news-learning article. Return exactly this JSON object:
            {{"entities": [string], "numbers": [string], "facts": [string], "quotes": [string]}}.

            Rules:
            - Include only facts explicitly stated in the sources.
            - facts must be short, neutral, and concrete; include at most 20.
            - entities and numbers must occur verbatim in the sources.
            - quotes are optional and must be exact source quotations of no more than 20 words.
            - Do not infer consequences, give context from general knowledge, or add companies, laws, statistics, or opinions not stated in the sources.

            SOURCES:
            {source_text}
        """).strip()},
    ]
    ledger = call_deepseek(messages, temperature=0.0)
    if set(ledger) != {"entities", "numbers", "facts", "quotes"}:
        raise ValueError("Fact ledger returned an invalid schema.")
    for key, values in ledger.items():
        if not isinstance(values, list) or not all(isinstance(value, str) and value.strip() for value in values):
            raise ValueError(f"Fact ledger field is invalid: {key}")
    if not ledger["facts"]:
        raise ValueError("Fact ledger contains no usable facts.")
    return ledger


def assess_text_difficulty(passage: str) -> tuple[str, int]:
    words = re.findall(r"[A-Za-z]+(?:['’-][A-Za-z]+)*", passage)
    sentences = [part for part in re.split(r"[.!?]+", passage) if part.strip()]
    if not words or not sentences:
        return "B1", 1
    average_sentence_length = len(words) / len(sentences)
    long_word_ratio = sum(len(word) >= 8 for word in words) / len(words)
    connector_ratio = sum(
        word.lower() in {"although", "because", "however", "therefore", "whereas", "while", "despite", "whether"}
        for word in words
    ) / len(words)
    complexity = average_sentence_length + (long_word_ratio * 30) + (connector_ratio * 60)
    if complexity < 16:
        return "B1", 1
    if complexity < 21:
        return "B2", 2 if complexity < 18 else 3
    if complexity < 27:
        return "C1", 4
    return "C2", 5


def apply_text_assessment(payload: dict[str, Any], profile: dict[str, Any]) -> None:
    _, payload["difficulty"] = assess_text_difficulty(payload["reading_passage"])
    payload["cefr"] = profile["cefr"]


def select_original_excerpt(story: Story, profile: dict[str, Any]) -> str:
    """Select a continuous, attributed news excerpt without altering its wording."""
    paragraphs = [paragraph.strip() for paragraph in story.source_text.splitlines() if paragraph.strip()]
    if not paragraphs:
        return story.source_text.strip()
    lower, upper = (int(value) for value in profile["words"].split("-"))
    target = (lower + upper) // 2
    best: tuple[int, int, int] | None = None
    for start in range(len(paragraphs)):
        count = 0
        for end in range(start, len(paragraphs)):
            count += len(re.findall(r"[A-Za-z]+(?:['’-][A-Za-z]+)*", paragraphs[end]))
            if count >= lower:
                candidate = (abs(count - target) + (10000 if count > upper else 0), start, end + 1)
                if best is None or candidate < best:
                    best = candidate
                break
    if best:
        _, start, end = best
        return "\n\n".join(paragraphs[start:end])
    return "\n\n".join(paragraphs)


def randomize_answer_positions(payload: dict[str, Any]) -> None:
    questions = payload.get("reading_questions", [])
    if not questions:
        return
    seed = sum(ord(char) for char in payload.get("title_en", "")) + len(questions)
    rng = random.Random(seed)
    for question in questions:
        target = rng.choice("ABCD")
        options = question.get("options", {})
        correct_letter = question.get("answer")
        if correct_letter not in options or set(options) != set("ABCD"):
            continue
        correct_option = options[correct_letter]
        remaining = [options[letter] for letter in "ABCD" if letter != correct_letter]
        new_options: dict[str, str] = {}
        for letter in "ABCD":
            new_options[letter] = correct_option if letter == target else remaining.pop(0)
        question["options"] = new_options
        question["answer"] = target
    payload["answer_key"] = "".join(question["answer"] for question in questions)


def render_markdown(payload: dict[str, Any], topic: str, sources: list[Story], content_mode: str = "adapted") -> str:
    passage = payload["reading_passage"].strip()
    word_count = len(re.findall(r"\b[A-Za-z]+(?:['’-][A-Za-z]+)*\b", passage))
    reading_minutes = max(1, round(word_count / 130))
    stars = "★" * payload["difficulty"] + "☆" * (5 - payload["difficulty"])
    lines = [f"# {payload['title_en']}｜{payload['title_zh']}", "", f"规范版本：`{SPEC_VERSION}`", ""]
    source_label = " · ".join(sorted(set(story.feed_title for story in sources)))
    lines.append(
        f"日期： `{dt.date.today().isoformat()}`｜词汇量：`{word_count:,} words`｜"
        f"预计阅读时间：`{reading_minutes} 分钟`｜CEFR：`{payload['cefr']}`｜来源：`{source_label}`"
    )
    lines.extend(["", f"🏷 主题：`{' · '.join(payload['themes'])}`", "", f"⭐ 难度：{stars}", "", "------", ""])
    if content_mode != "adapted":
        mode_label = "新闻原文连续节选" if content_mode == "original-adapt" else "新闻原文全文"
        lines.extend([f"> 正文模式：{mode_label}。正文未经 AI 改写；学习分析由 AI 基于该文本生成。", "", "------", ""])
    lines.extend(["## 文章摘要", "", payload["summary_zh"].strip(), "", "------", ""])
    lines.extend([
        "## Reading Passage", "", passage, "", "------", "", "## 单词卡片", "",
        "> 点开卡片查看词义、搭配和例句。", "",
    ])
    for category in VOCABULARY_CATEGORIES:
        category_items = [item for item in payload["vocabulary"] if item["category"] == category]
        lines.extend([f"### {VOCABULARY_SECTION_TITLES[category]}", ""])
        for index, item in enumerate(category_items, 1):
            collocations = item["collocations"]
            if isinstance(collocations, list):
                collocations = " · ".join(f"`{value}`" for value in collocations)
            else:
                collocations = f"`{collocations}`"
            lines.extend([
                '<details class="word-card">',
                f'<summary><strong>{html.escape(str(item["word"]))}</strong> '
                f'<span class="ipa">/{html.escape(str(item["ipa"]).strip("/[]"))}/</span> '
                f'<code>{html.escape(str(item["pos"]))}</code></summary>',
                '<div class="word-card-body">',
                f'<p><strong>释义</strong> {html.escape(str(item["meaning_zh"]))}</p>',
                f'<p><strong>常见搭配</strong> {collocations}</p>',
                f'<p><strong>例句</strong> {html.escape(str(item["example"]))}</p>',
                '</div>',
                '</details>', "",
            ])
    lines.extend(["------", "", "## 长难句理解", ""])
    for item in payload["difficult_sentences"]:
        lines.extend([
            f"> {item['sentence']}", "",
            f"**语法要点：**{item['grammar_point']}", "",
            f"**分析：**{item['explanation_zh']}", "",
            f"**翻译：**{item['translation_zh']}", "", "",
        ])
    lines.extend(["------", "", "## 习语与地道表达", ""])
    for item in payload["idioms"]:
        lines.extend([
            f"**{item['expression']}** {item['meaning_zh']}", "",
            item["usage_note"], "", f"例句：{item['example']}", "", "",
        ])
    lines.extend(["------", "", "## 阅读理解", ""])
    for idx, q in enumerate(payload["reading_questions"], 1):
        lines.extend([f"{idx}. **{q['question']}**", ""])
        for letter in "ABCD":
            lines.extend([f"{letter}. {q['options'][letter]}", ""])
        lines.extend(["------", ""])
    lines.extend([f"（答案：{payload['answer_key']}）", "", "", "## 数据源", ""])
    for story in sources:
        lines.extend([f"[{story.feed_title}] {story.title} ({story.link})", ""])
    lines.append("")
    return "\n".join(lines)


def validate_rendered_markdown(markdown_text: str, payload: dict[str, Any], profile: dict[str, Any], sources: list[Story]) -> None:
    """Reject rendered files that drift from the Markdown publication contract."""
    expected_headings = [
        "## 文章摘要", "## Reading Passage", "## 单词卡片", "## 长难句理解",
        "## 习语与地道表达", "## 阅读理解", "## 数据源",
    ]
    actual_headings = re.findall(r"(?m)^## .+$", markdown_text)
    if actual_headings != expected_headings:
        raise ValueError(f"Markdown section order is invalid: {actual_headings}")
    allowed_headings = {
        f"# {payload['title_en']}｜{payload['title_zh']}",
        *expected_headings,
        *(f"### {VOCABULARY_SECTION_TITLES[key]}" for key in VOCABULARY_CATEGORIES),
    }
    emitted_headings = re.findall(r"(?m)^#{1,6} .+$", markdown_text)
    if any(heading not in allowed_headings for heading in emitted_headings):
        raise ValueError("Markdown contains a heading not allowed by specification v1.0.")
    if len(re.findall(r"(?m)^# [^#].+$", markdown_text)) != 1:
        raise ValueError("Markdown must contain exactly one level-one bilingual title.")
    if not re.search(r"(?m)^# .+｜.+$", markdown_text):
        raise ValueError("Markdown title must use the full-width separator ｜.")
    if f"# {payload['title_en']}｜{payload['title_zh']}" not in markdown_text:
        raise ValueError("Markdown and JSON titles are inconsistent.")
    if not re.search(rf"(?m)^规范版本：`{re.escape(SPEC_VERSION)}`$", markdown_text):
        raise ValueError("Markdown specification version is missing or unsupported.")
    if payload.get("spec_version") != SPEC_VERSION:
        raise ValueError("Markdown and JSON specification versions are inconsistent.")
    forbidden_patterns = {
        "fenced code block": r"(?m)^```",
        "YAML front matter": r"(?m)^---\s*$",
        "HTML comment": r"<!--",
        "Markdown table": r"(?m)^\s*\|.*\|\s*$",
        "AI preamble": r"(?m)^(?:好的|当然|以下是|作为(?:一个)?AI).*$",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, markdown_text):
            raise ValueError(f"Markdown contains forbidden {label}.")
    metadata_pattern = (
        r"(?m)^日期： `\d{4}-\d{2}-\d{2}`｜词汇量：`[\d,]+ words`｜"
        r"预计阅读时间：`\d+ 分钟`｜CEFR：`[^`]+`｜来源：`[^`]+`$"
    )
    if not re.search(metadata_pattern, markdown_text):
        raise ValueError("Markdown metadata line does not match the standard template.")
    if not re.search(r"(?m)^🏷 主题：`[^`]+`$", markdown_text):
        raise ValueError("Markdown theme line is invalid.")
    if f"## 文章摘要\n\n{payload['summary_zh'].strip()}\n" not in markdown_text:
        raise ValueError("Markdown and JSON summaries are inconsistent.")
    if f"## Reading Passage\n\n{payload['reading_passage'].strip()}\n" not in markdown_text:
        raise ValueError("Markdown and JSON reading passages are inconsistent.")
    star_match = re.search(r"(?m)^⭐ 难度：([★☆]+)$", markdown_text)
    if not star_match or len(star_match.group(1)) != 5 or "☆★" in star_match.group(1):
        raise ValueError("Markdown difficulty must contain five ordered stars.")
    expected_groups = [f"### {VOCABULARY_SECTION_TITLES[key]}" for key in VOCABULARY_CATEGORIES]
    if re.findall(r"(?m)^### .+$", markdown_text) != expected_groups:
        raise ValueError("Markdown vocabulary groups or their order are invalid.")
    card_count = markdown_text.count('<details class="word-card">')
    if card_count != profile["vocab"] or markdown_text.count("</details>") != card_count:
        raise ValueError(f"Markdown must contain exactly {profile['vocab']} complete word cards.")
    for label in ("释义", "常见搭配", "例句"):
        if markdown_text.count(f"<p><strong>{label}</strong>") != card_count:
            raise ValueError(f"Every word card must contain the {label} field.")
    for item in payload["vocabulary"]:
        if f"<strong>{html.escape(str(item['word']))}</strong>" not in markdown_text:
            raise ValueError("Markdown and JSON vocabulary entries are inconsistent.")
    for item in payload["difficult_sentences"]:
        if f"> {item['sentence']}" not in markdown_text:
            raise ValueError("A difficult sentence is missing or differs from the passage.")
    quiz_section = markdown_text.split("## 阅读理解", 1)[1].split("## 数据源", 1)[0]
    question_numbers = [int(value) for value in re.findall(r"(?m)^(\d+)\. \*\*.+\*\*$", quiz_section)]
    if question_numbers != list(range(1, profile["questions"] + 1)):
        raise ValueError("Markdown quiz numbering/count is invalid.")
    for letter in "ABCD":
        if len(re.findall(rf"(?m)^{letter}\. .+$", quiz_section)) != profile["questions"]:
            raise ValueError(f"Every quiz question must contain option {letter}.")
    if f"（答案：{payload['answer_key']}）" not in quiz_section:
        raise ValueError("Markdown answer key is missing or inconsistent.")
    for question in payload["reading_questions"]:
        if f"**{question['question']}**" not in quiz_section:
            raise ValueError("Markdown and JSON quiz questions are inconsistent.")
        for letter in "ABCD":
            if f"{letter}. {question['options'][letter]}" not in quiz_section:
                raise ValueError("Markdown and JSON quiz options are inconsistent.")
    source_section = markdown_text.split("## 数据源", 1)[1]
    source_lines = re.findall(r"(?m)^\[[^\]]+\] .+ \(https://[^)]+\)$", source_section)
    if len(source_lines) != len(sources):
        raise ValueError("Markdown data-source lines do not match the selected sources.")
    expected_source_lines = [f"[{item['outlet']}] {item['title']} ({item['url']})" for item in payload.get("sources", [])]
    if source_lines != expected_source_lines:
        raise ValueError("Markdown and JSON data sources are inconsistent.")


def normalize_evidence(text: str) -> str:
    text = unicodedata.normalize("NFKC", html.unescape(text)).casefold()
    text = text.replace("'", "").replace("’", "")
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def token_similarity(left: str, right: str) -> float:
    left_tokens = normalize_evidence(left).split()
    right_tokens = normalize_evidence(right).split()
    if not left_tokens or not right_tokens:
        return 0.0
    shared = sum((Counter(left_tokens) & Counter(right_tokens)).values())
    return (2 * shared) / (len(left_tokens) + len(right_tokens))


def quote_matches_source(quote: str, source: str) -> bool:
    quote_tokens = normalize_evidence(quote).split()
    source_tokens = normalize_evidence(source).split()
    if not quote_tokens or not source_tokens:
        return False
    phrase = " ".join(quote_tokens)
    if phrase in " ".join(source_tokens):
        return True
    window_min = max(1, len(quote_tokens) - 3)
    window_max = min(len(source_tokens), len(quote_tokens) + 3)
    for start, token in enumerate(source_tokens):
        if token != quote_tokens[0]:
            continue
        for size in range(window_min, window_max + 1):
            window = source_tokens[start:start + size]
            if len(window) < window_min:
                continue
            if token_similarity(" ".join(quote_tokens), " ".join(window)) >= 0.88:
                return True
    return False


def repair_difficult_sentences(payload: dict[str, Any]) -> None:
    passage = payload.get("reading_passage", "")
    passage_sentences = re.split(r"(?<=[.!?])\s+", passage.strip())
    for item in payload.get("difficult_sentences", []):
        sentence = item.get("sentence", "")
        normalized = normalize_evidence(sentence)
        if normalized and normalized in normalize_evidence(passage):
            continue
        candidate = max(passage_sentences, key=lambda value: token_similarity(sentence, value), default="")
        if token_similarity(sentence, candidate) < 0.84:
            raise ValueError("A difficult sentence cannot be aligned to the reading passage.")
        item["sentence"] = candidate.strip()


def validate_payload(payload: dict[str, Any], sources: list[Story], profile: dict[str, Any]) -> None:
    required = [
        "title_zh",
        "title_en",
        "summary_zh",
        "cefr",
        "themes",
        "difficulty",
        "reading_passage",
        "vocabulary",
        "difficult_sentences",
        "idioms",
        "reading_questions",
        "answer_key",
    ]
    for key in required:
        if key not in payload:
            raise ValueError(f"Missing key: {key}")
    if payload["cefr"] != profile["cefr"]:
        raise ValueError(f"cefr must be {profile['cefr']}.")
    paragraphs = [value.strip() for value in re.split(r"\n\s*\n", payload["reading_passage"].strip()) if value.strip()]
    paragraph_word_counts = [len(re.findall(r"[A-Za-z]+(?:['’-][A-Za-z]+)*", value)) for value in paragraphs]
    if not paragraphs or not any(paragraph_word_counts):
        raise ValueError("Reading passage must contain non-empty English prose.")
    if not isinstance(payload["themes"], list) or not 1 <= len(payload["themes"]) <= 3:
        raise ValueError("themes must contain 1-3 labels.")
    if not isinstance(payload["difficulty"], int) or not 1 <= payload["difficulty"] <= 5:
        raise ValueError("difficulty must be an integer from 1 to 5.")
    if any(phrase in payload["summary_zh"] for phrase in SUMMARY_BANNED_PHRASES):
        raise ValueError("summary_zh contains learning-oriented rather than factual content.")
    vocabulary = payload["vocabulary"]
    if not isinstance(vocabulary, list) or len(vocabulary) != profile["vocab"]:
        raise ValueError(f"Expected exactly {profile['vocab']} vocabulary items.")
    categories = [item.get("category") for item in vocabulary]
    expected = [category for category, count in profile["vocab_distribution"].items() for _ in range(count)]
    if categories != expected:
        raise ValueError(f"Vocabulary category order/count is invalid: {categories}")
    vocab_keys = {"category", "word", "ipa", "pos", "meaning_zh", "collocations", "example"}
    for item in vocabulary:
        if not vocab_keys.issubset(item) or not all(item[key] for key in vocab_keys):
            raise ValueError("A vocabulary item is incomplete.")
        if item["pos"] not in POS_ABBREVIATIONS:
            raise ValueError(f"Unsupported vocabulary part of speech: {item['pos']}")
        if not isinstance(item["collocations"], list) or not 2 <= len(item["collocations"]) <= 3:
            raise ValueError("Every vocabulary item must contain 2-3 collocations.")
        if not all(isinstance(value, str) and value.strip() for value in item["collocations"]):
            raise ValueError("Vocabulary collocations must be non-empty strings.")
        if not re.search(r"[.!?]$", item["example"].strip()):
            raise ValueError("Every vocabulary example must end with sentence punctuation.")
        if item["word"].strip().casefold() in VOCABULARY_BANNED_WORDS:
            raise ValueError(f"Vocabulary item is forbidden: {item['word']}")
    if len(payload["difficult_sentences"]) != profile["sentences"]:
        raise ValueError(f"Expected exactly {profile['sentences']} difficult sentences.")
    normalized_passage = normalize_evidence(payload["reading_passage"])
    for item in payload["difficult_sentences"]:
        sentence_keys = {"sentence", "explanation_zh", "grammar_point", "translation_zh"}
        if not sentence_keys.issubset(item) or not all(item[key] for key in sentence_keys):
            raise ValueError("A difficult-sentence item is incomplete.")
        if normalize_evidence(item["sentence"]) not in normalized_passage:
            raise ValueError("Every difficult sentence must occur verbatim in the reading passage.")
    selected_paragraphs: list[int] = []
    for item in payload["difficult_sentences"]:
        matches = [index for index, paragraph in enumerate(paragraphs, 1) if normalize_evidence(item["sentence"]) in normalize_evidence(paragraph)]
        if not matches:
            raise ValueError("A difficult sentence cannot be mapped to a passage paragraph.")
        selected_paragraphs.append(matches[0])
    if not isinstance(payload["idioms"], list) or not 3 <= len(payload["idioms"]) <= 5:
        raise ValueError("Expected 3-5 idiomatic expressions.")
    idiom_keys = {"expression", "meaning_zh", "usage_note", "example"}
    for item in payload["idioms"]:
        if not idiom_keys.issubset(item) or not all(item[key] for key in idiom_keys):
            raise ValueError("An idiomatic-expression item is incomplete.")
        if not re.search(r"[.!?]$", item["example"].strip()):
            raise ValueError("Every idiom example must end with sentence punctuation.")
    vocabulary_terms = {normalize_evidence(item["word"]) for item in vocabulary}
    idiom_terms = {normalize_evidence(item["expression"]) for item in payload["idioms"]}
    if vocabulary_terms & idiom_terms:
        raise ValueError("Vocabulary and idiomatic-expression entries must not overlap.")
    questions = payload["reading_questions"]
    if not isinstance(questions, list) or len(questions) != profile["questions"]:
        raise ValueError(f"Expected exactly {profile['questions']} reading questions.")
    if [q.get("type") for q in questions] != profile["question_types"]:
        raise ValueError("Question types or order do not match the house style.")
    for question in questions:
        if set(question.get("options", {})) != set("ABCD"):
            raise ValueError("Every question must have exactly A-D options.")
        if question.get("answer") not in "ABCD":
            raise ValueError("Every question must have one A-D answer.")
        if not isinstance(question.get("evidence_paragraph"), int) or not 1 <= question["evidence_paragraph"] <= len(paragraphs):
            raise ValueError("Every question must reference a valid 1-based evidence_paragraph.")
    expected_key = "".join(question["answer"] for question in questions)
    if payload["answer_key"] != expected_key:
        raise ValueError(f"answer_key must be {expected_key}.")


def audit_facts(payload: dict[str, Any], sources: list[Story]) -> dict[str, Any]:
    source_text = "\n\n".join(
        f"SOURCE {idx}: {story.title}\n{story.source_text[:6000]}" for idx, story in enumerate(sources, 1)
    )
    messages = [
        {"role": "system", "content": "You are a strict fact checker. Use only supplied sources. Return JSON only."},
        {"role": "user", "content": textwrap.dedent(f"""
            Check the reading passage against the source texts. Treat unsupported names, numbers, quotations,
            causal statements, research findings, and overconfident generalizations as errors.
            Return exactly: {{"supported": true_or_false, "issues": ["specific issue", ...]}}.
            Do not judge style or Markdown. If uncertain, set supported to false.

            READING PASSAGE:
            {payload['reading_passage']}

            SOURCES:
            {source_text}
        """).strip()},
    ]
    result = call_deepseek(messages, temperature=0.0)
    if set(result) != {"supported", "issues"} or not isinstance(result["supported"], bool) or not isinstance(result["issues"], list):
        raise ValueError("Fact checker returned an invalid schema.")
    return result


def generate_with_retries(messages: list[dict[str, str]], sources: list[Story], profile: dict[str, Any], attempts: int = 2, original_passage: str | None = None) -> dict[str, Any]:
    errors: list[str] = []
    current_messages = list(messages)
    for attempt in range(1, attempts + 1):
        try:
            payload = call_deepseek(current_messages)
            if original_passage is not None:
                payload["reading_passage"] = original_passage
            apply_text_assessment(payload, profile)
            randomize_answer_positions(payload)
            validate_payload(payload, sources, profile)
            if original_passage is not None:
                return payload
            audit = audit_facts(payload, sources)
            if not audit["supported"]:
                issues = [str(issue) for issue in audit["issues"][:5]]
                eprint("Fact checker advisory (non-blocking): " + "; ".join(issues))
            return payload
        except (ValueError, KeyError, TypeError, RuntimeError, json.JSONDecodeError, requests.RequestException) as exc:
            errors.append(f"attempt {attempt}: {exc}")
            eprint(f"Generation rejected ({attempt}/{attempts}): {exc}")
            if attempt == attempts:
                break
            current_messages += [
                {"role": "assistant", "content": "The previous response failed validation."},
                {"role": "user", "content": f"Validation error: {exc}. Regenerate the entire JSON from scratch and obey every schema, count, order, and style rule exactly."},
            ]
    raise RuntimeError("DeepSeek output failed validation after retries: " + " | ".join(errors))


def main() -> None:
    feeds_file = Path(os.environ.get("NEWS_FEEDS_FILE", str(DEFAULT_FEEDS_FILE)))
    output_dir = Path(os.environ.get("OUTPUT_DIR", str(BASE_DIR / "outputs" / "generated")))
    topic_override = os.environ.get("TOPIC_OVERRIDE", "").strip().lower()
    difficulty_name = os.environ.get("DIFFICULTY_LEVEL", "college").strip().lower()
    content_mode = os.environ.get("CONTENT_MODE", "original-adapt").strip().lower()
    if difficulty_name not in DIFFICULTY_PROFILES:
        raise SystemExit(f"Invalid DIFFICULTY_LEVEL: {difficulty_name}. Choose from {', '.join(DIFFICULTY_PROFILES)}")
    profile = DIFFICULTY_PROFILES[difficulty_name]
    if content_mode not in {"adapted", "original-adapt", "original-full"}:
        raise SystemExit("Invalid CONTENT_MODE: choose adapted, original-adapt, or original-full.")
    if content_mode == "original-adapt" and difficulty_name not in {"high", "college", "advanced"}:
        raise SystemExit("original-adapt supports high, college, or advanced difficulty because it preserves source wording.")
    output_dir.mkdir(parents=True, exist_ok=True)

    feeds = load_feeds(feeds_file)
    stories_by_topic: dict[str, list[Story]] = defaultdict(list)

    for feed in feeds:
        try:
            stories = fetch_feed(feed.url)
        except (urllib.error.URLError, TimeoutError, ET.ParseError, requests.RequestException) as exc:
            eprint(f"Skipping feed {feed.url}: {exc}")
            continue
        for story in stories[:20]:
            story.category = infer_category(feed, story)
            stories_by_topic[story.category].append(story)

    if not stories_by_topic:
        raise SystemExit("No stories were collected.")

    topic = choose_topic(stories_by_topic, topic_override)
    selected = stories_by_topic[topic]
    selected = sorted(selected, key=lambda s: (s.published, s.title), reverse=True)[:2]
    for story in selected:
        story.source_text = fetch_article_text(story)
    selected = [story for story in selected if len(story.source_text.split()) >= 20]
    if not selected:
        raise SystemExit("No selected story had enough source text for grounded generation.")

    original_passage: str | None = None
    if content_mode != "adapted":
        # A single source keeps the original text, attribution, questions, and analysis aligned.
        selected = [selected[0]]
        original_passage = (
            select_original_excerpt(selected[0], profile)
            if content_mode == "original-adapt"
            else selected[0].source_text.strip()
        )
        if not original_passage:
            raise SystemExit("The selected source has no usable original text.")
        messages = build_prompt(topic, selected, difficulty_name, profile, original_passage=original_passage)
    else:
        ledger = extract_fact_ledger(selected)
        messages = build_prompt(topic, selected, difficulty_name, profile, ledger=ledger)
    payload = generate_with_retries(messages, selected, profile, original_passage=original_passage)
    payload["content_mode"] = content_mode
    payload["spec_version"] = SPEC_VERSION
    payload["sources"] = [
        {"outlet": story.feed_title, "title": story.title, "url": story.link}
        for story in selected
    ]

    today = dt.date.today().isoformat()
    json_path = output_dir / f"{today}.json"
    md_path = output_dir / f"{today}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_text = render_markdown(payload, topic, selected, content_mode)
    validate_rendered_markdown(markdown_text, payload, profile, selected)
    md_path.write_text(markdown_text, encoding="utf-8")
    eprint(f"Wrote {json_path}")
    eprint(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
