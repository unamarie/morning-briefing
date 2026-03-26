#!/usr/bin/env python3
"""
Morning briefing: RSS → Claude API → HTML Dashboard
Fetches articles from configured RSS feeds, summarizes them with Claude,
and generates a static HTML dashboard.
"""

import os
import json
import time
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import anthropic

# CONFIGURATION

FEEDS = {
    # Microsoft Fabric and Power Platform
    "Microsoft Fabric": [
        "https://blog.fabric.microsoft.com/en-us/blog/feed",
        "https://devblogs.microsoft.com/powerbi/feed/",
        "https://rss.app/feeds/cF6hSzjKQvaJcQVf.xml",
    ],

    # Data Engineering
    "Data Engineering": [
        "https://www.getdbt.com/blog/rss.xml",
        "https://medium.com/feed/snowflake",
        "https://www.databricks.com/feed",
        "https://cloud.google.com/feeds/bigquery-release-notes.xml",
        "https://www.apacheairflow.com/blog/rss.xml",  # Airflow / orchestration
        "https://dagster.io/blog/rss.xml",
        "https://delta.io/feed.xml",                    # Delta Lake
    ],

    # AI, LLMs and Agents
    "AI and Agents": [
        "https://openai.com/blog/rss.xml",
        "https://www.anthropic.com/rss.xml",
        "https://blog.google/technology/ai/rss/",
        "https://huggingface.co/blog/feed.xml",
        "https://www.langchain.com/blog/rss.xml",
        "https://lilianweng.github.io/index.xml",       # Lilian Weng (OpenAI)
        "https://simonwillison.net/atom/everything/",    # Simon Willison — LLM tooling
        "https://buttondown.com/ainews/rss",             # AI News newsletter
    ],

    # Automation and Orchestration
    "Automation and Orchestration": [
        "https://blog.n8n.io/rss/",
        "https://zapier.com/blog/feeds/latest/",
        "https://www.make.com/en/blog/feed",
        "https://temporal.io/blog/feed",                 # Workflow orchestration
        "https://prefect.io/blog/rss.xml",
    ],

    # Cloud and Infrastructure
    "Cloud and Infrastructure": [
        "https://aws.amazon.com/blogs/aws/feed/",
        "https://azure.microsoft.com/en-us/blog/feed/",
        "https://cloud.google.com/blog/feeds/all.xml",
        "https://www.hashicorp.com/blog/feed.xml",       # Terraform, Vault, etc.
        "https://www.pulumi.com/blog/rss.xml",
    ],

    # System Architecture and DevOps
    "Architecture and DevOps": [
        "https://www.infoq.com/feed/",                   # Deep architecture content
        "https://thenewstack.io/feed/",
        "https://martinfowler.com/feed.atom",
        "https://newsletter.pragmaticengineer.com/feed",
        "https://blog.bytebytego.com/feed",              # System design
    ],

    # General Tech News
    "General Tech News": [
        "https://feeds.arstechnica.com/arstechnica/technology-lab",
        "https://www.theverge.com/rss/index.xml",
        "https://hnrss.org/best?count=15",
        "https://tldr.tech/api/rss/tech",                # TLDR newsletter
    ],

    # GitHub
    "GitHub": [
        "https://github.blog/feed/",
        "https://github.blog/changelog/feed/",
    ],

    # Reddit Communities
    "Reddit": [
        "https://www.reddit.com/r/llmdevs/top/.rss?t=week",
        "https://www.reddit.com/r/AI_Agents/top/.rss?t=week",
        "https://www.reddit.com/r/MicrosoftFabric/top/.rss?t=week",
        "https://www.reddit.com/r/dataengineering/top/.rss?t=week",
        "https://www.reddit.com/r/LocalLLaMA/top/.rss?t=week",
        "https://www.reddit.com/r/selfhosted/top/.rss?t=week",
    ],

    # World News
    "World": [
        "https://theconversation.com/global/feeds",
    ],
}

# How many hours back to look for articles (default: 26h to catch overnight posts)
LOOKBACK_HOURS = int(os.environ.get("LOOKBACK_HOURS", "26"))

# Max articles per category to summarize (keeps cost down)
MAX_ARTICLES_PER_CATEGORY = int(os.environ.get("MAX_ARTICLES", "8"))

# Claude model to use for summaries
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514")

# Output path
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "public"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger(__name__)


# RSS FETCHING

