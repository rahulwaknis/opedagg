from collections import defaultdict
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
import re

from flask import Flask, jsonify, request, send_from_directory

from rss_ingest import get_active_sources, get_connection, init_db, fetch_feed, utc_now


app = Flask(__name__)

TOPIC_KEYWORDS = {
    "India Domestic Politics": (
        "india", "indian", "modi", "narendra modi", "amit shah", "rahul gandhi",
        "sonia gandhi", "priyanka gandhi", "mallikarjun kharge", "yogi adityanath",
        "mamata banerjee", "arvind kejriwal", "nitish kumar", "tejashwi yadav",
        "mk stalin", "pinarayi vijayan", "hemant soren", "chandrababu naidu",
        "bjp", "bharatiya janata party", "congress", "inc", "aap", "aam aadmi party",
        "tmc", "trinamool", "dmk", "aiadmk", "jd(u)", "jdu", "rjd", "ncp",
        "shiv sena", "ubt", "bsp", "samajwadi party", "sp", "cpi", "cpim",
        "cpi(m)", "cpim", "rss", "nda", "india bloc", "mahagathbandhan",
        "supreme court of india", "supreme court", "cji", "chief justice of india",
        "high court", "election commission of india", "election commission", "eci",
        "model code of conduct", "evm", "vvpats", "delimitation", "lok sabha",
        "rajya sabha", "vidhan sabha", "assembly election", "state election",
        "panchayat", "municipal election", "police", "ed", "enforcement directorate",
        "cbi", "nia", "income tax department", "uapa", "sedition", "communalism",
        "communal", "secularism", "hindutva", "minority", "reservation", "caste",
        "dalit", "obc", "aadivasi", "tribal", "waqf", "citizenship", "caa", "nrc",
        "federalism", "governor", "chief minister", "cm", "mla", "mp",
        "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh",
        "goa", "gujarat", "haryana", "himachal pradesh", "jharkhand", "karnataka",
        "kerala", "madhya pradesh", "maharashtra", "manipur", "meghalaya", "mizoram",
        "nagaland", "odisha", "punjab", "rajasthan", "sikkim", "tamil nadu",
        "telangana", "tripura", "uttar pradesh", "up", "uttarakhand", "west bengal",
        "andaman and nicobar", "chandigarh", "dadra and nagar haveli", "daman and diu",
        "delhi", "jammu and kashmir", "ladakh", "lakshadweep", "puducherry"
    ),
    "International Politics": (
        "trump", "biden", "starmer", "macron", "le pen", "meloni", "putin",
        "zelensky", "netanyahu", "xi jinping", "erdogan", "merkel", "merz",
        "labour", "conservative", "republican", "democrat", "democrats",
        "republicans", "far right", "leftwing", "rightwing", "populist",
        "national rally", "reform uk", "brexit", "tory", "tories",
        "white house", "congressional", "senate", "house of representatives",
        "downing street", "westminster", "european parliament", "european union",
        "eu", "nato", "united nations", "un", "election", "campaign", "voter",
        "parliament", "coalition", "referendum", "prime minister", "president",
        "democracy", "authoritarian", "junta", "coup", "protest", "sanctions",
        "diplomacy", "geopolitics", "foreign minister", "summit", "bilateral",
        "multilateral", "treaty", "alliance", "trade war", "tariff", "immigration",
        "ukraine", "russia", "china", "taiwan", "israel", "gaza", "iran",
        "palestine", "hamas", "europe", "france", "germany", "britain", "uk",
        "united states", "america", "canada", "australia", "japan", "south korea",
        "north korea", "middle east", "africa", "latin america"
    ),
    "Economy": (
        "economy", "economic", "market", "markets", "finance", "trade",
        "inflation", "growth", "jobs", "business", "bond", "tax", "budget",
        "rupee", "dollar", "bank", "housing", "rent", "cost of living",
        "crisis", "diversification"
    ),
    "India's Foreign Policy": (
        "india and", "india's foreign policy", "indian foreign policy",
        "new delhi", "south block", "external affairs ministry", "mea",
        "s jaishankar", "jaishankar", "narendra modi and", "modi and",
        "india-us", "india us", "india-u.s.", "india u.s.", "india-china",
        "india china", "india-pakistan", "india pakistan", "india-russia",
        "india russia", "india-uk", "india uk", "india-eu", "india eu",
        "india-france", "india france", "india-japan", "india japan",
        "india-south korea", "india south korea", "india-norway", "india norway",
        "india-italy", "india italy", "quad", "brics", "saarc", "g20",
        "non-alignment", "non alignment", "strategic autonomy", "act east",
        "neighbourhood first", "vishwaguru", "global south", "indian ocean",
        "indo-pacific", "line of actual control", "lac", "galwan", "doklam",
        "china", "pakistan", "bangladesh", "sri lanka", "nepal", "bhutan",
        "maldives", "myanmar", "afghanistan", "russia", "ukraine", "israel",
        "gaza", "iran", "u.s.", "us", "united states", "europe", "gulf",
        "foreign policy", "diplomacy", "geopolitics", "border", "defence",
        "defense", "security", "sanctions", "trade pact", "free trade agreement",
        "fta", "bilateral", "multilateral", "summit", "strategic partnership"
    ),
    "Society": (
        "culture", "education", "health", "city", "cities", "identity",
        "social", "school", "university", "religion", "pope", "citizenship",
        "inequality", "smoking", "music", "antisemitism", "food", "recipe",
        "recipes", "cooking", "restaurant", "restaurants", "diet", "nutrition",
        "clothing", "fashion", "apparel", "style", "menswear", "womenswear",
        "real estate", "property", "housing", "homebuyers", "rent", "rental",
        "landlord", "social media", "facebook", "instagram", "tiktok",
        "youtube", "x", "twitter", "hobby", "hobbies", "gardening", "travel",
        "sports", "football", "cricket", "cinema", "film", "television",
        "streaming", "celebrity", "lifestyle", "family", "parenting"
    ),
    "Technology": (
        "ai", "artificial intelligence", "technology", "tech", "digital",
        "platform", "data", "internet", "surveillance", "cyber", "software",
        "mobile phone", "mobile phones", "smartphone", "smartphones", "phone",
        "phones", "handset", "handsets", "5g", "6g", "4g", "lte", "wi-fi",
        "wifi", "bluetooth", "nfc", "satellite internet", "broadband",
        "semiconductor", "semiconductors", "chip", "chips", "chipmaker",
        "chipmakers", "nvidia", "qualcomm", "intel", "amd", "tsmc", "arm",
        "mediatek", "broadcom", "micron", "samsung", "google", "apple",
        "alphabet", "android", "ios", "iphone", "iphones", "pixel",
        "google pixel", "samsung galaxy", "galaxy", "oneplus", "xiaomi",
        "oppo", "vivo", "motorola", "nothing phone", "app store",
        "play store", "search engine", "cloud computing", "data centre",
        "data center", "server", "servers", "gpu", "gpus", "processor",
        "processors", "cpu", "cpus", "app", "apps", "social network",
        "algorithm", "algorithms"
    ),
}


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response


