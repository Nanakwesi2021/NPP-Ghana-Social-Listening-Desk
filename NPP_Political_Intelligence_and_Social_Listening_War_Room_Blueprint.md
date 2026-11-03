# NPP Social Media Monitoring & Strategic Response System (War Room Blueprint)

A complete architectural, operational, and technical blueprint designed for the New Patriotic Party (NPP) social media and communications machinery in Ghana. This system captures real-time trending issues, flags opposition attack narratives, monitors Ghanaian digital platforms, and automates alert dispatches to party communicators.

---

## 1. System Architecture & Information Flow

```
[ Data Ingestion Sources ]
 ├── X (Twitter) API v2 (Keywords, Trends, Hashtags)
 ├── Mainstream Online Portals (Citi, Joy, Graphic, Peace FM via RSS)
 ├── Meta Graph API (Facebook Public Pages & Groups)
 ├── TikTok API / Scrapers (Viral Skits & Sounds)
 └── Grassroots WhatsApp Bot (Forwarded Audios & Videos)
               │
               ▼
[ NLP & Threat Scoring Engine ]
 ├── Ghanaian Political Lexicon (Twi, Pidgin, Nicknames)
 ├── Narrative Clustering (Cedi, Dumsor, Galamsey, Corruption)
 └── Threat Level Classification (Level 1 to Level 4)
               │
               ▼
[ Storage & Distribution Gateway ]
 ├── SQLite / Redis (Deduplication & Cache)
 ├── Telegram War Room Bot (Instant Alert Dispatch)
 └── Strategic Research Desk (Factsheets & Rebuttal Generation)
```

---

## 2. Ghanaian Political Threat Classification Matrix

| Level | Classification | Trigger Criteria | Action Protocol |
| :--- | :--- | :--- | :--- |
| **Level 1** | Routine Monitoring | General party mentions, non-escalating political banter, low engagement (<100 interactions). | Logged automatically for weekly trend reports and sentiment baseline. |
| **Level 2** | Emerging Narrative | Critical policy mention gaining velocity (e.g., utility tariffs, fuel adjustment) crossing 200+ mentions/hr. | Dispatched to regional comms leads; monitoring increased to 5-minute intervals. |
| **Level 3** | High-Risk Narrative / Disinformation | Coordinated astroturfing, spliced audio/video of party leadership, unverified corruption claims, or opposition press briefings gaining rapid traction. | Instant Telegram dispatch to War Room; research team issues fact-checked talking points within 30 minutes. |
| **Level 4** | Code Red / Crisis | Trending nationwide #1, major breaking crisis, national security issues, or internal leadership controversy. | Immediate escalation to the National Communications Director and Party Leadership with a full mitigation dossier. |

---

## 3. Platform Breakdown in the Ghanaian Context

* **X (Twitter):** Agenda-setter for journalists, civil society organizations (IMANI, CDD, IES), and youth influencers. Highest priority for breaking policy debates.
* **TikTok:** Center for emotional engagement, memes, satirical skits, cost-of-living rants, and protest footage. The primary battleground for first-time and youth voters.
* **Facebook:** Deep grassroots saturation across all 16 regions and rural constituencies. Essential for monitoring local community pages and morning show live comments.
* **Radio & YouTube:** Morning political shows (*Peace FM Kokrokoo*, *Joy Super Morning Show*, *Citi Breakfast Show*, *Good Evening Ghana*) set the daily narrative. The system monitors portal summaries and transcripts of these broadcasts.

---

## 4. Master Boolean Search Taxonomies

### A. NPP Leadership & Brand Tracking
```boolean
("NPP" OR "New Patriotic Party" OR "Kukrudu" OR "Elephant Party" OR "Bawumia" OR "Mahamudu Bawumia" OR "Akufo-Addo" OR "Nana Addo" OR "NAPO" OR "Matthew Opoku Prempeh" OR "Justin Kodua" OR "Stephen Ntim")
AND NOT ("National Petroleum Provider" OR "Net Primary Product" OR "Non-Practicing")
```

