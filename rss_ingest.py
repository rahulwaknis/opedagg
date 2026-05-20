import os
import sqlite3
import feedparser
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse, urlunparse


DB_NAME = "opinion_articles.db"

TAG_OPTIONS = {
    "access_type": ("free", "paywalled", "unknown"),
    "article_type": ("opinion", "news", "analysis", "unknown"),
    "stance": ("pro", "anti", "mixed", "neutral", "unclear"),
    "confidence": ("low", "medium", "high"),
}

ACCESS_TYPE_BY_SOURCE = {
    "Financial Times Opinion": "paywalled",
    "Mint Opinion": "paywalled",
    "The Guardian Opinion": "free",
}


RSS_FEEDS = [
    {
        "source": "Indian Express Opinion",
        "url": "https://indianexpress.com/section/opinion/feed/"
    },
    {
        "source": "Mint Opinion",
        "url": "https://www.livemint.com/rss/opinionRSS"
    },
    {
        "source": "The Hindu Opinion",
        "url": "https://www.thehindu.com/opinion/feeder/default.rss"
    },
    {
        "source": "India Today Opinion",
        "url": "https://www.indiatoday.in/rss/1836291"
    },
    {
        "source": "Financial Times Opinion",
        "url": "https://www.ft.com/opinion?format=rss"
    },
    {
        "source": "The Guardian Opinion",
        "url": "https://www.theguardian.com/commentisfree/rss"
    },
    {
        "source": "ThePrint Opinion",
        "url": "https://theprint.in/category/opinion/feed/"
    },
    {
        "source": "The Statesman Opinion",
        "url": "https://www.thestatesman.com/rss/opinion"
    },
]

TOPIC_BUCKETS = [
    {
        "name": "Politics",
        "description": "Elections, parties, institutions, governance, and political strategy."
    },
    {
        "name": "Economy",
        "description": "Macroeconomics, business, finance, trade, jobs, and markets."
    },
    {
        "name": "Foreign Policy",
        "description": "Diplomacy, geopolitics, conflict, alliances, and global institutions."
    },
    {
        "name": "Society",
        "description": "Culture, identity, education, health, cities, and social change."
    },
    {
        "name": "Technology",
        "description": "AI, platforms, digital policy, science, and technical change."
    },
    {
        "name": "Climate",
        "description": "Climate policy, energy transition, environment, and sustainability."
    },
]


def utc_now():
    return datetime.now(UTC).isoformat()


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def normalize_url(url: str) -> str:
    """
    Cleans URLs so duplicate links are easier to catch.
    Removes tracking parameters and fragments.
    """
    parsed = urlparse(url)
    clean = parsed._replace(query="", fragment="")
    return urlunparse(clean)


def table_exists(cursor, table_name):
    cursor.execute("""
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
    """, (table_name,))
    return cursor.fetchone() is not None


def get_table_columns(cursor, table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row["name"] for row in cursor.fetchall()}


def add_column_if_missing(cursor, table_name, column_name, definition):
    if column_name not in get_table_columns(cursor, table_name):
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def ensure_article_tag_columns(cursor):
    add_column_if_missing(
        cursor,
        "articles",
        "access_type",
        "TEXT NOT NULL DEFAULT 'unknown' CHECK(access_type IN ('free', 'paywalled', 'unknown'))"
    )
    add_column_if_missing(
        cursor,
        "articles",
        "article_type",
        "TEXT NOT NULL DEFAULT 'unknown' CHECK(article_type IN ('opinion', 'news', 'analysis', 'unknown'))"
    )
    add_column_if_missing(
        cursor,
        "articles",
        "stance",
        "TEXT NOT NULL DEFAULT 'unclear' CHECK(stance IN ('pro', 'anti', 'mixed', 'neutral', 'unclear'))"
    )
    add_column_if_missing(
        cursor,
        "articles",
        "confidence",
        "TEXT NOT NULL DEFAULT 'low' CHECK(confidence IN ('low', 'medium', 'high'))"
    )


def migrate_legacy_articles(cursor):
    if not table_exists(cursor, "articles"):
        return

    article_columns = get_table_columns(cursor, "articles")
    is_legacy_schema = "source" in article_columns and "source_id" not in article_columns

    if is_legacy_schema and not table_exists(cursor, "articles_legacy"):
        cursor.execute("ALTER TABLE articles RENAME TO articles_legacy")


