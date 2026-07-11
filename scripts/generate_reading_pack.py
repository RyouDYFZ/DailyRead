#!/usr/bin/env python3
from __future__ import annotations

import dataclasses
import datetime as dt
import html
import json
import os
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
            return article_text[:12000]
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

VOCABULARY_CATEGORIES = {
    "core_word": 4,
    "fixed_collocation": 3,
    "phrasal_verb": 2,
    "academic_word": 1,
}


def build_prompt(topic: str, selected: list[Story]) -> list[dict[str, str]]:
    items = []
    for idx, story in enumerate(selected, 1):
        items.append(
            f"SOURCE {idx}\n"
            f"   outlet: {story.feed_title}\n"
            f"   title: {story.title}\n"
            f"   link: {story.link}\n"
            f"   published: {story.published}\n"
            f"   source text:\n{story.source_text[:6000]}"
        )
    user_prompt = textwrap.dedent(
        f"""
        You are writing a publication-ready daily English reading pack for Chinese learners.
        Topic: {topic}
        Use only the source facts below. Do not invent named entities, statistics, or claims.
        Create a learner-friendly original article in CEFR B2-C1 level, aiming for about 600-900 words, with low repetition and natural journalistic style. Prioritize factual completeness and clarity over an exact word count.
        The article should be about one coherent news story or a tight cluster of stories related to the topic.

        CONSISTENCY IS MANDATORY. The JSON will be rendered by a fixed Markdown template, so follow the schema, wording style, item order, punctuation, and counts exactly. Do not add Markdown to JSON values except ordinary paragraph breaks in reading_passage.

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
        - summary_zh: one polished Chinese paragraph summarizing the article and its learning value.
        - cefr: exactly "B2", "B2-C1", or "C1".
        - themes: 1-3 concise English theme labels, e.g. ["Medicine", "Public Health"].
        - difficulty: integer from 3 to 5.
        - reading_passage: aim for about 600-900 English words, coherent paragraphs, no heading. This is a target, not a hard limit.
        - vocabulary: exactly 10 items in this exact order: 4 core_word, 3 fixed_collocation, 2 phrasal_verb, 1 academic_word. Each item contains category, word, ipa, pos, meaning_zh, collocations, example. category must be exactly one of those four labels. For multiword entries, still provide natural IPA and a suitable POS label. collocations is a list of 2-3 common English collocations or usage patterns.
        - difficult_sentences: 3-5 items, each with sentence, explanation_zh, grammar_point, translation_zh. Choose useful sentences that accurately reflect the reading passage.
        - idioms: 3-5 items, each with expression, meaning_zh, usage_note, example.
        - reading_questions: exactly 7 multiple-choice objects in this exact type order: Main Idea, Detail, Inference, Vocabulary in Context, Author's Attitude, Organization, Title. Each object contains type, question, options and answer. options is an object with exactly A, B, C, D. answer is one capital letter.
        - answer_key: exactly the seven answer letters as one string, with no spaces or punctuation, matching reading_questions.
        - Never introduce a number, date, proper name, quotation, causal claim, or research finding that is absent from the source text.
        - Avoid sports, entertainment gossip, and political controversy.
        - Chinese prose must be idiomatic, precise, restrained, and consistent with a professional learning publication.

        Source facts:
        {chr(10).join(items)}
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


def render_markdown(payload: dict[str, Any], topic: str, sources: list[Story]) -> str:
    passage = payload["reading_passage"].strip()
    word_count = len(re.findall(r"\b[A-Za-z]+(?:['’-][A-Za-z]+)*\b", passage))
    reading_minutes = max(1, round(word_count / 130))
    stars = "★" * payload["difficulty"] + "☆" * (5 - payload["difficulty"])
    lines = [f"# {payload['title_en']}｜{payload['title_zh']}", ""]
    lines.append(
        f"日期： `{dt.date.today().isoformat()}`｜词汇量：`{word_count:,} words`｜"
        f"预计阅读时间：`{reading_minutes} 分钟`｜CEFR：`{payload['cefr']}`｜来源：`BBC News`"
    )
    lines.extend(["", f"🏷 主题：`{' · '.join(payload['themes'])}`", "", f"⭐ 难度：{stars}", "", "------", ""])
    lines.extend(["## 文章摘要", "", payload["summary_zh"].strip(), "", "------", ""])
    lines.extend(["## Reading Passage", "", passage, "", "------", "", "## 单词积累", ""])
    for item in payload["vocabulary"]:
        collocations = item["collocations"]
        if isinstance(collocations, list):
            collocations = "; ".join(collocations)
        lines.extend([
            f"**{item['word']}** [/{item['ipa'].strip('/[]')}/]", "",
            f"**{item['pos']}** {item['meaning_zh']}", "",
            f"常见搭配：{collocations}", "",
            f"例句：{item['example']}", "", "",
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


def validate_payload(payload: dict[str, Any], sources: list[Story]) -> None:
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
    if payload["cefr"] not in {"B2", "B2-C1", "C1"}:
        raise ValueError("cefr must be B2, B2-C1, or C1.")
    if not isinstance(payload["themes"], list) or not 1 <= len(payload["themes"]) <= 3:
        raise ValueError("themes must contain 1-3 labels.")
    if not isinstance(payload["difficulty"], int) or not 3 <= payload["difficulty"] <= 5:
        raise ValueError("difficulty must be an integer from 3 to 5.")
    vocabulary = payload["vocabulary"]
    if not isinstance(vocabulary, list) or len(vocabulary) != 10:
        raise ValueError("Expected exactly 10 vocabulary items.")
    categories = [item.get("category") for item in vocabulary]
    expected = [category for category, count in VOCABULARY_CATEGORIES.items() for _ in range(count)]
    if categories != expected:
        raise ValueError(f"Vocabulary category order/count is invalid: {categories}")
    vocab_keys = {"category", "word", "ipa", "pos", "meaning_zh", "collocations", "example"}
    for item in vocabulary:
        if not vocab_keys.issubset(item) or not all(item[key] for key in vocab_keys):
            raise ValueError("A vocabulary item is incomplete.")
    if not 3 <= len(payload["difficult_sentences"]) <= 5:
        raise ValueError("Expected 3-5 difficult sentences.")
    questions = payload["reading_questions"]
    if not isinstance(questions, list) or len(questions) != 7:
        raise ValueError("Expected exactly 7 reading questions.")
    if [q.get("type") for q in questions] != QUESTION_TYPES:
        raise ValueError("Question types or order do not match the house style.")
    for question in questions:
        if set(question.get("options", {})) != set("ABCD"):
            raise ValueError("Every question must have exactly A-D options.")
        if question.get("answer") not in "ABCD":
            raise ValueError("Every question must have one A-D answer.")
    expected_key = "".join(question["answer"] for question in questions)
    if payload["answer_key"] != expected_key:
        raise ValueError(f"answer_key must be {expected_key}.")
    source_corpus = normalize_evidence(" ".join(
        f"{story.title} {story.published} {story.source_text}" for story in sources
    ))
    passage_numbers = set(re.findall(r"(?<!\w)\d+(?:[.,]\d+)*(?:%|st|nd|rd|th)?", payload["reading_passage"]))
    unsupported_numbers = sorted(number for number in passage_numbers if normalize_evidence(number) not in source_corpus)
    if unsupported_numbers:
        raise ValueError(f"Passage contains numbers absent from sources: {unsupported_numbers}")


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


def generate_with_retries(messages: list[dict[str, str]], sources: list[Story], attempts: int = 3) -> dict[str, Any]:
    errors: list[str] = []
    current_messages = list(messages)
    for attempt in range(1, attempts + 1):
        try:
            payload = call_deepseek(current_messages)
            validate_payload(payload, sources)
            audit = audit_facts(payload, sources)
            if audit["supported"]:
                return payload
            issues = [str(issue) for issue in audit["issues"][:5]]
            message = "Fact checker suggestions: " + "; ".join(issues)
            errors.append(f"attempt {attempt}: {message}")
            eprint(f"Generation needs revision ({attempt}/{attempts}): {message}")
            if attempt == attempts:
                break
            current_messages += [
                {"role": "assistant", "content": json.dumps(payload, ensure_ascii=False)},
                {"role": "user", "content": (
                    "Revise the previous JSON. Correct only the unsupported or overconfident statements "
                    "identified by the fact checker below, using the supplied sources. Keep accurate material, "
                    "preserve the complete JSON schema, and return JSON only. Re-check every reading question, "
                    "all four options, each question's answer, and answer_key against the revised passage. "
                    "Answers are dynamic for each article and must never be copied from a fixed template.\n\n"
                    + "\n".join(issues)
                )},
            ]
            continue
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

    messages = build_prompt(topic, selected)
    payload = generate_with_retries(messages, selected)

    today = dt.date.today().isoformat()
    json_path = output_dir / f"{today}.json"
    md_path = output_dir / f"{today}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(payload, topic, selected), encoding="utf-8")
    eprint(f"Wrote {json_path}")
    eprint(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
