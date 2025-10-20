#!/usr/bin/env python3
"""
Zscaler Help Releases RSS Generator (robust)

- Crawlt automatisch help.zscaler.com über die Sitemap (inkl. .xml.gz),
  findet alle Release-Notes- und What's-New-Seiten (inkl. neuer Produkte)
  und extrahiert Artikel/Einträge.
- Baut einen RSS-Feed und schreibt ihn nach ./public/rss.xml.
- Optionales Zeitfenster über BACKFILL_DAYS (Standard: 14 Tage).

Voraussetzungen:
  pip install requests beautifulsoup4 feedgen python-dateutil lxml
"""

import os
import re
import time
import gzip
import io
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
    "User-Agent": "Mozilla/5.0 (compatible; Zscaler-Release-RSS/1.1; +https://www.zscaler.com)",
    "Accept": "application/xml,text/xml;q=0.9,*/*;q=0.8"
}
OUTPUT_DIR = os.path.join(os.getcwd(), "public")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "rss.xml")

# Muster für relevante Seiten
RELEASE_PAGE_PATTERNS = [
    re.compile(r"/[a-z0-9-]+/release-notes/?$", re.I),   # z.B. /zia/release-notes
    re.compile(r"/release-notes/?$", re.I),              # generische Pfade
]
WHATS_NEW_PATTERNS = [
    re.compile(r"/whats-new/?$", re.I),
    re.compile(r"/what's-new/?$", re.I),
]
ARTICLE_URL_HINTS = ["release", "notes", "whats-new", "what's-new", "new"]

# Fallback-Quellen, falls Sitemap leer oder fehlerhaft
FALLBACK_SOURCES = [
    f"{BASE}/whats-new",
    f"{BASE}/zia/release-notes",
    f"{BASE}/zpa/release-notes",
    f"{BASE}/zdx/release-notes",
    f"{BASE}/workload-segmentation/release-notes",
    f"{BASE}/zscaler-private-access/release-notes",  # gelegentliche Alias-Pfade
]


def fetch(url: str, timeout: int = 30) -> str:
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.text


def fetch_bytes(url: str, timeout: int = 30) -> bytes:
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.content


def maybe_decompress_sitemap(url: str, content: bytes) -> bytes:
    # Entpacke, wenn URL auf .gz endet oder Content-Type gzip ist
    ct = ""
    try:
        # Wir holen den Content-Type mit eine leichte HEAD-Anfrage (optional)
        head = requests.head(url, headers=HEADERS, timeout=15, allow_redirects=True)
        ct = head.headers.get("Content-Type", "")
    except Exception:
        pass

    if url.lower().endswith(".gz") or ("gzip" in ct.lower() or "x-gzip" in ct.lower()):
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(content)) as gz:
                return gz.read()
        except Exception as e:
            print(f"[WARN] Gzip-Entpackung fehlgeschlagen für {url}: {e}")
    return content


def is_help_domain(url: str) -> bool:
    try:
        p = urlparse(url)
        return p.netloc.endswith("help.zscaler.com")
    except Exception:
        return False


