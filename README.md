# ☀️ Morning Briefing

A daily AI-powered news dashboard for data professionals. Fetches RSS feeds, summarizes them with Claude, and publishes a static HTML dashboard to GitHub Pages — automatically, every morning.

![Python](https://img.shields.io/badge/python-3.12-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## What you get

A clean, dark-themed dashboard at `https://<your-username>.github.io/morning-briefing/` that refreshes every day with:

- **Microsoft Fabric / Power BI** — official blog + devblog
- **GitHub** — blog + changelog
- **Data Engineering** — dbt, Snowflake, Databricks, BigQuery
- **General Tech** — Ars Technica, The Verge, Hacker News top stories

Each article gets a 1-2 sentence summary and a relevance rating (high / medium / low) tailored for data engineers and analytics professionals.

---

## Quick setup (10 minutes)

### 1. Create the repo

```bash
# Clone or fork this repo
git clone https://github.com/<you>/morning-briefing.git
cd morning-briefing
```

### 2. Add your Anthropic API key

Go to your repo on GitHub:

**Settings → Secrets and variables → Actions → New repository secret**

| Name | Value |
|------|-------|
| `ANTHROPIC_API_KEY` | `sk-ant-...` (your key from console.anthropic.com) |

### 3. Enable GitHub Pages

**Settings → Pages → Source → GitHub Actions**

### 4. Test it

Go to **Actions → Morning Briefing → Run workflow** and click the green button.

After ~2 minutes your dashboard will be live at:
```
https://<your-username>.github.io/morning-briefing/
```

That's it. The workflow runs automatically every morning at 06:00 UTC (07:00 CET / 08:00 CEST).

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

---

## Tips

- **Bookmark the dashboard URL** on your phone/tablet for a morning reading habit
- **Add a .gitignore** with `public/` so generated files aren't committed
- **Want email instead?** Add a step in the workflow that sends the HTML via a service like Resend or SendGrid
- **Want Slack/Teams?** Add a step that posts the `briefing.json` summaries via webhook
- **Multiple dashboards?** Run different configs on different schedules (e.g., weekly deep-dive on Fridays)