### B. Opposition Attack Handles & Nicknames
```boolean
("Addo D" OR "Nana Showboy" OR "Clearing Agent" OR "Digital Bawumia" OR "Dr. Digital" OR "Economic Prophet" OR "Bawuliar" OR "King Promise" OR "Otumfuo nephew")
```

### C. Issue-Specific Attack Vectors
```boolean
// 1. Dumsor & Energy
("dumsor" OR "dum sor" OR "power outage" OR "light out" OR "GRIDCo" OR "ECG" OR "VRA" OR "power crisis" OR "no light" OR "lights out" OR "tariffs" OR "PURC")
AND ("NPP" OR "Bawumia" OR "Ministry of Energy" OR "government" OR "Ghana" OR "Accra" OR "Kumasi")

// 2. Economy & Currency
("NPP" OR "government" OR "Bawumia" OR "Finance Ministry" OR "Bank of Ghana" OR "BoG")
AND ("cedi depreciation" OR "dollar rate" OR "inflation" OR "GRA" OR "taxes" OR "fuel price" OR "cost of living" OR "haircut" OR "DDEP" OR "debt restructuring" OR "economic hardship" OR "sika mpɛ dede")

// 3. Mining & Galamsey
("galamsey" OR "illegal mining" OR "polluted water" OR "Pra river" OR "Birim river" OR "Ankobra" OR "turbidity" OR "forestry commission" OR "mining lease" OR "red zones" OR "stop galamsey")
AND ("NPP" OR "government" OR "party bigwigs" OR "ministers" OR "police" OR "military" OR "EPA")

// 4. Governance & Procurement Scandals
("NPP" OR "appointees" OR "government" OR "politicians")
AND ("corruption" OR "scandal" OR "procurement" OR "nepotism" OR "family and friends" OR "Agyapa" OR "National Cathedral" OR "PPA" OR "Special Prosecutor" OR "CHRAJ" OR "ORCA" OR "embezzlement" OR "kickback" OR "bribe")
```

### D. Akan / Pidgin Discontent Lexicon
```boolean
("wahala" OR "chale" OR "e go over you" OR "the country hard" OR "we dey suffer" OR "hunger dey" OR "system no dey work" OR "ground no balance" OR "ɛkɔm de yɛn" OR "abrabo yɛ den" OR "sika nni hɔ" OR "yɛbrɛ" OR "yabrɛ" OR "adwenfi" OR "gyimii" OR "scam" OR "con" OR "4 more to do what" OR "boot for boot")
```

### E. Opposition Watchlist (NDC & CSOs)
```boolean
("NDC" OR "National Democratic Congress" OR "Mahama" OR "John Mahama" OR "Jane Naana" OR "Asiedu Nketiah" OR "General Mosquito" OR "Fifi Kwetey" OR "Sammy Gyamfi" OR "Felix Kwakye")
AND ("press conference" OR "statement" OR "manifesto" OR "scandal" OR "exposed" OR "failure" OR "24-hour economy" OR "resetting Ghana" OR "rescue mission" OR "accountability")
```

---

## 5. Automated Monitoring Engine (Python Implementation)

### Environment Setup
Create a file named `.env`:
```env
X_BEARER_TOKEN="your_x_api_v2_bearer_token"
TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
TELEGRAM_CHAT_ID="your_telegram_channel_or_group_id"
```

Install requirements:
```bash
pip install tweepy feedparser python-dotenv requests
```

### Complete Source Code (`warroom_monitor.py`)

