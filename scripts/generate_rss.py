#!/usr/bin/env python3
"""
Zscaler Help Releases RSS Generator

- Crawlt automatisch help.zscaler.com über die Sitemap, findet alle Release-Notes-Seiten
  (inkl. neuer Produkte) und extrahiert Artikel/Einträge.
- Baut einen RSS-Feed und schreibt ihn nach ./public/rss.xml.
- Optionales Zeitfenster über BACKFILL_DAYS (Standard: 14 Tage).

Voraussetzungen:
  pip install requests beautifulsoup4 feedgen python-dateutil lxml
"""

import os
import re
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
    "User-Agent": "Mozilla/5.0 (compatible; Zscaler-Release-RSS/1.0; +https://www.zscaler.com)"
}
OUTPUT_DIR = os.path.join(os.getcwd(), "public")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "rss.xml")

# Muster für Release-Notes-Seiten und Artikel
RELEASE_PAGE_PATTERNS = [
    re.compile(r"/[a-z0-9-]+/release-notes/?$", re.I),   # z.B. /zia/release-notes
    re.compile(r"/release-notes/?$", re.I),              # generische Pfade
]
ARTICLE_URL_HINTS = ["release", "notes", "whats-new", "what's-new", "new"]


def fetch(url: str, timeout: int = 30) -> str:
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.text


def fetch_bytes(url: str, timeout: int = 30) -> bytes:
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.content


def is_help_domain(url: str) -> bool:
    try:
        p = urlparse(url)
        return p.netloc.endswith("help.zscaler.com")
    except Exception:
        return False


def parse_sitemap(url: str) -> list[str]:
    """
    Lädt sitemap.xml oder eine Sub-Sitemap. Unterstützt sitemapindex mit rekursiver Auflösung.
    Liefert alle <loc>-URLs zurück.
    """
    try:
        content = fetch_bytes(url)
    except Exception as e:
        print(f"[WARN] Sitemap fehlgeschlagen: {url} -> {e}")
        return []

    try:
        root = ET.fromstring(content)
    except Exception as e:
        print(f"[WARN] Sitemap XML-Parsing fehlgeschlagen: {url} -> {e}")
        return []

    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls: list[str] = []

    # Prüfe, ob sitemapindex
    if root.tag.endswith("sitemapindex"):
        for sm_el in root.findall("sm:sitemap", ns):
            loc_el = sm_el.find("sm:loc", ns)
            if loc_el is not None and loc_el.text:
                sub_url = loc_el.text.strip()
                urls.extend(parse_sitemap(sub_url))
        return urls

    # Sonst: normale urlset
    for url_el in root.findall("sm:url", ns):
        loc_el = url_el.find("sm:loc", ns)
        if loc_el is not None and loc_el.text:
            loc = loc_el.text.strip()
            urls.append(loc)

    return urls


def discover_release_pages_from_sitemap() -> list[str]:
    """
    Entdeckt alle Release-Notes-Seiten über die Sitemap automatisch.
    """
    all_urls = parse_sitemap(SITEMAP_URL)
    release_pages: set[str] = set()
    for u in all_urls:
        if not is_help_domain(u):
            continue
        path = urlparse(u).path
        for patt in RELEASE_PAGE_PATTERNS:
            if patt.search(path):
                release_pages.add(u)
                break
    return sorted(release_pages)


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
    # 1) Versuche strukturierte Metadaten
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

    # 3) Heuristik: Texte mit "Published", "Updated", "Release", "Date"
    candidates = soup.select("*")
    for c in candidates:
        t = c.get_text(" ", strip=True)
        tl = t.lower()
        if any(k in tl for k in ["published", "updated", "release", "date", "released", "last updated"]):
            m = re.search(r"(\d{1,2}\s+\w+\s+\d{4}|\w+\s+\d{1,2},\s*\d{4}|\d{4}-\d{2}-\d{2})", t)
            if m:
                return normalize_date(m.group(1))

    # Fallback: jetzt
    return datetime.now(timezone.utc)


