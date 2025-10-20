#!/usr/bin/env python3
"""
Zscaler Help Releases RSS Generator (vollständige Sitemap-Nutzung)

- Nutzt die komplette Sitemap (inkl. Sub-Sitemaps und .xml.gz) von help.zscaler.com.
- Filtert alle relevanten Seiten (Release Notes & What's New) direkt aus der Sitemap.
- Extrahiert Titel & Veröffentlichungsdatum je Seite und erstellt einen RSS-Feed.
- Beschränkt den Feed optional mit BACKFILL_DAYS (Standard: 14, z. B. 90).

Voraussetzungen:
  pip install requests beautifulsoup4 feedgen python-dateutil lxml
"""

import os
import re
import io
import gzip
import time
import requests
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from dateutil import parser as dateparser

BASE = "https://help.zscaler.com"
SITEMAP_URL = f"{BASE}/sitemap.xml"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Zscaler-Release-RSS/2.0; +https://www.zscaler.com)",
    "Accept": "application/xml,text/xml;q=0.9,*/*;q=0.8"
}
OUTPUT_DIR = os.path.join(os.getcwd(), "public")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "rss.xml")

# Relevanz-Hinweise für Seiten aus der Sitemap
# Wir berücksichtigen gezielt Release-Notes- und What's-New-Pfade.
URL_INCLUDE_HINTS = [
    "release-notes",        # typische Pfade für Release Notes
    "whats-new",            # What's New Übersicht
    "what's-new",           # alternative Schreibweise
]
# Optional: zusätzliche Hinweise, aber mit Vorsicht (zu breit bedeutet Rauschen)
# URL_INCLUDE_HINTS += ["release", "notes"]

# Ausschlussmuster (um offensichtliche Nicht-Artikel zu vermeiden)
URL_EXCLUDE_HINTS = [
    "/tag/", "/taxonomy/", "/author/", "/search", "/attachment", "/node/",
]

# Minimal-Pause zwischen Abrufen (freundliches Crawling)
FETCH_DELAY_SEC = 0.3


def fetch(url: str, timeout: int = 30) -> str:
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.text


def fetch_bytes(url: str, timeout: int = 30) -> bytes:
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.content


def maybe_decompress_sitemap(url: str, content: bytes) -> bytes:
    # Entpacken, wenn URL .gz endet oder der Content tatsächlich gzipped ist
    try:
        # Wenn es nach gzip aussieht, versuche zu entpacken
        if url.lower().endswith(".gz"):
            with gzip.GzipFile(fileobj=io.BytesIO(content)) as gz:
                return gz.read()
        # Einige Server senden ungekennzeichnete gzip-Daten; heuristischer Versuch
        if content[:2] == b"\x1f\x8b":
            with gzip.GzipFile(fileobj=io.BytesIO(content)) as gz:
                return gz.read()
    except Exception as e:
        print(f"[WARN] Gzip-Entpackung fehlgeschlagen für {url}: {e}")
    return content


def is_help_domain(url: str) -> bool:
    try:
        p = urlparse(url)
        return p.scheme in ("http", "https") and p.netloc.endswith("help.zscaler.com")
    except Exception:
        return False


def parse_sitemap(url: str) -> list[str]:
    """
    Lädt sitemap.xml oder eine Sub-Sitemap. Unterstützt sitemapindex rekursiv und .xml.gz.
    Gibt eine flache Liste aller <loc>-URLs zurück.
    """
    try:
        raw = fetch_bytes(url)
        content = maybe_decompress_sitemap(url, raw)
    except Exception as e:
        print(f"[WARN] Sitemap abrufen fehlgeschlagen: {url} -> {e}")
        return []

    try:
        root = ET.fromstring(content)
    except Exception as e:
        print(f"[WARN] Sitemap XML-Parsing fehlgeschlagen: {url} -> {e}")
        return []

    def localname(tag: str) -> str:
        return tag.split("}")[-1]

    urls: list[str] = []

    tag = localname(root.tag)
    if tag == "sitemapindex":
        for sm in root:
            if localname(sm.tag) != "sitemap":
                continue
            loc_el = next((c for c in sm if localname(c.tag) == "loc"), None)
            if loc_el is not None and loc_el.text:
                sub = loc_el.text.strip()
                urls.extend(parse_sitemap(sub))
        return urls

    if tag == "urlset":
        for u in root:
            if localname(u.tag) != "url":
                continue
            loc_el = next((c for c in u if localname(c.tag) == "loc"), None)
            if loc_el is not None and loc_el.text:
                urls.append(loc_el.text.strip())

    # Generischer Fallback: sammle alle <loc>
    if not urls:
        for el in root.iter():
            if localname(el.tag) == "loc" and el.text:
                urls.append(el.text.strip())

    return urls