def fetch_articles(feeds: dict, lookback_hours: int) -> dict:
    """Fetch recent articles from all RSS feeds, grouped by category."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    results = {}

    for category, urls in feeds.items():
        articles = []
        for url in urls:
            try:
                log.info(f"  Fetching {url}")
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    # Parse published date
                    published = None
                    for date_field in ("published_parsed", "updated_parsed"):
                        t = getattr(entry, date_field, None)
                        if t:
                            published = datetime(*t[:6], tzinfo=timezone.utc)
                            break

                    # If no date found, include it (better to over-include)
                    if published and published < cutoff:
                        continue

                    # Extract clean text summary or description
                    summary_text = ""
                    if hasattr(entry, "summary"):
                        summary_text = entry.summary[:1500]
                    elif hasattr(entry, "description"):
                        summary_text = entry.description[:1500]

                    articles.append({
                        "title": entry.get("title", "Untitled"),
                        "link": entry.get("link", ""),
                        "published": published.isoformat() if published else "",
                        "source": feed.feed.get("title", url),
                        "summary_raw": summary_text,
                    })
            except Exception as e:
                log.warning(f"  Failed to fetch {url}: {e}")

        # Deduplicate by title similarity and limit
        seen = set()
        unique = []
        for a in articles:
            key = hashlib.md5(a["title"].lower().encode()).hexdigest()[:10]
            if key not in seen:
                seen.add(key)
                unique.append(a)
        results[category] = unique[:MAX_ARTICLES_PER_CATEGORY]

    return results


# CLAUDE SUMMARIZATION

def summarize_category(client: anthropic.Anthropic, category: str, articles: list) -> dict:
    """Send a batch of articles to Claude and get back structured summaries."""
    if not articles:
        return {"category": category, "summary": "No new articles found.", "articles": []}

    articles_text = ""
    for i, a in enumerate(articles, 1):
        articles_text += f"\n--- Article {i} ---\n"
        articles_text += f"Title: {a['title']}\n"
        articles_text += f"Source: {a['source']}\n"
        articles_text += f"Link: {a['link']}\n"
        articles_text += f"Content: {a['summary_raw']}\n"

    prompt = f"""You are a morning news briefing assistant. Summarize the following {category} articles for a data engineer / analytics professional.

Return your response as JSON (no markdown fences) with this structure:
{{
  "category_summary": "2-3 sentence overview of the most important themes/trends across these articles",
  "articles": [
    {{
      "title": "article title",
      "link": "article url",
      "source": "source name",
      "summary": "1-2 sentence summary of why this matters",
      "relevance": "high" | "medium" | "low"
    }}
  ]
}}

Sort articles by relevance (high first). Be concise and opinionated — highlight what actually matters for someone working in data.