def parse_sitemap(url: str) -> list[str]:
    """
    Lädt sitemap.xml oder eine Sub-Sitemap. Unterstützt sitemapindex mit rekursiver Auflösung.
    Liefert alle <loc>-URLs zurück, tolerant gegenüber Namespaces und gzip.
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
        # Entfernt Namespace-Prefixe
        return tag.split("}")[-1]

    urls: list[str] = []

    if localname(root.tag) == "sitemapindex":
        for sm_el in root:
            if localname(sm_el.tag) != "sitemap":
                continue
            loc_el = None
            for child in sm_el:
                if localname(child.tag) == "loc":
                    loc_el = child
                    break
            if loc_el is not None and loc_el.text:
                sub_url = loc_el.text.strip()
                urls.extend(parse_sitemap(sub_url))
        return urls

    if localname(root.tag) == "urlset":
        for url_el in root:
            if localname(url_el.tag) != "url":
                continue
            loc_el = None
            for child in url_el:
                if localname(child.tag) == "loc":
                    loc_el = child
                    break
            if loc_el is not None and loc_el.text:
                loc = loc_el.text.strip()
                urls.append(loc)

    # Falls Struktur anders ist, suche generisch nach allen <loc>-Elementen
    if not urls:
        for el in root.iter():
            if localname(el.tag) == "loc" and el.text:
                urls.append(el.text.strip())

    return urls


def discover_pages_from_sitemap() -> tuple[list[str], list[str]]:
    """
    Entdeckt Release-Notes- und What's-New-Seiten aus der Sitemap.
    Gibt zwei Listen zurück: (release_pages, whats_new_pages)
    """
    all_urls = parse_sitemap(SITEMAP_URL)
    release_pages: set[str] = set()
    whats_new_pages: set[str] = set()

    for u in all_urls:
        if not is_help_domain(u):
            continue
        path = urlparse(u).path
        for patt in RELEASE_PAGE_PATTERNS:
            if patt.search(path):
                release_pages.add(u)
                break
        for patt in WHATS_NEW_PATTERNS:
            if patt.search(path):
                whats_new_pages.add(u)
                break

    return sorted(release_pages), sorted(whats_new_pages)


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

    # 3) Heuristik
    candidates = soup.select("*")
    for c in candidates:
        t = c.get_text(" ", strip=True)
        tl = t.lower()
        if any(k in tl for k in ["published", "updated", "release", "date", "released", "last updated"]):
            m = re.search(r"(\d{1,2}\s+\w+\s+\d{4}|\w+\s+\d{1,2},\s*\d{4}|\d{4}-\d{2}-\d{2})", t)
            if m:
                return normalize_date(m.group(1))

    return datetime.now(timezone.utc)


def extract_articles_from_page(url: str) -> list[dict]:
    """
    Extrahiert Artikel/Einträge von einer Indexseite (Release Notes oder What's New).
    """
    try:
        html = fetch(url)
    except Exception as e:
        print(f"[WARN] Seite nicht abrufbar: {url} -> {e}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    items: list[dict] = []

    for a in soup.select("a[href]"):
        href = a.get("href")
        if not href:
            continue
        link = urljoin(BASE, href) if href.startswith("/") else href
        if not is_help_domain(link):
            continue

        title = a.get_text(strip=True)
        if not title or len(title) < 5:
            continue

        url_l = link.lower()
        if any(h in url_l for h in ARTICLE_URL_HINTS):
            items.append({"title": title, "link": link})

    # Dedup
    seen = set()
    clean: list[dict] = []
    for it in items:
        if it["link"] in seen:
            continue
        seen.add(it["link"])
        path = urlparse(it["link"]).path
        if path.strip("/"):
            clean.append(it)

    # Anreichern mit Datum
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

    # Fallback: wenn keine Unterartikel gefunden, nimm die Seite selbst
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

    BACKFILL_DAYS = int(os.getenv("BACKFILL_DAYS", "14"))
    cutoff = datetime.now(timezone.utc) - timedelta(days=BACKFILL_DAYS)

    release_pages, whats_new_pages = discover_pages_from_sitemap()
    print(f"[INFO] Release-Notes-Seiten gefunden: {len(release_pages)}")
    print(f"[INFO] What's-New-Seiten gefunden: {len(whats_new_pages)}")

    # Fallback, falls die Sitemap keine Seiten liefert
    if not release_pages and not whats_new_pages:
        print(f"[WARN] Keine Seiten aus Sitemap gefunden, nutze Fallback-Quellen.")
        release_pages = []
        whats_new_pages = []
        for src in FALLBACK_SOURCES:
            # zuordnen: Release vs What's New
            if "whats-new" in src:
                whats_new_pages.append(src)
            else:
                release_pages.append(src)

    aggregated: list[dict] = []

    # Release-Notes
    for page_url in release_pages:
        try:
            items = extract_articles_from_page(page_url)
            aggregated.extend(items)
            time.sleep(0.5)
        except Exception as e:
            print(f"[WARN] Fehler beim Extrahieren (Release): {page_url} -> {e}")

    # What's New
    for page_url in whats_new_pages:
        try:
            items = extract_articles_from_page(page_url)
            aggregated.extend(items)
            time.sleep(0.5)
        except Exception as e:
            print(f"[WARN] Fehler beim Extrahieren (Whats New): {page_url} -> {e}")

    # Zeitfenster
    window_items = [it for it in aggregated if it["published"] >= cutoff]
    print(f"[INFO] Items gesamt: {len(aggregated)}, innerhalb {BACKFILL_DAYS} Tage: {len(window_items)}")

    # Deduplizieren
    final: list[dict] = []
    seen_links = set()
    for it in window_items:
        if it["link"] in seen_links:
            continue
        seen_links.add(it["link"])
        final.append(it)

    # RSS schreiben
    rss_xml = build_feed(final)
    with open(OUTPUT_PATH, "wb") as f:
        f.write(rss_xml)
    print(f"[INFO] RSS geschrieben: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