def select_relevant_urls(all_urls: list[str]) -> list[str]:
    """
    Filtert die aus der Sitemap gewonnenen URLs auf relevante Seiten:
    - Domain help.zscaler.com
    - Enthalten Hinweise auf Release-Notes oder What's New
    - Schließt offensichtliche Nicht-Artikel aus
    """
    relevant: set[str] = set()
    for u in all_urls:
        if not is_help_domain(u):
            continue
        path = urlparse(u).path.lower()
        if any(excl in path for excl in URL_EXCLUDE_HINTS):
            continue
        if any(hint in path for hint in URL_INCLUDE_HINTS):
            relevant.add(u)
    return sorted(relevant)


def normalize_date(date_text: str | None) -> datetime:
    if not date_text:
        return datetime.now(timezone.utc)
    try:
        dt = dateparser.parse(date_text)
        if not dt:
            return datetime.now(timezone.utc)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def extract_date_from_soup(soup: BeautifulSoup) -> datetime:
    # 1) strukturierte Metadaten
    meta_selectors = [
        ('meta[property="article:published_time"]', "content"),
        ('meta[name="article:published_time"]', "content"),
        ('meta[property="og:updated_time"]', "content"),
        ('meta[name="date"]', "content"),
    ]
    for css, attr in meta_selectors:
        el = soup.select_one(css)
        if el and el.get(attr):
            return normalize_date(el.get(attr))

    # 2) time-Tag
    time_el = soup.find("time")
    if time_el:
        if time_el.get("datetime"):
            return normalize_date(time_el.get("datetime"))
        txt = time_el.get_text(strip=True)
        if txt:
            return normalize_date(txt)

    # 3) Sichtbare Datumstexte
    for c in soup.select("*"):
        t = c.get_text(" ", strip=True)
        tl = t.lower()
        if any(k in tl for k in ["published", "updated", "release", "date", "released", "last updated"]):
            m = re.search(r"(\d{1,2}\s+\w+\s+\d{4}|\w+\s+\d{1,2},\s*\d{4}|\d{4}-\d{2}-\d{2})", t)
            if m:
                return normalize_date(m.group(1))

    # Fallback: jetzt
    return datetime.now(timezone.utc)


def extract_title(soup: BeautifulSoup, default: str) -> str:
    # Bevorzugt H1, sonst <title>, sonst Fallback
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)
    if soup.title and soup.title.get_text(strip=True):
        return soup.title.get_text(strip=True)
    return default


def build_feed(items: list[dict]) -> bytes:
    fg = FeedGenerator()
    fg.id(BASE)
    fg.title("Zscaler Releases (help.zscaler.com)")
    fg.link(href=BASE, rel='alternate')
    fg.link(href=urljoin(BASE, "/rss.xml"), rel='self')
    fg.description("Automatisch generierter Feed für neue Zscaler Release Notes über alle Produkte.")
    fg.language('de')

    items_sorted = sorted(items, key=lambda x: x["published"], reverse=True)
    for it in items_sorted:
        fe = fg.add_entry()
        fe.id(it["link"])
        fe.title(it["title"])
        fe.link(href=it["link"])
        fe.published(it["published"])
        fe.updated(it["published"])
        fe.summary(f"{it['title']} – Quelle: {it['source_page']}")
    return fg.rss_str(pretty=True)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    BACKFILL_DAYS = int(os.getenv("BACKFILL_DAYS", "14"))
    cutoff = datetime.now(timezone.utc) - timedelta(days=BACKFILL_DAYS)

    # 1) Vollständige Sitemap einlesen
    all_urls = parse_sitemap(SITEMAP_URL)
    print(f"[INFO] Gesamt-URLs aus Sitemap: {len(all_urls)}")

    # 2) Relevante Seiten auswählen (Release Notes & What's New)
    candidates = select_relevant_urls(all_urls)
    print(f"[INFO] Relevante Seiten nach Filter: {len(candidates)}")
    for c in candidates[:15]:
        print(f" - {c}")
    if len(candidates) > 15:
        print(f" ... ({len(candidates) - 15} weitere)")

    # 3) Jede Kandidaten-Seite abrufen und Metadaten extrahieren
    aggregated: list[dict] = []
    for url in candidates:
        try:
            html = fetch(url)
            soup = BeautifulSoup(html, "html.parser")
            title = extract_title(soup, default=url)
            published = extract_date_from_soup(soup)
            aggregated.append({
                "title": title,
                "link": url,
                "published": published,
                "source_page": url
            })
            time.sleep(FETCH_DELAY_SEC)
        except Exception as e:
            print(f"[WARN] Fehler beim Abruf: {url} -> {e}")

    print(f"[INFO] Extrahierte Seiten gesamt: {len(aggregated)}")

    # 4) Zeitfenster anwenden
    window_items = [it for it in aggregated if it["published"] >= cutoff]
    print(f"[INFO] Innerhalb der letzten {BACKFILL_DAYS} Tage: {len(window_items)}")

    # 5) Dedup nach Link
    final: list[dict] = []
    seen = set()
    for it in window_items:
        if it["link"] in seen:
            continue
        seen.add(it["link"])
        final.append(it)

    # 6) RSS bauen und schreiben
    rss_xml = build_feed(final)
    with open(OUTPUT_PATH, "wb") as f:
        f.write(rss_xml)
    print(f"[INFO] RSS geschrieben: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
