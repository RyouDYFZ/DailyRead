#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import markdown


BASE_DIR = Path(__file__).resolve().parents[1]
SITE_DIR = BASE_DIR / "site"
PUBLIC_DIR = BASE_DIR / "public"


def discover_articles() -> list[Path]:
    paths = list((BASE_DIR / "outputs" / "generated").glob("*.md"))
    paths.extend(BASE_DIR.glob("DailyRead *.md"))
    return sorted(set(paths))


def extract_date(text: str, path: Path) -> str:
    match = re.search(r"\u65e5\u671f\uff1a\s*`(\d{4}-\d{2}-\d{2})`", text)
    if not match:
        match = re.search(r"(\d{4}-\d{2}-\d{2})", path.name)
    if not match:
        raise ValueError(f"Cannot find article date in {path}")
    return match.group(1)


def extract_quiz(section: str, answer_key: str) -> list[dict[str, object]]:
    pattern = re.compile(
        r"(?ms)^\s*(\d+)\.\s+\*\*(.+?)\*\*\s*\n\s*"
        r"A\.\s+(.+?)\s*\n\s*B\.\s+(.+?)\s*\n\s*"
        r"C\.\s+(.+?)\s*\n\s*D\.\s+(.+?)(?=\n\s*(?:------|\d+\.\s+\*\*|\uff08\u7b54\u6848\uff1a))"
    )
    questions: list[dict[str, object]] = []
    for index, match in enumerate(pattern.finditer(section)):
        if index >= len(answer_key):
            break
        questions.append({
            "number": int(match.group(1)),
            "question": match.group(2).strip(),
            "options": {
                "A": match.group(3).strip(),
                "B": match.group(4).strip(),
                "C": match.group(5).strip(),
                "D": match.group(6).strip(),
            },
            "answer": answer_key[index],
        })
    if len(questions) != len(answer_key):
        raise ValueError(f"Expected {len(answer_key)} quiz questions, found {len(questions)}")
    return questions


def parse_article(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    title_match = re.search(r"(?m)^#\s+(.+?)\s*$", text)
    if not title_match:
        raise ValueError(f"Cannot find title in {path}")
    date = extract_date(text, path)
    quiz_heading = text.find("## \u9605\u8bfb\u7406\u89e3")
    sources_heading = text.find("## \u6570\u636e\u6e90")
    if quiz_heading < 0 or sources_heading < 0 or sources_heading <= quiz_heading:
        raise ValueError(f"Missing quiz or sources section in {path}")
    answer_match = re.search(r"\uff08\u7b54\u6848\uff1a([A-D]{5,12})\uff09", text[quiz_heading:sources_heading])
    if not answer_match:
        raise ValueError(f"Cannot find a 5-12 letter answer key in {path}")
    quiz = extract_quiz(text[quiz_heading:sources_heading], answer_match.group(1))
    md = markdown.Markdown(extensions=["extra", "sane_lists"])
    content_html = md.convert(text[:quiz_heading].strip())
    md.reset()
    sources_html = md.convert(text[sources_heading:].strip())
    return {
        "date": date,
        "title": title_match.group(1).strip(),
        "content_html": content_html,
        "sources_html": sources_html,
        "quiz": quiz,
    }


def main() -> None:
    if PUBLIC_DIR.exists():
        shutil.rmtree(PUBLIC_DIR)
    shutil.copytree(SITE_DIR, PUBLIC_DIR)
    articles_dir = PUBLIC_DIR / "articles"
    articles_dir.mkdir(parents=True, exist_ok=True)

    articles: dict[str, dict[str, object]] = {}
    for path in discover_articles():
        article = parse_article(path)
        articles[str(article["date"])] = article
    if not articles:
        raise SystemExit("No DailyRead Markdown articles were found.")

    manifest = []
    for date in sorted(articles, reverse=True):
        article = articles[date]
        output = articles_dir / f"{date}.json"
        output.write_text(json.dumps(article, ensure_ascii=False), encoding="utf-8")
        manifest.append({"date": date, "title": article["title"], "file": f"articles/{date}.json"})
    (PUBLIC_DIR / "articles.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (PUBLIC_DIR / ".nojekyll").write_text("", encoding="utf-8")
    print(f"Built {len(manifest)} article(s) in {PUBLIC_DIR}")


if __name__ == "__main__":
    main()
