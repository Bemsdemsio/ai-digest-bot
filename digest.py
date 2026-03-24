#!/usr/bin/env python3
"""
AI Tools Weekly Digest Bot
Збирає нові AI-інструменти з кількох джерел, генерує AI-резюме через Claude
і публікує дайджест у Telegram-канал.

Джерела: Product Hunt, Hacker News, Reddit, RSS-стрічки
"""

import os
import json
import time
import hashlib
import logging
import datetime
import requests
import feedparser
from pathlib import Path
from dataclasses import dataclass, field

# ─── Налаштування ─────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN  = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHANNEL_ID = os.environ["TELEGRAM_CHANNEL_ID"]
ANTHROPIC_API_KEY   = os.environ["ANTHROPIC_API_KEY"]

DAYS_BACK     = int(os.getenv("DAYS_BACK", "7"))
MAX_TOOLS     = int(os.getenv("MAX_TOOLS", "15"))
SEEN_IDS_FILE = Path("seen_ids.json")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


# ─── Структура даних ──────────────────────────────────────────────────────────

@dataclass
class AITool:
    title:       str
    url:         str
    description: str
    source:      str
    score:       int  = 0
    tags:        list = field(default_factory=list)
    ai_summary:  str  = ""

    @property
    def uid(self) -> str:
        return hashlib.md5(self.url.encode()).hexdigest()[:12]


# ─── Утиліти ──────────────────────────────────────────────────────────────────

def load_seen_ids() -> set:
    if SEEN_IDS_FILE.exists():
        return set(json.loads(SEEN_IDS_FILE.read_text()))
    return set()

def save_seen_ids(ids: set):
    SEEN_IDS_FILE.write_text(json.dumps(list(ids), ensure_ascii=False))

def cutoff_dt() -> datetime.datetime:
    return datetime.datetime.utcnow() - datetime.timedelta(days=DAYS_BACK)

AI_KEYWORDS = [
    "ai ", " ai,", " ai.", "llm", "gpt", "claude", "gemini", "copilot",
    "machine learning", "neural", "generative", "diffusion", "chatbot",
    "assistant", "openai", "anthropic", "hugging face", "transformer",
    "inference", "embedding", "vector", "rag ", "agent", "multimodal",
    "text-to-", "image generation", "voice ai", "code generation",
    "artificial intelligence", "stable diffusion", "midjourney",
]

def is_ai_related(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in AI_KEYWORDS)


# ─── Парсери джерел ───────────────────────────────────────────────────────────

def fetch_product_hunt() -> list:
    log.info("Downloading Product Hunt...")
    tools, since = [], cutoff_dt()
    feed = feedparser.parse(
        "https://www.producthunt.com/feed?category=artificial-intelligence"
    )
    for e in feed.entries:
        try:
            pub = datetime.datetime(*e.published_parsed[:6])
        except Exception:
            continue
        if pub < since:
            continue
        title = e.get("title", "")
        desc  = e.get("summary", "")
        url   = e.get("link", "")
        if not is_ai_related(title + " " + desc):
            continue
        tools.append(AITool(
            title=title, url=url,
            description=desc[:300], source="Product Hunt 🐱",
            tags=["product-hunt"],
        ))
    log.info(f"   Product Hunt: {len(tools)} tools")
    return tools