def create_tables(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            feed_url TEXT NOT NULL UNIQUE,
            homepage_url TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            topic_id INTEGER,
            title TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            published TEXT,
            author TEXT,
            summary TEXT,
            fetched_at TEXT NOT NULL,
            ai_tags TEXT NOT NULL DEFAULT '[]',
            ai_summary TEXT,
            ai_processed_at TEXT,
            access_type TEXT NOT NULL DEFAULT 'unknown'
                CHECK(access_type IN ('free', 'paywalled', 'unknown')),
            article_type TEXT NOT NULL DEFAULT 'unknown'
                CHECK(article_type IN ('opinion', 'news', 'analysis', 'unknown')),
            stance TEXT NOT NULL DEFAULT 'unclear'
                CHECK(stance IN ('pro', 'anti', 'mixed', 'neutral', 'unclear')),
            confidence TEXT NOT NULL DEFAULT 'low'
                CHECK(confidence IN ('low', 'medium', 'high')),
            FOREIGN KEY (source_id) REFERENCES sources (id),
            FOREIGN KEY (topic_id) REFERENCES topics (id)
        )
    """)

    ensure_article_tag_columns(cursor)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_articles_source_id
        ON articles (source_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_articles_topic_id
        ON articles (topic_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_articles_published
        ON articles (published)
    """)


def seed_sources(cursor):
    now = utc_now()
    for feed in RSS_FEEDS:
        homepage_url = f"{urlparse(feed['url']).scheme}://{urlparse(feed['url']).netloc}"
        cursor.execute("""
            INSERT INTO sources (name, feed_url, homepage_url, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                feed_url = excluded.feed_url,
                homepage_url = excluded.homepage_url,
                updated_at = excluded.updated_at
        """, (
            feed["source"],
            feed["url"],
            homepage_url,
            now,
            now
        ))


def seed_topics(cursor):
    now = utc_now()
    for topic in TOPIC_BUCKETS:
        cursor.execute("""
            INSERT INTO topics (name, description, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                description = excluded.description
        """, (
            topic["name"],
            topic["description"],
            now
        ))


def migrate_legacy_rows(cursor):
    if not table_exists(cursor, "articles_legacy"):
        return

    cursor.execute("""
        INSERT OR IGNORE INTO articles (
            source_id, title, url, published, summary, fetched_at
        )
        SELECT
            sources.id,
            articles_legacy.title,
            articles_legacy.url,
            articles_legacy.published,
            articles_legacy.summary,
            articles_legacy.fetched_at
        FROM articles_legacy
        JOIN sources ON sources.name = articles_legacy.source
    """)


def backfill_article_tags(cursor):
    cursor.execute("""
        SELECT
            articles.id,
            sources.name AS source_name,
            articles.title,
            articles.summary
        FROM articles
        JOIN sources ON sources.id = articles.source_id
        WHERE articles.access_type = 'unknown'
            AND articles.article_type = 'unknown'
            AND articles.stance = 'unclear'
            AND articles.confidence = 'low'
    """)
    rows = cursor.fetchall()

    for row in rows:
        tags = infer_article_tags(
            row["source_name"],
            row["title"],
            row["summary"] or ""
        )
        cursor.execute("""
            UPDATE articles
            SET
                ai_tags = ?,
                access_type = ?,
                article_type = ?,
                stance = ?,
                confidence = ?
            WHERE id = ?
        """, (
            json.dumps(tags, sort_keys=True),
            tags["access_type"],
            tags["article_type"],
            tags["stance"],
            tags["confidence"],
            row["id"]
        ))


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    migrate_legacy_articles(cursor)
    create_tables(cursor)
    seed_sources(cursor)
    seed_topics(cursor)
    migrate_legacy_rows(cursor)
    backfill_article_tags(cursor)

    conn.commit()
    conn.close()