def extract_articles_from_release_page(url: str) -> list[dict]:
    """
    Extrahiert Einzelartikel/Einträge aus einer Release-Notes-Seite.
    Greift auf gängige Link-Pattern zurück und dedupliziert.
    """
    try:
        html = fetch(url)
    except Exception as e:
        print(f"[WARN] Release-Seite nicht abrufbar: {url} -> {e}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    items: list[dict] = []

    # Kandidaten-Links innerhalb des Inhalts
    for a in soup.select("a[href]"):
        href = a.get("href")
        if not href:
            continue
        # Absolut machen
        if href.startswith("/"):
            link = urljoin(BASE, href)
        else:
            link = href

        # Nur help.zscaler.com
        if not is_help_domain(link):
            continue

        # Titel
        title = a.get_text(strip=True)
        if not title or len(title) < 5:
            continue

        # Relevanz anhand URL-Hints
        url_l = link.lower()
        if any(h in url_l for h in ARTICLE_URL_HINTS):
            items.append({
                "title": title,
                "link": link
            })

    # Deduplizieren nach Link und grob filtern:
    seen = set()
    clean: list[dict] = []
    for it in items:
        link = it["link"]
        if link in seen:
            continue
        seen.add(link)
        path = urlparse(link).path
        if path.strip("/"):
            clean.append(it)

    # Für jeden Artikel das Datum bestimmen
    enriched: list[dict] = []
    for it in clean:
        try:
            art_html = fetch(it["link"])
            art_soup = BeautifulSoup(art_html, "html.parser")
            published = extract_date_from_soup(art_soup)
        except Exception:
            published = datetime.now(timezone.utc)
        enriched.append({
            "title": it["title"],
            "link": it["link"],
            "published": published,
            "source_page": url
        })

    # Falls keine Unterartikel gefunden, nimm die Seite selbst als Eintrag
    if not enriched:
        published = extract_date_from_soup(soup)
        enriched.append({
            "title": soup.title.get_text(strip=True) if soup.title else url,
            "link": url,
            "published": published,
            "source_page": url
        })

    return enriched


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

    # Anzahl Tage, die in die Vergangenheit berücksichtigt werden (Standard: 14)
    BACKFILL_DAYS = int(os.getenv("BACKFILL_DAYS", "14"))
    cutoff = datetime.now(timezone.utc) - timedelta(days=BACKFILL_DAYS)

    # 1) Release-Notes-Seiten automatisch über Sitemap finden
    release_pages = discover_release_pages_from_sitemap()
    print(f"[INFO] Gefundene Release-Notes-Seiten: {len(release_pages)}")
    for rp in release_pages[:10]:
        print(f" - {rp}")
    if len(release_pages) > 10:
        print(f" ... ({len(release_pages)-10} weitere)")

    # 2) Artikel aus allen Release-Notes-Seiten extrahieren
    aggregated: list[dict] = []
    for page_url in release_pages:
        try:
            items = extract_articles_from_release_page(page_url)
            aggregated.extend(items)
            time.sleep(0.5)  # höflicher Crawl
        except Exception as e:
            print(f"[WARN] Fehler beim Extrahieren: {page_url} -> {e}")

    # 3) Nach Zeitfenster filtern (nur letzte BACKFILL_DAYS)
    window_items = [it for it in aggregated if it["published"] >= cutoff]
    print(f"[INFO] Gefundene Items gesamt: {len(aggregated)}, innerhalb {BACKFILL_DAYS} Tage: {len(window_items)}")

    # 4) Final deduplizieren
    final: list[dict] = []
    seen_links = set()
    for it in window_items:
        if it["link"] in seen_links:
            continue
        seen_links.add(it["link"])
        final.append(it)

    # 5) RSS bauen und schreiben
    rss_xml = build_feed(final)
    with open(OUTPUT_PATH, "wb") as f:
        f.write(rss_xml)
    print(f"[INFO] RSS geschrieben: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