def fetch_hacker_news() -> list:
    log.info("Downloading Hacker News...")
    tools, seen, since = [], set(), cutoff_dt()
    unix_since = int(since.timestamp())
    queries = ["AI tool", "LLM", "generative AI", "GPT", "Claude API", "open source AI"]

    for q in queries:
        try:
            r = requests.get(
                "https://hn.algolia.com/api/v1/search_by_date",
                params={"query": q, "tags": "story",
                        "numericFilters": f"created_at_i>{unix_since}",
                        "hitsPerPage": 30},
                timeout=15,
            )
            r.raise_for_status()
            for hit in r.json().get("hits", []):
                oid   = hit.get("objectID")
                score = hit.get("points") or 0
                title = hit.get("title", "")
                url   = hit.get("url") or f"https://news.ycombinator.com/item?id={oid}"
                if oid in seen or score < 15 or not is_ai_related(title):
                    continue
                seen.add(oid)
                tools.append(AITool(
                    title=title, url=url,
                    description=f"HN points: {score}",
                    source="Hacker News 🔶", score=score,
                    tags=["hacker-news"],
                ))
        except Exception as e:
            log.error(f"HN error ({q}): {e}")
        time.sleep(0.4)

    tools.sort(key=lambda t: t.score, reverse=True)
    result = tools[:15]
    log.info(f"   Hacker News: {len(result)} tools")
    return result


def fetch_reddit() -> list:
    log.info("Downloading Reddit...")
    tools, since = [], cutoff_dt()
    subreddits = ["artificial", "MachineLearning", "ChatGPT", "LocalLLaMA"]
    headers = {"User-Agent": "AI-Digest-Bot/2.0"}

    for sub in subreddits:
        try:
            r = requests.get(
                f"https://www.reddit.com/r/{sub}/new.json",
                params={"limit": 50}, headers=headers, timeout=15,
            )
            r.raise_for_status()
            for post in r.json()["data"]["children"]:
                d = post["data"]
                created = datetime.datetime.utcfromtimestamp(d["created_utc"])
                if created < since:
                    continue
                title    = d.get("title", "")
                url      = d.get("url", "")
                score    = d.get("score", 0)
                selftext = d.get("selftext", "")[:250]
                if score < 25 or not is_ai_related(title + " " + selftext):
                    continue
                if not url.startswith("http"):
                    url = "https://reddit.com" + d.get("permalink", "")
                tools.append(AITool(
                    title=title, url=url,
                    description=selftext or f"r/{sub} · {score} upvotes",
                    source=f"Reddit r/{sub} 👾", score=score,
                    tags=["reddit", sub],
                ))
            time.sleep(1)
        except Exception as e:
            log.error(f"Reddit r/{sub}: {e}")

    tools.sort(key=lambda t: t.score, reverse=True)
    result = tools[:15]
    log.info(f"   Reddit: {len(result)} tools")
    return result