def get_active_sources():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, feed_url
        FROM sources
        WHERE active = 1
        ORDER BY name
    """)
    sources = cursor.fetchall()
    conn.close()
    return sources


def infer_article_tags(source_name, title, summary):
    """
    Assign conservative defaults from RSS metadata.
    Stance needs a target issue/person, so it stays unclear until reviewed or AI-tagged.
    """
    text = f"{title} {summary}".lower()
    access_type = ACCESS_TYPE_BY_SOURCE.get(source_name, "unknown")
    article_type = "unknown"
    confidence = "low"

    if "opinion" in source_name.lower() or "commentisfree" in source_name.lower():
        article_type = "opinion"
        confidence = "high" if access_type != "unknown" else "medium"
    elif "analysis" in text:
        article_type = "analysis"
        confidence = "medium"
    elif any(word in text for word in ("op-ed", "editorial", "column")):
        article_type = "opinion"
        confidence = "medium"

    tags = {
        "access_type": access_type,
        "article_type": article_type,
        "stance": "unclear",
        "confidence": confidence,
    }
    validate_article_tags(tags)
    return tags


def validate_article_tags(tags):
    for tag_name, allowed_values in TAG_OPTIONS.items():
        if tags[tag_name] not in allowed_values:
            raise ValueError(f"Invalid {tag_name}: {tags[tag_name]}")


def insert_article(source_id, title, url, published, author, summary, tags):
    conn = get_connection()
    cursor = conn.cursor()
    tag_json = json.dumps(tags, sort_keys=True)

    try:
        cursor.execute("""
            INSERT INTO articles (
                source_id, title, url, published, author, summary, fetched_at,
                ai_tags, access_type, article_type, stance, confidence
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            source_id,
            title,
            url,
            published,
            author,
            summary,
            utc_now(),
            tag_json,
            tags["access_type"],
            tags["article_type"],
            tags["stance"],
            tags["confidence"]
        ))

        conn.commit()
        return True

    except sqlite3.IntegrityError:
        # Duplicate URL
        return False

    finally:
        conn.close()


def parse_published_date(entry):
    if hasattr(entry, "published"):
        return entry.published

    if hasattr(entry, "updated"):
        return entry.updated

    return None


def parse_entry_datetime(entry):
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        return datetime(*entry.published_parsed[:6], tzinfo=UTC)

    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        return datetime(*entry.updated_parsed[:6], tzinfo=UTC)

    return None


def fetch_feed(feed_config):
    source_id = feed_config["id"]
    source_name = feed_config["name"]
    feed_url = feed_config["feed_url"]

    print(f"\nFetching: {source_name}")

    feed = feedparser.parse(feed_url)

    if feed.bozo:
        print(f"  Warning: feed may have parsing issues: {feed.bozo_exception}")

    new_count = 0
    skipped_old_count = 0
    skipped_undated_count = 0
    cutoff = datetime.now(UTC) - timedelta(days=3)

    for entry in feed.entries:
        title = entry.get("title", "").strip()
        raw_url = entry.get("link", "").strip()
        summary = entry.get("summary", "").strip()
        author = entry.get("author", "").strip() or None
        published = parse_published_date(entry)
        published_at = parse_entry_datetime(entry)

        if not title or not raw_url:
            continue

        if published_at is None:
            skipped_undated_count += 1
            continue

        if published_at < cutoff:
            skipped_old_count += 1
            continue

        clean_url = normalize_url(raw_url)
        tags = infer_article_tags(source_name, title, summary)

        inserted = insert_article(
            source_id=source_id,
            title=title,
            url=clean_url,
            published=published,
            author=author,
            summary=summary,
            tags=tags
        )

        if inserted:
            new_count += 1
            print(f"  Added: {title}")

    print(f"  New articles added: {new_count}")
    print(f"  Skipped older than 3 days: {skipped_old_count}")
    print(f"  Skipped without dates: {skipped_undated_count}")


def show_latest(limit=20):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            sources.name AS source,
            articles.title,
            articles.url,
            articles.published,
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
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()

    print("\nLatest articles:")
    for row in rows:
        topic = row["topic"] or "Untopiced"
        print(f"\n[{row['source']}]")
        print(row["title"])
        print(row["published"])
        print(f"Topic: {topic}")
        print(
            "Tags: "
            f"access={row['access_type']}, "
            f"type={row['article_type']}, "
            f"stance={row['stance']}, "
            f"confidence={row['confidence']}"
        )
        print(row["url"])


def main():
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)

    init_db()

    for source in get_active_sources():
        fetch_feed(source)

    show_latest()


if __name__ == "__main__":
    main()