Articles:
{articles_text}"""

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        return {"category": category, **json.loads(text)}
    except Exception as e:
        log.error(f"  Summarization failed for {category}: {e}")
        return {
            "category": category,
            "category_summary": "Summarization failed — see raw articles below.",
            "articles": [
                {"title": a["title"], "link": a["link"], "source": a["source"],
                 "summary": a["summary_raw"][:200], "relevance": "medium"}
                for a in articles
            ],
        }


# HTML DASHBOARD GENERATION

def generate_html(summaries: list[dict], generated_at: str) -> str:
    """Produce a self-contained HTML dashboard."""

    category_blocks = ""
    for s in summaries:
        article_cards = ""
        for a in s.get("articles", []):
            relevance = a.get("relevance", "medium")
            badge_color = {
                "high": "#e74c3c", "medium": "#f39c12", "low": "#7f8c8d"
            }.get(relevance, "#7f8c8d")

            article_cards += f"""
            <a href="{a.get('link', '#')}" target="_blank" class="article-card">
              <div class="card-header">
                <span class="badge" style="background:{badge_color}">{relevance}</span>
                <span class="source">{a.get('source', '')}</span>
              </div>
              <h3>{a.get('title', 'Untitled')}</h3>
              <p>{a.get('summary', '')}</p>
            </a>"""

        category_blocks += f"""
        <section class="category">
          <h2>{s['category']}</h2>
          <p class="category-summary">{s.get('category_summary', '')}</p>
          <div class="card-grid">
            {article_cards}
          </div>
        </section>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Morning briefing {generated_at}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,700&family=Source+Sans+3:wght@400;600&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #0f1117;
    --surface: #181b24;
    --surface-hover: #1f2330;
    --border: #2a2e3a;
    --text: #e1e4ed;
    --text-muted: #8b90a0;
    --accent: #f0c040;
    --accent-dim: rgba(240, 192, 64, 0.12);
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'Source Sans 3', system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    min-height: 100vh;
  }}
  .container {{ max-width: 1100px; margin: 0 auto; padding: 2rem 1.5rem 4rem; }}

  /* Header */
  header {{
    text-align: center;
    padding: 3rem 0 2.5rem;
    border-bottom: 1px solid var(--border);
    margin-bottom: 2.5rem;
  }}
  header h1 {{
    font-family: 'Fraunces', serif;
    font-size: 2.8rem;
    font-weight: 700;
    letter-spacing: -0.03em;
    background: linear-gradient(135deg, var(--accent), #ff8c42);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }}
  header .dateline {{
    color: var(--text-muted);
    margin-top: 0.5rem;
    font-size: 0.95rem;
  }}

  /* Category sections */
  .category {{
    margin-bottom: 3rem;
  }}
  .category h2 {{
    font-family: 'Fraunces', serif;
    font-size: 1.5rem;
    color: var(--accent);
    margin-bottom: 0.4rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }}
  .category h2::before {{
    content: '◆';
    font-size: 0.6rem;
    opacity: 0.6;
  }}
  .category-summary {{
    color: var(--text-muted);
    margin-bottom: 1.2rem;
    font-size: 0.95rem;
    max-width: 750px;
  }}

  /* Card grid */
  .card-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 1rem;
  }}
  .article-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.2rem 1.3rem;
    text-decoration: none;
    color: inherit;
    transition: background 0.2s, border-color 0.2s, transform 0.15s;
    display: block;
  }}
  .article-card:hover {{
    background: var(--surface-hover);
    border-color: var(--accent);
    transform: translateY(-2px);
  }}
  .card-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.6rem;
  }}
  .badge {{
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 0.15rem 0.5rem;
    border-radius: 4px;
    color: #fff;
  }}
  .source {{
    font-size: 0.78rem;
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 180px;
  }}
  .article-card h3 {{
    font-size: 1rem;
    font-weight: 600;
    line-height: 1.4;
    margin-bottom: 0.4rem;
  }}
  .article-card p {{
    font-size: 0.88rem;
    color: var(--text-muted);
    line-height: 1.5;
  }}

  /* Footer */
  footer {{
    text-align: center;
    color: var(--text-muted);
    font-size: 0.8rem;
    padding-top: 2rem;
    border-top: 1px solid var(--border);
  }}

  @media (max-width: 600px) {{
    header h1 {{ font-size: 2rem; }}
    .container {{ padding: 1rem; }}
    .card-grid {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>
  <div class="container">
    <header>
      <h1>Morning briefing</h1>
      <p class="dateline">Generated {generated_at}</p>
    </header>
    {category_blocks}
    <footer>
      Powered by RSS feeds &amp; Claude API &middot; auto-generated daily
    </footer>
  </div>
</body>
</html>"""


# MAIN

def main():
    log.info("Morning briefing, starting")

    # 1. Fetch RSS
    log.info("Fetching RSS feeds...")
    articles_by_category = fetch_articles(FEEDS, LOOKBACK_HOURS)
    total = sum(len(v) for v in articles_by_category.values())
    log.info(f"Found {total} articles across {len(articles_by_category)} categories")

    # 2. Summarize with Claude
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.error("ANTHROPIC_API_KEY not set!")
        raise SystemExit(1)

    client = anthropic.Anthropic(api_key=api_key)
    summaries = []
    for category, articles in articles_by_category.items():
        log.info(f"Summarizing {category} ({len(articles)} articles)...")
        result = summarize_category(client, category, articles)
        summaries.append(result)
        time.sleep(0.5)  # Be nice to the API

    # 3. Generate HTML
    now = datetime.now(timezone.utc).strftime("%A %B %d, %Y at %H:%M UTC")
    html = generate_html(summaries, now)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "index.html"
    out_path.write_text(html, encoding="utf-8")
    log.info(f"Dashboard written to {out_path}")

    # Also save raw JSON for debugging / downstream use
    json_path = OUTPUT_DIR / "briefing.json"
    json_path.write_text(json.dumps(summaries, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info(f"JSON written to {json_path}")


if __name__ == "__main__":
    main()