def parse_int(value, default, minimum=1, maximum=100):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def parse_bool(value, default=False):
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "y", "on")


def parse_published(value):
    if not value:
        return None

    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def clean_summary(summary):
    if not summary:
        return None

    text = re.sub(r"<[^>]+>", " ", summary)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return None
    return text[:500]


def keyword_matches(text, keyword):
    escaped = re.escape(keyword)
    return re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text) is not None


def has_any_keyword(text, keywords):
    return any(keyword_matches(text, keyword) for keyword in keywords)


def infer_topic(title, summary, existing_topic=None):
    if existing_topic:
        return existing_topic

    text = f"{title or ''} {summary or ''}".lower()
    scores = {
        topic: sum(1 for keyword in keywords if keyword_matches(text, keyword))
        for topic, keywords in TOPIC_KEYWORDS.items()
    }

    india_markers = (
        "india", "indian", "new delhi", "modi", "narendra modi", "jaishankar",
        "s jaishankar", "mea", "external affairs ministry"
    )
    india_foreign_markers = (
        "foreign policy", "diplomacy", "geopolitics", "border", "defence",
        "defense", "security", "sanctions", "bilateral", "multilateral",
        "summit", "strategic partnership", "trade pact", "free trade agreement",
        "fta", "china", "pakistan", "bangladesh", "sri lanka", "nepal",
        "bhutan", "maldives", "myanmar", "afghanistan", "russia", "ukraine",
        "israel", "gaza", "iran", "u.s.", "us", "united states", "europe",
        "france", "germany", "italy", "sweden", "norway", "uk", "britain",
        "japan", "south korea", "australia", "canada", "gulf", "quad",
        "brics", "saarc", "g20", "indian ocean", "indo-pacific"
    )

    has_india_marker = has_any_keyword(text, india_markers)
    has_india_foreign_marker = has_any_keyword(text, india_foreign_markers)

    if not has_india_marker:
        scores["India's Foreign Policy"] = 0

    india_foreign_score = scores.get("India's Foreign Policy", 0)
    india_domestic_score = scores.get("India Domestic Politics", 0)
    international_score = scores.get("International Politics", 0)

    if india_foreign_score and has_india_marker and has_india_foreign_marker:
        return "India's Foreign Policy"

    if india_domestic_score and india_domestic_score >= international_score - 1:
        return "India Domestic Politics"

    best_topic, best_score = max(scores.items(), key=lambda item: item[1])
    return best_topic if best_score else "Uncategorized"