```python
"""
NPP Social Media & News Ingestion Engine
Tracks Ghanaian political discourse across X API and mainstream media RSS feeds.
Categorizes threat levels and dispatches real-time alerts to a Telegram War Room.
"""

import os
import re
import time
from datetime import datetime
from dotenv import load_dotenv
import feedparser
import requests
import tweepy

load_dotenv()

# ==========================================
# CONFIGURATION
# ==========================================
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

RSS_SOURCES = {
    "Citi Newsroom": "https://citinewsroom.com/feed/",
    "Joy Online": "https://www.myjoyonline.com/feed/",
    "Daily Graphic": "https://www.graphic.com.gh/news?format=feed&type=rss",
    "Peace FM Online": "https://peacefmonline.com/pages/rss/rss_politics.xml"
}

THREAT_TAXONOMY = {
    "Dumsor & Utilities": [
        r"\bdumsor\b", r"\blight out\b", r"\bpower outage\b", r"\becg\b", r"\bgridco\b"
    ],
    "Economy & Cost of Living": [
        r"\bcedi\b", r"\bdollar rate\b", r"\binflation\b", r"\bgra\b", r"\bhaircut\b", 
        r"\bddep\b", r"\bcost of living\b", r"\bsika mp[eɛ] dede\b"
    ],
    "Galamsey & Water Bodies": [
        r"\bgalamsey\b", r"\billegal mining\b", r"\briver pra\b", r"\bankobra\b", r"\bbirim\b"
    ],
    "Corruption & Scandals": [
        r"\bcorruption\b", r"\bkickback\b", r"\bcathedral\b", r"\bprocurement\b", r"\bagyapa\b"
    ],
    "Opposition Campaign Narrative": [
        r"\bmahama\b", r"\b24-hour economy\b", r"\bresetting ghana\b", r"\bsammy gyamfi\b", 
        r"\bgeneral mosquito\b", r"\bboot for boot\b"
    ],
    "Grassroots Discontent & Slang": [
        r"\bground no balance\b", r"\by[eɛ]br[eɛ]\b", r"\bwahala\b", r"\bwe dey suffer\b", 
        r"\b4 more to do what\b", r"\bsystem no dey work\b"
    ]
}

# In-memory deduplication set (Replace with Redis or SQLite for persistent production)
PROCESSED_ITEMS = set()

# ==========================================
# ANALYSIS & ALERT DISPATCH
# ==========================================
def evaluate_narrative(text: str) -> dict:
    """Matches text against threat taxonomies and calculates severity."""
    detected = []
    text_clean = text.lower()

    for category, regex_list in THREAT_TAXONOMY.items():
        for pattern in regex_list:
            if re.search(pattern, text_clean):
                detected.append(category)
                break

    severity = 1
    if len(detected) >= 3 or "Corruption & Scandals" in detected or "Dumsor & Utilities" in detected:
        severity = 3
    elif len(detected) >= 1:
        severity = 2

    return {
        "categories": detected,
        "severity": severity,
        "is_alert_worthy": severity >= 2
    }

def dispatch_telegram_alert(source: str, identifier: str, content: str, url: str, categories: list, severity: int):
    """Pushes high-priority alerts to the designated Telegram War Room channel."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    urgency_header = "🔴 LEVEL 3 - PRIORITY THREAT" if severity >= 3 else "🟡 LEVEL 2 - EMERGING ISSUE"
    formatted_msg = (
        f"{urgency_header}\n\n"
        f"**Channel:** {source}\n"
        f"**Identifier / Headline:** {identifier}\n"
        f"**Categories:** {', '.join(categories)}\n\n"
        f"**Excerpt:**\n{content[:260]}...\n\n"
        f"🔗 **URL:** {url}"
    )

    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": formatted_msg,
        "parse_mode": "Markdown"
    }

    try:
        requests.post(api_url, json=payload, timeout=6)
    except Exception as exc:
        print(f"[!] Alert notification delivery failed: {exc}")

# ==========================================
# INGESTION WORKERS
# ==========================================
def monitor_rss_portals():
    """Scrapes latest headlines and summaries from major Ghanaian news outlets."""
    print("[*] Checking Ghanaian online media feeds...")
    for outlet_name, feed_url in RSS_SOURCES.items():
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:5]:
                link = entry.get("link", "")
                if link in PROCESSED_ITEMS:
                    continue

                title = entry.get("title", "")
                summary = entry.get("summary", "")
                full_body = f"{title} - {summary}"

                analysis = evaluate_narrative(full_body)
                PROCESSED_ITEMS.add(link)

                if analysis["is_alert_worthy"]:
                    print(f"  [!] Flagged news from {outlet_name}: {title}")
                    dispatch_telegram_alert(
                        source=f"News Portal ({outlet_name})",
                        identifier=title,
                        content=summary or title,
                        url=link,
                        categories=analysis["categories"],
                        severity=analysis["severity"]
                    )
        except Exception as exc:
            print(f"[!] Feed fetch failed for {outlet_name}: {exc}")

def monitor_x_stream(client: tweepy.Client):
    """Executes search queries on X API v2 targeting current political debates."""
    print("[*] Running X network political scanner...")
    if not client:
        print("  [!] Skipped: Missing X_BEARER_TOKEN.")
        return

    search_query = (
        '(NPP OR Bawumia OR Akufo-Addo OR "dumsor" OR "galamsey" OR "cedi") '
        'lang:en -is:retweet'
    )

    try:
        response = client.search_recent_tweets(
            query=search_query,
            max_results=25,
            tweet_fields=["created_at", "public_metrics", "author_id"],
            expansions=["author_id"]
        )

        if not response.data:
            print("  [-] No matching recent posts found on X.")
            return

        users_by_id = {user.id: user.username for user in response.includes.get("users", [])}

        for tweet in response.data:
            if tweet.id in PROCESSED_ITEMS:
                continue

            username = users_by_id.get(tweet.author_id, "unknown_user")
            metrics = tweet.public_metrics
            total_interactions = metrics["retweet_count"] + metrics["like_count"] + metrics["reply_count"]
            tweet_url = f"https://x.com/{username}/status/{tweet.id}"

            analysis = evaluate_narrative(tweet.text)
            PROCESSED_ITEMS.add(tweet.id)

            # Boost severity if post has significant viral velocity
            if total_interactions > 60:
                analysis["severity"] = min(analysis["severity"] + 1, 4)

            if analysis["is_alert_worthy"]:
                print(f"  [!] Flagged Tweet from @{username} (Severity L{analysis['severity']}, Engagements: {total_interactions})")
                dispatch_telegram_alert(
                    source=f"X Post (@{username})",
                    identifier=f"@{username} ({total_interactions} total engagements)",
                    content=tweet.text,
                    url=tweet_url,
                    categories=analysis["categories"],
                    severity=analysis["severity"]
                )
    except tweepy.TweepyException as exc:
        print(f"[!] X API request error: {exc}")

# ==========================================
# RUNTIME LOOP
# ==========================================
if __name__ == "__main__":
    x_api_client = tweepy.Client(bearer_token=X_BEARER_TOKEN) if X_BEARER_TOKEN else None

    print("=" * 65)
    print("NPP DIGITAL COMMUNICATIONS INTELLIGENCE ENGINE ACTIVATED")
    print(f"System Clock: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)

    monitor_rss_portals()
    monitor_x_stream(x_api_client)

    print("\n[*] Initial ingestion cycle complete.")
```

---

## 6. Daily War Room Operating Cadence

1. **05:45 GMT — Pre-Morning Show Briefing:**
   * Automated overnight report compiled.
   * Key talking points, macroeconomic data, and rebuttal factsheets delivered to party panelists appearing on *Kokrokoo*, *Joy Super Morning Show*, *Citi Breakfast Show*, and *Good Evening Ghana*.
2. **09:00 to 14:00 GMT — Active Interception Window:**
   * Monitor real-time audience reactions, viral quotes, and audio snippets pulled from radio broadcasts.
   * Deploy infographics and counter-narratives before false narratives solidify.
3. **16:00 to 20:00 GMT — Drive-Time & Evening TV Tracking:**
   * Monitor evening news telecasts (*News360*, *Joy News Prime*) and track youth discourse on TikTok and X spaces.
4. **21:30 GMT — Post-Mortem & Tomorrow's Outlook:**
   * Evaluate which party narratives won engagement metrics.
   * Flag emerging opposition campaigns expected to mature the following morning.