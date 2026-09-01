# CommentOps

**Turn audience noise into a prioritized creator action plan.**

CommentOps is a lightweight creator-operations tool built for the AI Content Engine Hackathon. It scans large comment exports, identifies what actually needs attention, groups recurring audience needs, ranks them by demand, and turns the highest-value groups into ChatGPT-ready action plans.

## Why it exists

Creators often handle comments one-by-one even when dozens of people are asking the same underlying question. CommentOps changes the unit of work from **individual comments** to **recurring audience needs**.

In the included synthetic demo:

- 120 comments are scanned
- 80 require attention
- 8 recurring audience needs are identified
- the dashboard estimates ~180 minutes of repetitive reply work avoided

The time-saved number is an **estimate**, not a measured benchmark. The default assumption is 2.5 minutes per manual reply and is adjustable in the UI.

## Core workflow

1. Upload a CSV of comments.
2. CommentOps classifies comments into actionable, low-priority, and spam.
3. A conservative local clustering stage groups recurring audience needs.
4. Demand Score combines repetition, engagement, and urgency.
5. The highest-value groups are converted into a structured prompt for ChatGPT.
6. ChatGPT returns JSON containing:
   - audience-need summary
   - intent
   - recommended creator action
   - draft reply
   - pinned comment
   - content opportunity
   - suggested title
   - hook
7. The JSON is imported back into CommentOps.

## Zero-API design

CommentOps deliberately supports a **zero-API ChatGPT bridge**.

The local application does not require an OpenAI API key and does not make paid model API calls. Instead, it produces a structured prompt that can be copied into ChatGPT manually and accepts the structured JSON response back into the app.

This keeps the demo usable without secrets, billing configuration, or external API availability.

## Architecture

```text
CSV comments
    |
    v
Local triage
    |
    v
Recurring-anchor clustering
    |
    v
Demand scoring
    |
    +----------------------+
    |                      |
    v                      v
Creator Command Center   ChatGPT bridge
                           |
                           v
                    Structured JSON
                           |
                           v
                    Action plans
```

### Local components

- **Streamlit** — UI and Creator Command Center
- **pandas** — CSV ingestion and data transformation
- **scikit-learn** — retained as a project dependency for experimentation
- **Python heuristics** — triage and conservative recurring-topic grouping
- **ChatGPT bridge** — optional manual AI reasoning layer with no API key

## Demand Score

The score is intentionally transparent:

- recurrence: up to 45 points
- combined engagement: up to 25 points
- urgency: up to 30 points

It is a prioritization heuristic, not a prediction of future performance.

## Demo data

`data/demo_comments_120.csv` is **synthetic demo data** created specifically to exercise the product. It is not scraped customer data and must not be presented as real creator analytics.

It contains recurring examples around:

- Windows installation
- macOS installation
- Docker memory usage
- export crashes
- login/password reset problems
- deployment
- database explanations
- testing

plus positive comments and spam.

## Run locally

Requires Python 3.11+.

```bash
python -m venv .venv
```

Windows:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run tests:

```bash
python -m pytest
```

Start CommentOps:

```bash
python -m streamlit run app.py
```

Then open the local URL shown by Streamlit.

## CSV format

Minimum:

```csv
comment
"How do I install this on Windows?"
```

With engagement:

```csv
comment,likes
"How do I install this on Windows?",42
```

Accepted text-column names:

- `comment`
- `text`
- `content`
- `message`

Accepted engagement-column names include:

- `likes`
- `like_count`
- `votes`

## Privacy

CommentOps processes the CSV locally in the Streamlit runtime. In zero-API mode, no comments are automatically sent to an AI provider. A user explicitly chooses what generated prompt to copy into ChatGPT.

Creators should avoid submitting private or sensitive information to third-party AI services unless they are authorized to do so.

## Hackathon notes

Built for the **AI Content Engine Hackathon**.

The project focuses on repetitive creator operations, particularly comment triage and response planning. The goal is not to auto-post generic AI replies. Instead, CommentOps preserves human review while compressing a large inbox into a much smaller number of evidence-backed decisions.

## Status

Hackathon prototype / MVP.