def row_to_article(row):
    topic = infer_topic(row["title"], row["summary"], row["topic"])
    return {
        "id": row["id"],
        "source": row["source"],
        "title": row["title"],
        "url": row["url"],
        "published": row["published"],
        "author": row["author"],
        "summary": clean_summary(row["summary"]),
        "topic": topic,
        "tags": {
            "access_type": row["access_type"],
            "article_type": row["article_type"],
            "stance": row["stance"],
            "confidence": row["confidence"],
        },
    }


def load_recent_articles(days, max_articles=2000):
    cutoff = datetime.now(UTC) - timedelta(days=days)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            articles.id,
            sources.name AS source,
            articles.title,
            articles.url,
            articles.published,
            articles.author,
            articles.summary,
            topics.name AS topic,
            articles.access_type,
            articles.article_type,
            articles.stance,
            articles.confidence
        FROM articles
        JOIN sources ON sources.id = articles.source_id
        LEFT JOIN topics ON topics.id = articles.topic_id
        ORDER BY articles.id DESC
        LIMIT ?
    """, (max_articles,))
    rows = cursor.fetchall()
    conn.close()

    articles = []
    for row in rows:
        published_at = parse_published(row["published"])
        if published_at and published_at < cutoff:
            continue

        article = row_to_article(row)
        article["_published_at"] = published_at
        articles.append(article)

    return articles


def topic_score(articles):
    now = datetime.now(UTC)
    score = 0.0

    for article in articles:
        published_at = article["_published_at"]
        if published_at is None:
            score += 0.25
            continue

        age_days = max((now - published_at).total_seconds() / 86400, 0)
        score += 1 / (1 + age_days)

    source_count = len({article["source"] for article in articles})
    return round(score * (1 + (source_count - 1) * 0.25), 3)


def public_article(article):
    cleaned = dict(article)
    cleaned.pop("_published_at", None)
    return cleaned


@app.get("/api/health")
def health():
    init_db()
    return jsonify({"status": "ok", "generated_at": utc_now()})


@app.get("/")
def home():
    return send_from_directory("static", "index.html")


@app.get("/<path:path>")
def static_files(path):
    return send_from_directory("static", path)


def build_topics_payload(days, default_limit, default_articles_per_topic):
    limit = parse_int(request.args.get("limit"), default=default_limit, minimum=1, maximum=20)
    articles_per_topic = parse_int(
        request.args.get("articles_per_topic"),
        default=default_articles_per_topic,
        minimum=1,
        maximum=25
    )
    include_uncategorized = parse_bool(request.args.get("include_uncategorized"))

    grouped = defaultdict(list)
    for article in load_recent_articles(days):
        if article["topic"] == "Uncategorized" and not include_uncategorized:
            continue
        grouped[article["topic"]].append(article)

    topics = []
    for topic, articles in grouped.items():
        articles.sort(
            key=lambda item: item["_published_at"] or datetime.min.replace(tzinfo=UTC),
            reverse=True
        )
        topics.append({
            "topic": topic,
            "score": topic_score(articles),
            "article_count": len(articles),
            "source_count": len({article["source"] for article in articles}),
            "latest_published": articles[0]["published"],
            "articles": [
                public_article(article)
                for article in articles[:articles_per_topic]
            ],
        })

    topics.sort(key=lambda item: (item["score"], item["article_count"]), reverse=True)

    return jsonify({
        "generated_at": utc_now(),
        "window_days": days,
        "topics": topics[:limit],
    })


@app.get("/api/current-topics")
def current_topics():
    init_db()
    return build_topics_payload(
        days=5,
        default_limit=8,
        default_articles_per_topic=5
    )


@app.get("/api/topic-history")
def topic_history():
    init_db()
    return build_topics_payload(
        days=30,
        default_limit=20,
        default_articles_per_topic=10
    )


@app.get("/api/hot-topics")
def hot_topics():
    init_db()
    days = parse_int(request.args.get("days"), default=5, minimum=1, maximum=90)
    return build_topics_payload(
        days=days,
        default_limit=8,
        default_articles_per_topic=5
    )


@app.get("/api/articles")
def articles():
    init_db()
    days = parse_int(request.args.get("days"), default=14, minimum=1, maximum=90)
    limit = parse_int(request.args.get("limit"), default=50, minimum=1, maximum=200)
    topic_filter = request.args.get("topic")

    recent_articles = load_recent_articles(days)
    if topic_filter:
        recent_articles = [
            article for article in recent_articles
            if article["topic"].lower() == topic_filter.lower()
        ]

    recent_articles.sort(
        key=lambda item: item["_published_at"] or datetime.min.replace(tzinfo=UTC),
        reverse=True
    )

    return jsonify({
        "generated_at": utc_now(),
        "window_days": days,
        "articles": [
            public_article(article)
            for article in recent_articles[:limit]
        ],
    })


@app.post("/api/refresh")
def refresh():
    init_db()
    for source in get_active_sources():
        fetch_feed(source)
    return jsonify({"status": "refreshed", "generated_at": utc_now()})


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
