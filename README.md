# ☀️ Morning briefing

A daily AI-powered news dashboard for data professionals. Fetches RSS feeds, summarizes them with Claude, and publishes a static HTML dashboard to GitHub Pages.

![Python](https://img.shields.io/badge/python-3.12-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## What

A clean, dark-themed dashboard at `https://unamariei.github.io/morning-briefing/` that refreshes every day with:

- **Microsoft Fabric/Power BI**: official blog + devblog
- **GitHub**: blog + changelog
- **Data Engineering**: dbt, Snowflake, Databricks, BigQuery
- **General Tech**: Ars Technica, The Verge, Hacker News top stories

Each article gets a 1-2 sentence summary and a relevance rating (high/medium/low) tailored for data engineers and analytics professionals.

---

## Customization

### Change the schedule

Edit `.github/workflows/daily-news.yml`, line 7:

```yaml
- cron: "0 6 * * *"   # 06:00 UTC daily
```

Use [crontab.guru](https://crontab.guru/) to pick your preferred time.

### Add or remove RSS feeds

Edit the `FEEDS` dict in `news_bot.py`:

```python
FEEDS = {
    "My New Category": [
        "https://example.com/feed.xml",
        "https://another-source.com/rss",
    ],
    # Remove categories by deleting them
}
```

### Tune article volume

Environment variables (set in the workflow or locally):

| Variable | Default | Description |
|----------|---------|-------------|
| `LOOKBACK_HOURS` | `26` | How far back to look for articles |
| `MAX_ARTICLES` | `8` | Max articles per category to summarize |
| `CLAUDE_MODEL` | `claude-sonnet-4-20250514` | Model to use (sonnet is fast + cheap) |
| `OUTPUT_DIR` | `public` | Where to write the HTML |

---

## Run locally

```bash
# Install deps
pip install -r requirements.txt

# Set your API key
export ANTHROPIC_API_KEY="sk-ant-..."

# Generate the dashboard
python news_bot.py

# Open it
open public/index.html    # macOS
xdg-open public/index.html  # Linux
```

---

## Cost estimate

With default settings (~30 articles/day, using Claude Sonnet):
- ~4 API calls/day × ~2K input tokens × ~500 output tokens
- **≈ $0.02–0.05/day** → roughly **$1–1.50/month**

---

## Project structure

```
morning-briefing/
├── news_bot.py                  # Main script: fetch → summarize → HTML
├── requirements.txt             # Python dependencies
├── .github/workflows/
│   └── daily-news.yml           # GitHub Actions: schedule + deploy
└── public/                      # Generated output (git-ignored)
    ├── index.html               # The dashboard
    └── briefing.json            # Raw summary data
```