def fetch_rss() -> list:
    log.info("Downloading RSS feeds...")
    feeds = [
        ("TechCrunch AI",  "https://techcrunch.com/category/artificial-intelligence/feed/"),
        ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/"),
        ("The Verge AI",   "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
        ("Wired AI",       "https://www.wired.com/feed/tag/ai/latest/rss"),
    ]
    tools, since = [], cutoff_dt()

    for name, url in feeds:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries:
                try:
                    pub = datetime.datetime(*e.published_parsed[:6])
                except Exception:
                    continue
                if pub < since:
                    continue
                title = e.get("title", "")
                desc  = e.get("summary", "")[:300]
                link  = e.get("link", "")
                if not is_ai_related(title + " " + desc):
                    continue
                tools.append(AITool(
                    title=title, url=link,
                    description=desc, source=f"{name} 📰",
                    tags=["rss"],
                ))
        except Exception as e:
            log.error(f"RSS {name}: {e}")

    log.info(f"   RSS: {len(tools)} tools")
    return tools


# ─── Claude: генерація AI-резюме ─────────────────────────────────────────────

def generate_ai_summaries(tools: list) -> list:
    """
    Один запит до Claude Haiku — отримуємо JSON-масив коротких резюме
    для всіх інструментів одночасно.
    """
    log.info(f"Generating AI summaries for {len(tools)} tools...")

    items_json = json.dumps([
        {"id": i, "title": t.title, "description": t.description[:200]}
        for i, t in enumerate(tools)
    ], ensure_ascii=False)

    prompt = (
        "Ти — редактор AI-дайджесту для україномовного Telegram-каналу.\n\n"
        f"Ось список AI-інструментів або AI-новин тижня:\n{items_json}\n\n"
        "Для кожного елементу напиши коротке резюме УКРАЇНСЬКОЮ — 1–2 речення, "
        "максимум 120 символів. Поясни: що це, для кого, яка головна фіча або новина. "
        "Не починай з 'Це', не використовуй 'революційний' або 'потужний'.\n\n"
        "Відповідай ТІЛЬКИ валідним JSON-масивом:\n"
        '[{"id": 0, "summary": "..."}, {"id": 1, "summary": "..."}]\n'
        "Без жодного тексту поза JSON."
    )

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 2048,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
        r.raise_for_status()
        raw = r.json()["content"][0]["text"].strip()

        # Прибираємо можливі ```json ``` огорожі
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        summaries = {item["id"]: item["summary"] for item in json.loads(raw)}
        for i, tool in enumerate(tools):
            tool.ai_summary = summaries.get(i, "")
        log.info("AI summaries done")

    except Exception as e:
        log.error(f"Claude error: {e} — continuing without summaries")

    return tools


# ─── Форматування Telegram-повідомлення ──────────────────────────────────────

def escape_md(text: str) -> str:
    for ch in ["\\", "*", "[", "]", "_"]:
        text = text.replace(ch, "\\" + ch)
    return text

def format_digest(tools: list) -> str:
    now        = datetime.datetime.utcnow()
    week_start = (now - datetime.timedelta(days=DAYS_BACK)).strftime("%d.%m")
    week_end   = now.strftime("%d.%m.%Y")

    lines = [
        f"🤖 *AI\\-інструменти тижня* | {week_start}–{week_end}",
        f"Відібрано: *{len(tools)}* нових інструментів\n",
        "━━━━━━━━━━━━━━━━━━━━",
    ]

    for i, t in enumerate(tools, 1):
        title   = escape_md(t.title)
        summary = (t.ai_summary or t.description[:100]).replace("*", "").replace("_", "").strip()
        lines.append(f"*{i}\\. {title}*")
        lines.append(f"_{summary}_")
        lines.append(f"{t.source} → [посилання]({t.url})\n")

    lines += [
        "━━━━━━━━━━━━━━━━━━━━",
        "_Підписуйтесь, щоб не пропустити наступний дайджест_ 👆",
    ]

    return "\n".join(lines)


def send_to_telegram(text: str):
    url    = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    chunks = [text[i:i + 4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        r = requests.post(url, json={
            "chat_id":                  TELEGRAM_CHANNEL_ID,
            "text":                     chunk,
            "parse_mode":               "Markdown",
            "disable_web_page_preview": True,
        }, timeout=15)
        r.raise_for_status()
        log.info("Telegram chunk sent")
        time.sleep(0.5)


# ─── Головна логіка ───────────────────────────────────────────────────────────

def run():
    log.info("AI Digest Bot — start")
    seen_ids = load_seen_ids()

    # 1. Збираємо
    raw: list = (
        fetch_product_hunt()
        + fetch_hacker_news()
        + fetch_reddit()
        + fetch_rss()
    )

    # 2. Дедублікація
    seen_urls, unique = set(), []
    for t in raw:
        if t.uid not in seen_ids and t.url not in seen_urls:
            seen_urls.add(t.url)
            unique.append(t)

    log.info(f"Unique new tools: {len(unique)}")
    if not unique:
        log.info("Nothing new — skipping")
        return

    # 3. Пріоритизація: Product Hunt → score → решта
    unique.sort(key=lambda t: (0 if "product-hunt" in t.tags else 1, -t.score))
    final = unique[:MAX_TOOLS]

    # 4. AI-резюме
    final = generate_ai_summaries(final)

    # 5. Публікація
    message = format_digest(final)
    log.info(f"Message length: {len(message)} chars")
    send_to_telegram(message)

    # 6. Кешуємо ID
    save_seen_ids(seen_ids | {t.uid for t in final})
    log.info(f"Done! Published {len(final)} tools")


if __name__ == "__main__":
    run()
