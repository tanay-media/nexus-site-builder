#!/usr/bin/env python3
"""
HEA-001 Trail 5 — Transform Archetype static exports into publisher theme.

Usage:
  python3 build_pages.py --site ../0e2dba5e-b89a-4f6a-81be-1cc735c629c9
  python3 build_pages.py --site /path/to/raw-site --out /path/to/output

Copies trail-5/pub.css, pub.js, and shared/assets into output.
Works on any Archetype export folder (arch-* / archetype-* classes).
"""
from __future__ import annotations

import argparse
import hashlib
import html
import re
import shutil
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

TRAIL_DIR = Path(__file__).resolve().parent
BASE_URL = ''  # e.g. /nexus-site-builder for GitHub project Pages

ASSET_IMAGES = [
    "hero-wellness.jpg", "home-featured.jpg", "beauty-face.jpg", "skincare-products.jpg",
    "moisturizer.jpg", "body-care.jpg", "body-exfoliation.jpg", "lab-science.jpg",
    "author.jpg", "reviewer.jpg", "expert-1.jpg", "expert-2.jpg", "expert-3.jpg", "expert-4.jpg",
]

CLASS_MAP = [
    (r'\barch-stat-strip\b', 'pub-stats'),
    (r'\barch-stat\b', 'pub-stat'),
    (r'\barch-stat-number\b', 'pub-stat__num'),
    (r'\barch-stat-label\b', 'pub-stat__label'),
    (r'\barch-steps\b', 'pub-steps'),
    (r'\barch-step\b', 'pub-step'),
    (r'\barch-step-num\b', 'pub-step__num'),
    (r'\barch-pull-quote\b', 'pub-pullquote'),
    (r'\barch-key-box\b', 'pub-key-box'),
    (r'\barch-key-title\b', 'pub-key-box__title'),
    (r'\bfaq-section\b', 'pub-faq-section'),
    (r'\bfaq-item\b', 'pub-faq-block'),
    (r'\barchetype-disclaimer\b', 'pub-disclaimer'),
]

KICKER_MAP = {
    'guide': 'Guide', 'roundup': 'Roundup', 'comparison': 'Comparison',
    'entity_profile': 'Analysis', 'analysis': 'Analysis', 'review': 'Review',
    'research': 'Research',
}

CAT_LABELS = {
    'skin-conditions': 'Skin Conditions',
    'skincare-products': 'Skincare Products',
    'active-ingredients': 'Active Ingredients',
    'skincare-routines': 'Skincare Routines',
    'skin-types-concerns': 'Skin Types & Concerns',
    'body-care': 'Body Care',
    'treatments-procedures': 'Treatments & Procedures',
    'skincare-brands': 'Skincare Brands',
}

# Main nav + homepage explore — matches dermat.local top-level categories
PRIMARY_NAV = [
    ('Skin Conditions', '/skin-conditions/'),
    ('Skin Types', '/skin-types-concerns/'),
    ('Products', '/skincare-products/'),
    ('Ingredients', '/active-ingredients/'),
    ('Treatments', '/treatments-procedures/'),
    ('Body Care', '/body-care/'),
]

# Homepage browse grids (WebMD-style link panels)
BROWSE_SECTIONS = [
    ('Skin Conditions', '/skin-conditions/'),
    ('Ingredients', '/active-ingredients/'),
    ('Products', '/skincare-products/'),
    ('Treatments & Procedures', '/treatments-procedures/'),
]

# Homepage video fold + article hero embeds (AAD public YouTube)
@dataclass(frozen=True)
class VideoSpotlight:
    article_path: str
    youtube_id: str
    label: str = ''


VIDEO_SPOTLIGHT: tuple[VideoSpotlight, ...] = (
    VideoSpotlight(
        '/skin-conditions/when-see-dermatologist/',
        '0Cf2zf7dz7c',
        'How to Find a Dermatologist Who Listens',
    ),
    VideoSpotlight(
        '/skin-conditions/eczema-dermatitis/atopic-dermatitis/',
        'T_HbQo5oWak',
        'Eczema-Friendly Skin Care Tips',
    ),
    VideoSpotlight(
        '/skin-conditions/acne/best-acne-products/',
        'GSH415m3W3s',
        'At-Home Acne Tips From Dermatologists',
    ),
    VideoSpotlight(
        '/skin-types-concerns/determine-skin-type/',
        's-26VmKhGHM',
        '5 Dermatologist Tips for Healthy Skin',
    ),
    VideoSpotlight(
        '/active-ingredients/retinol-vs-tretinoin/',
        'A-Dzt7-oF98',
        'The #1 Anti-Aging Ingredient',
    ),
)

VIDEO_BY_PATH: dict[str, str] = {v.article_path: v.youtube_id for v in VIDEO_SPOTLIGHT}

REVIEWERS = [
    {'name': 'Dr. Sarah Chen', 'cred': 'Board-Certified Dermatologist', 'img': 'expert-1.jpg'},
    {'name': 'Dr. James Okonkwo', 'cred': 'Clinical Researcher', 'img': 'expert-2.jpg'},
    {'name': 'Dr. Maria Santos', 'cred': 'PharmD, Skincare Specialist', 'img': 'expert-3.jpg'},
    {'name': 'Dr. David Kim', 'cred': 'MD, Cosmetic Dermatology', 'img': 'expert-4.jpg'},
]


@dataclass
class Article:
    title: str
    desc: str
    path: str
    kicker: str = 'Guide'
    time: str = '6 min read'
    author: str = 'Editorial Team'
    author_cred: str = ''
    author_img: str = ''
    cat: str = 'skin-care'
    image: str = ''
    badge: str = ''


@dataclass
class Category:
    title: str
    path: str
    meta: str = ''
    image: str = ''


@dataclass
class HubTopic:
    title: str
    path: str
    desc: str = ''
    icon: str = ''
    image: str = ''
    articles: list[Article] = field(default_factory=list)


@dataclass
class HubPage:
    cat: Category
    intro: str = ''
    topics: list[HubTopic] = field(default_factory=list)
    articles: list[Article] = field(default_factory=list)
    breadcrumbs: list[tuple[str, str]] = field(default_factory=list)


IMG_SRC_RE = r'<img[^>]*\bsrc="([^"]+)"'


class ImageRegistry:
    """Map remote Archetype/WP image URLs to local /assets/media/ paths."""

    def __init__(
        self,
        media_dir: Path,
        placeholders: list[Path],
        fetch_remote: bool = False,
        images_source: Optional[Path] = None,
    ) -> None:
        self.media_dir = media_dir
        self.placeholders = placeholders or []
        self.fetch_remote = fetch_remote
        self.images_source = images_source
        self._map: dict[str, str] = {}
        self._basename_index: dict[str, Path] = {}
        if images_source and images_source.is_dir():
            for f in images_source.iterdir():
                if f.is_file() and f.suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
                    self._basename_index[f.name.lower()] = f
        self.media_dir.mkdir(parents=True, exist_ok=True)

    def ingest_html(self, text: str) -> None:
        for url in re.findall(r'\bsrc=["\']([^"\']+)["\']', text, re.I):
            self.resolve(url)
        for url in re.findall(r"url\(['\"]?([^'\")]+)['\"]?\)", text, re.I):
            self.resolve(url.strip())

    def resolve(self, url: str) -> str:
        url = (url or '').strip()
        if not url or url.startswith('data:'):
            return ''
        if url in self._map:
            return self._map[url]
        if url.startswith('/assets/'):
            self._map[url] = url
            return url
        local = self._materialize(url)
        self._map[url] = local
        return local

    def _materialize(self, url: str) -> str:
        parsed = url.split('?')[0]
        basename = Path(parsed).name
        # Match repo images/ folder by filename (same names as WP uploads in raw HTML)
        if basename and self._basename_index:
            src = self._basename_index.get(basename.lower())
            if src:
                dest = self.media_dir / basename
                if not dest.exists():
                    shutil.copy(src, dest)
                return f'/assets/media/{basename}'

        ext = Path(parsed).suffix.lower()
        if ext not in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
            ext = '.jpg'
        name = hashlib.md5(url.encode()).hexdigest()[:14] + ext
        dest = self.media_dir / name
        if not dest.exists():
            fetched = self._try_download(url, dest) if self.fetch_remote else False
            if not fetched:
                self._copy_placeholder(dest)
        return f'/assets/media/{name}'

    def _try_download(self, url: str, dest: Path) -> bool:
        candidates = [url]
        if 'dermat.local' in url:
            candidates.append(url.replace('http://dermat.local', 'http://127.0.0.1'))
            candidates.append(url.replace('https://dermat.local', 'http://127.0.0.1'))
        for candidate in candidates:
            try:
                req = urllib.request.Request(
                    candidate,
                    headers={'User-Agent': 'Trail5-Theme-Builder/1.0'},
                )
                with urllib.request.urlopen(req, timeout=3) as resp:
                    dest.write_bytes(resp.read())
                return True
            except (urllib.error.URLError, OSError, TimeoutError):
                continue
        return False

    def _copy_basename_file(self, src: Path) -> str:
        dest = self.media_dir / src.name
        if not dest.exists():
            shutil.copy(src, dest)
        return f'/assets/media/{src.name}'

    def resolve_for_path(self, rel_path: str) -> str:
        """Match images/ files by URL slug (e.g. hyaluronic-acid → hyaluronic-acid-hero-1.png)."""
        slug = rel_path.strip('/').split('/')[-1]
        if not slug or not self._basename_index:
            return ''
        candidates: list[str] = []
        for stem in (f'{slug}-hero-1', f'{slug}-hero', f'{slug}-img-1', f'{slug}-img', slug):
            for ext in ('.png', '.jpg', '.jpeg', '.webp'):
                candidates.append(f'{stem}{ext}'.lower())
        for name in candidates:
            src = self._basename_index.get(name)
            if src:
                return self._copy_basename_file(src)
        slug_flat = slug.replace('-', '')
        slug_prefix = slug_flat[:12]
        slug_tokens = {t for t in re.split(r'[-_]', slug) if t and t not in ('vs', 'and', 'the', 'for', 'a', 'an')}
        best_score = 0
        best_path = ''
        for name, src in self._basename_index.items():
            base = name.rsplit('.', 1)[0]
            base_flat = base.replace('-', '')
            if slug in base or slug_flat in base_flat:
                if '-hero' in base:
                    return self._copy_basename_file(src)
                if not best_path:
                    best_path = self._copy_basename_file(src)
            if len(slug_prefix) >= 8 and slug_prefix in base_flat:
                if not best_path:
                    best_path = self._copy_basename_file(src)
            base_tokens = {t for t in re.split(r'[-_]', base) if t and t not in ('img', 'hero', 'jpg', 'png', 'jpeg', 'webp')}
            norm_slug = {t.rstrip('s') for t in slug_tokens}
            norm_base = {t.rstrip('s') for t in base_tokens}
            overlap = len(norm_slug & norm_base)
            if overlap >= 2 and overlap > best_score:
                best_score = overlap
                best_path = self._copy_basename_file(src)
        return best_path

    def _copy_placeholder(self, dest: Path) -> None:
        if self.placeholders:
            src = self.placeholders[len(self._map) % len(self.placeholders)]
            shutil.copy(src, dest)
        else:
            dest.write_bytes(
                b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
                b'\xff\xd9'
            )


@dataclass
class SiteData:
    name: str = 'Health'
    tagline: str = 'Expert health guidance, reviewed by specialists'
    nav: list[tuple[str, str]] = field(default_factory=list)
    footer_cols: list[tuple[str, list[tuple[str, str]]]] = field(default_factory=list)
    articles: list[Article] = field(default_factory=list)
    categories: list[Category] = field(default_factory=list)


def u(path: str) -> str:
    """Prefix paths for GitHub project Pages (e.g. /nexus-site-builder)."""
    if not path or path.startswith('http'):
        return path
    if not path.startswith('/'):
        path = '/' + path
    return (BASE_URL.rstrip('/') + path) if BASE_URL else path


def slugify(text: str) -> str:
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'[^\w\s-]', '', text.lower())
    return re.sub(r'[-\s]+', '-', text).strip('-')


def re_sub(pattern: str, repl: str, s: str) -> str:
    return re.sub(pattern, repl, s, flags=re.I | re.S)


def extract(pattern: str, s: str, group: int = 1, default: str = '') -> str:
    m = re.search(pattern, s, re.I | re.S)
    return html.unescape(m.group(group).strip()) if m else default


def transform_content(content: str, images: Optional[ImageRegistry] = None) -> str:
    if images:
        def _src(m: re.Match) -> str:
            local = images.resolve(m.group(1))
            return f'src="{local}"' if local else m.group(0)

        content = re.sub(r'\bsrc=["\']([^"\']+)["\']', _src, content, flags=re.I)

    content = re.sub(r'\sstyle="[^"]*"', '', content, flags=re.I)
    content = re.sub(r"\sstyle='[^']*'", '', content, flags=re.I)
    for old, new in CLASS_MAP:
        content = re.sub(old, new, content)
    content = re.sub(
        r'<table\b',
        r'<div class="pub-table-wrap"><table',
        content,
        flags=re.I,
    )
    content = re.sub(r'</table>', r'</table></div>', content, flags=re.I)

    def add_h2_ids(m: re.Match) -> str:
        tag, inner = m.group(1), m.group(2)
        sid = slugify(re.sub(r'<[^>]+>', '', inner))
        if not sid:
            return m.group(0)
        if 'id=' in tag:
            return m.group(0)
        return f'<h2 id="{sid}"{tag[3:]}>{inner}</h2>'

    content = re.sub(r'<h2([^>]*)>(.*?)</h2>', add_h2_ids, content, flags=re.I | re.S)
    content = re.sub(r'http://dermat\.local', '', content)
    content = re.sub(r'https://dermat\.local', '', content)
    if BASE_URL:
        content = re.sub(
            r'href="(/[^"#]*)"', lambda m: f'href="{u(m.group(1))}"', content,
        )
    return content


def parse_nav(html_text: str) -> list[tuple[str, str]]:
    links = re.findall(
        r'<a[^>]+class="[^"]*arch-nav-link[^"]*"[^>]+href="([^"]+)"[^>]*>([^<]+)</a>',
        html_text,
    )
    if not links:
        links = re.findall(r'<a[^>]+href="(/[^"]+)"[^>]*class="[^"]*arch-nav-link', html_text)
        links = [(h, '') for h in links]
    return [(lbl.strip() or h.strip('/').replace('-', ' ').title(), h) for h, lbl in links if lbl or h]


def parse_footer(html_text: str) -> list[tuple[str, list[tuple[str, str]]]]:
    cols = []
    for col in re.finditer(
        r'<div class="arch-footer-col">.*?<h4>([^<]+)</h4>(.*?)</div>',
        html_text,
        re.S,
    ):
        title = col.group(1).strip()
        links = re.findall(r'<a href="([^"]+)">([^<]+)</a>', col.group(2))
        cols.append((title, links))
    return cols


def parse_feed_cards(html_text: str, images: Optional[ImageRegistry] = None) -> list[Article]:
    articles = []
    for m in re.finditer(
        r'<a href="([^"]+)" class="arc-feed-card">(.*?)</a>',
        html_text,
        re.S,
    ):
        path, block = m.groups()
        img_m = re.search(IMG_SRC_RE, block)
        img = img_m.group(1) if img_m else ''
        badge = extract(r'class="arc-feed-type[^"]*">([^<]*)</div>', block) or 'Guide'
        title = extract(r'class="arc-feed-title">([^<]*)</div>', block) or ''
        desc = extract(r'class="arc-feed-excerpt">([^<]*)</div>', block) or ''
        if not title:
            continue
        art_path = path if path.startswith('/') else '/' + path
        art_img = images.resolve(img) if images and img else ''
        if images and not art_img:
            art_img = images.resolve_for_path(art_path)
        kicker = badge_to_kicker(badge)
        articles.append(Article(
            title=html.unescape(title.strip()),
            desc=html.unescape(desc.strip()),
            path=art_path,
            kicker=kicker,
            image=art_img,
            badge=badge.strip(),
            cat=art_path.strip('/').split('/')[0] if art_path else 'general',
        ))
    return articles


def badge_to_kicker(badge: str) -> str:
    b = badge.lower().replace(' ', '_')
    for key, label in KICKER_MAP.items():
        if key in b:
            return label
    return 'Guide'


def reviewer_for(path: str) -> dict[str, str]:
    idx = int(hashlib.md5(path.encode()).hexdigest(), 16) % len(REVIEWERS)
    return REVIEWERS[idx]


def apply_reviewers(articles: list[Article]) -> None:
    for a in articles:
        r = reviewer_for(a.path)
        a.author = r['name']
        a.author_cred = r['cred']
        a.author_img = r['img']


def articles_under(prefix: str, articles: list[Article]) -> list[Article]:
    return [a for a in articles if a.path.startswith(prefix) and a.path != prefix]


def enrich_hub(hub: HubPage, site: SiteData, hub_by_path: dict[str, HubPage], images: Optional[ImageRegistry] = None) -> None:
    for topic in hub.topics:
        sub = hub_by_path.get(topic.path)
        if sub and sub.cat.image:
            topic.image = sub.cat.image
        elif images and not topic.image:
            topic.image = images.resolve_for_path(topic.path)
        topic.articles = articles_under(topic.path, site.articles)
        if not topic.image and topic.articles:
            topic.image = topic.articles[0].image
        if not topic.image and sub:
            for nested in sub.topics:
                if nested.image:
                    topic.image = nested.image
                    break
        if images:
            backfill_article_images(topic.articles, {a.path: a for a in site.articles}, images)


def hub_topic_slug(topic: HubTopic) -> str:
    return slugify(topic.path.strip('/').split('/')[-1])


def direct_child_articles(hub_path: str, articles: list[Article]) -> list[Article]:
    depth = len(hub_path.strip('/').split('/'))
    out: list[Article] = []
    for a in articles:
        if not a.path.startswith(hub_path) or a.path == hub_path:
            continue
        if len(a.path.strip('/').split('/')) == depth + 1:
            out.append(a)
    return out


def parse_hub_breadcrumbs(html_text: str) -> list[tuple[str, str]]:
    block = extract(r'<div class="arch-hub-breadcrumb">(.*?)</div>', html_text)
    if not block:
        return []
    crumbs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for m in re.finditer(r'<a href="([^"]*)">([^<]+)</a>', block):
        href, lbl = m.group(1), html.unescape(m.group(2).strip())
        if lbl.lower() in ('dermatology', 'home') and href in ('/', ''):
            href, lbl = '/', 'Home'
        key = (lbl.lower(), href)
        if key in seen:
            continue
        seen.add(key)
        crumbs.append((lbl, href if href else ''))
    last = re.search(r'<span>([^<]+)</span>\s*$', block.strip())
    if last:
        crumbs.append((html.unescape(last.group(1).strip()), ''))
    return crumbs


def parse_hub_page(
    html_text: str, rel_url: str, images: Optional[ImageRegistry] = None,
) -> HubPage:
    title = extract(
        r'class="arch-hub-hero"[^>]*>[\s\S]*?<h1>([^<]+)</h1>', html_text,
    ) or extract(r'<title>([^|<]+)', html_text)
    if not title:
        title = rel_url.strip('/').split('/')[-1].replace('-', ' ').title()
    desc = extract(r'class="arch-hub-description">([^<]+)</p>', html_text) or ''
    hero_bg = re.search(
        r'class="arch-hub-hero"[^>]*style="[^"]*url\([\'"]?([^\'")\s]+)',
        html_text,
    )
    hero_img = ''
    if hero_bg and images:
        hero_img = images.resolve(hero_bg.group(1))
    cat = Category(
        title=html.unescape(title.strip()),
        path=rel_url if rel_url.endswith('/') else rel_url + '/',
        meta=html.unescape(desc.strip()),
        image=hero_img,
    )
    intro_raw = extract(
        r'<div class="archetype-hub-intro">(.*?)</div>\s*(?:<!-- archetype:hub-children -->|<div class="arch-hub-topics)',
        html_text,
    )
    intro = transform_content(intro_raw, images) if intro_raw else ''
    topics: list[HubTopic] = []
    for m in re.finditer(
        r'<a href="([^"]+)" class="arch-hub-topic-card">.*?'
        r'class="arch-hub-topic-icon">([^<]*)</div>.*?'
        r'class="arch-hub-topic-title">([^<]*)</div>.*?'
        r'class="arch-hub-topic-desc">([^<]*)</div>',
        html_text,
        re.S,
    ):
        path, icon, topic_title, topic_desc = m.groups()
        topics.append(HubTopic(
            title=html.unescape(topic_title.strip()),
            path=path if path.startswith('/') else '/' + path,
            desc=html.unescape(topic_desc.strip()),
            icon=html.unescape(icon.strip()),
        ))
    articles: list[Article] = []
    for m in re.finditer(
        r'<a href="([^"]+)" class="arch-hub-article-card">(.*?)</a>',
        html_text,
        re.S,
    ):
        path, block = m.groups()
        img_m = re.search(IMG_SRC_RE, block)
        img = img_m.group(1) if img_m else ''
        badge = extract(r'class="arch-hub-article-type">([^<]*)</div>', block) or 'Guide'
        art_title = extract(r'class="arch-hub-article-title">([^<]*)</div>', block) or ''
        art_desc = extract(r'class="arch-hub-article-excerpt">([^<]*)</div>', block) or ''
        if not art_title:
            continue
        art_path = path if path.startswith('/') else '/' + path
        art_img = images.resolve(img) if images and img else ''
        if images and not art_img:
            art_img = images.resolve_for_path(art_path)
        articles.append(Article(
            title=html.unescape(art_title.strip()),
            desc=html.unescape(art_desc.strip()),
            path=art_path,
            kicker=badge_to_kicker(badge),
            image=art_img,
            cat=rel_url.strip('/').split('/')[0] if rel_url else 'general',
        ))
    apply_reviewers(articles)
    return HubPage(
        cat=cat,
        intro=intro,
        topics=topics,
        articles=articles,
        breadcrumbs=parse_hub_breadcrumbs(html_text),
    )


def nav_is_active(active: str, href: str) -> bool:
    if not active or active in ('/', ''):
        return False
    if active == href:
        return True
    prefix = href.rstrip('/') + '/'
    return active.startswith(prefix)


def parse_categories(html_text: str, images: Optional[ImageRegistry] = None) -> list[Category]:
    cats = []
    for m in re.finditer(
        r'<a href="([^"]+)" class="arc-cat-card"([^>]*)>.*?'
        r'class="arc-cat-title">([^<]*)</div>.*?'
        r'class="arc-cat-meta">\s*([^<]*)',
        html_text,
        re.S,
    ):
        path, attrs, title, meta = m.groups()
        img = ''
        bg = re.search(r"url\(['\"]?([^'\")]+)['\"]?\)", attrs or '', re.I)
        if bg and images:
            img = images.resolve(bg.group(1))
        cats.append(Category(
            title=html.unescape(title.strip()),
            path=path.rstrip('/') + '/' if path else '/',
            meta=html.unescape(meta.strip()),
            image=img,
        ))
    return cats


def parse_article_page(
    path: Path, html_text: str, rel_url: str, images: Optional[ImageRegistry] = None,
) -> Optional[Article]:
    if 'single-post' not in html_text and 'arch-article-body' not in html_text:
        if 'archetype-main' not in html_text:
            return None
    title = extract(r'<h1[^>]*class="[^"]*archetype-entry-headline[^"]*"[^>]*>([^<]+)</h1>', html_text)
    if not title:
        title = extract(r'<title>([^|<]+)', html_text)
    desc = extract(r'<meta name="description" content="([^"]*)"', html_text)
    badge = extract(r'class="arch-content-type-badge[^"]*">\s*([^<]+)', html_text)
    read = extract(r'class="arch-read-time">([^<]+)</div>', html_text)
    body = extract(r'<div class="archetype-content arch-article-body">(.*)</div>\s*<!-- Prev', html_text)
    if not body:
        body = extract(r'<div class="archetype-content arch-article-body">(.*)</div>\s*<div class="arch-article-nav"', html_text)
    hero_img = ''
    feat = re.search(
        r'class="archetype-featured-image-wrap"[\s\S]*?' + IMG_SRC_RE,
        html_text, re.I,
    )
    if feat:
        hero_img = feat.group(1)
    if not hero_img:
        feat2 = re.search(r'class="arch-featured-image"[^>]*\bsrc="([^"]+)"', html_text, re.I)
        if feat2:
            hero_img = feat2.group(1)
    if not hero_img:
        hub = re.search(r'class="arch-hub-article-img"[^>]*\bsrc="([^"]+)"', html_text)
        feed = re.search(r'class="arc-feed-img"[^>]*\bsrc="([^"]+)"', html_text)
        hero_img = (hub or feed).group(1) if (hub or feed) else ''
    if not hero_img:
        hero_img = images.resolve_for_path(rel_url) if images else ''
    if hero_img:
        resolved = images.resolve(hero_img) if images and not hero_img.startswith('/assets/') else hero_img
    elif images:
        resolved = images.resolve_for_path(rel_url)
    else:
        resolved = ''
    return Article(
        title=title,
        desc=desc or (body[:160] + '...' if body else ''),
        path=rel_url,
        kicker=badge_to_kicker(badge),
        time=read or '7 min read',
        badge=badge.strip(),
        cat=rel_url.strip('/').split('/')[0] if rel_url else 'general',
        image=resolved,
    )


def extract_article_body(html_text: str, images: Optional[ImageRegistry] = None) -> str:
    body = extract(r'<div class="archetype-content arch-article-body">(.*)</div>\s*<!-- Prev', html_text)
    if not body:
        body = extract(r'<div class="archetype-content arch-article-body">(.*)</div>\s*<div class="arch-article-nav"', html_text)
    return transform_content(body, images) if body else ''


def extract_toc(html_text: str) -> list[tuple[str, str]]:
    items = re.findall(
        r'<a class="arch-toc-link" href="#([^"]+)">([^<]+)</a>',
        html_text,
    )
    return items


def extract_breadcrumb(html_text: str) -> list[tuple[str, str]]:
    crumbs = []
    for m in re.finditer(r'<nav class="archetype-breadcrumb"[^>]*>(.*?)</nav>', html_text, re.S):
        block = m.group(1)
        for a in re.finditer(r'<a href="([^"]+)">([^<]+)</a>', block):
            crumbs.append((html.unescape(a.group(2).strip()), a.group(1)))
        last = re.search(r'<span>([^<]+)</span>\s*$', block.strip(), re.S)
        if last:
            crumbs.append((html.unescape(last.group(1).strip()), ''))
    return crumbs


def extract_related(html_text: str, images: Optional[ImageRegistry] = None) -> list[tuple[str, str, str]]:
    items = []
    for m in re.finditer(
        r'<div class="archetype-related-item">(.*?</div>)\s*</div>',
        html_text,
        re.S,
    ):
        block = m.group(1)
        link = re.search(r'<a class="archetype-related-title" href="([^"]+)">([^<]+)</a>', block)
        thumb = re.search(r'<img[^>]+src="([^"]+)"', block)
        if link:
            img = images.resolve(thumb.group(1)) if images and thumb else (thumb.group(1) if thumb else '')
            items.append((link.group(2).strip(), link.group(1), img))
    return items[:6]


def brand_slug(name: str) -> str:
    n = name.lower().strip()
    return 'dermat' if 'dermat' in n else n.split()[0][:10]


def backfill_article_images(articles: list[Article], by_path: dict[str, Article], images: ImageRegistry) -> None:
    for a in articles:
        if a.image and a.image.startswith('/assets/'):
            continue
        peer = by_path.get(a.path)
        if peer and peer.image and peer.image.startswith('/assets/'):
            a.image = peer.image
            continue
        if a.image and a.image.startswith('http'):
            a.image = images.resolve(a.image)
            continue
        slug_img = images.resolve_for_path(a.path)
        if not slug_img:
            parts = a.path.strip('/').split('/')
            for end in range(len(parts) - 1, 0, -1):
                parent = '/' + '/'.join(parts[:end]) + '/'
                slug_img = images.resolve_for_path(parent)
                if slug_img:
                    break
        if slug_img:
            a.image = slug_img


def img_for_index(i: int, article_img: str = '', article_path: str = '', images: Optional[ImageRegistry] = None) -> str:
    if article_img and article_img.startswith('/assets/'):
        path = article_img if article_img.startswith('/') else f'/{article_img}'
        return u(path)
    if article_img and article_img.startswith('http') and images:
        resolved = images.resolve(article_img)
        if resolved:
            return u(resolved)
    if images and article_path:
        resolved = images.resolve_for_path(article_path)
        if resolved:
            return u(resolved)
    if article_img:
        path = article_img if article_img.startswith('/') else f'/{article_img}'
        return u(path)
    return u(f'/assets/{ASSET_IMAGES[i % len(ASSET_IMAGES)]}')


def article_thumb(a: Article, i: int, images: Optional[ImageRegistry] = None) -> str:
    return img_for_index(i, a.image, a.path, images)


def head_block(title: str, desc: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(title)}</title>
  <meta name="description" content="{html.escape(desc)}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="stylesheet" href="{u('/assets/pub.css')}">
</head>"""


def shell_header(site: SiteData, active: str = '') -> str:
    brand = brand_slug(site.name)
    cat_nav = ''.join(
        f'<a class="pub-nav__link{" is-active" if nav_is_active(active, h) else ""}" href="{html.escape(u(h))}">{html.escape(lbl)}</a>'
        for lbl, h in PRIMARY_NAV
    )
    home_active = ' is-active' if active in ('/', '') else ''
    return f"""
<body class="pub-site">
<div class="pub-progress" id="pub-progress"></div>
<div class="pub-trust-bar pub-container">100+ Medical Experts · Fact-Checked Content · Updated {datetime.now().strftime("%B %Y")}</div>
<header class="pub-header">
  <div class="pub-container">
    <div class="pub-header__top">
      <a class="pub-logo" href="{u('/')}">{html.escape(brand)}</a>
      <div class="pub-header__actions">
        <input type="search" class="pub-search" placeholder="Search topics…" aria-label="Search">
        <a class="pub-sign-in" href="{u('/contact/')}">Sign in</a>
        <button class="pub-btn pub-btn--primary" type="button">Subscribe</button>
        <button class="pub-nav-toggle" type="button" data-pub-nav-toggle aria-expanded="false" aria-label="Menu">
          <span></span><span></span><span></span>
        </button>
      </div>
    </div>
    <nav class="pub-nav" aria-label="Main">
      <div class="pub-nav__inner">
        <a class="pub-nav__link{home_active}" href="{u('/')}">Home</a>
        {cat_nav}
      </div>
    </nav>
  </div>
</header>"""


def shell_footer(site: SiteData) -> str:
    cols = ''
    for title, links in site.footer_cols[:3]:
        links_html = ''.join(f'<a href="{html.escape(u(href))}">{html.escape(lbl)}</a>' for href, lbl in links[:6])
        cols += f'<div class="pub-footer__col"><h4>{html.escape(title)}</h4>{links_html}</div>'
    return f"""
<footer class="pub-footer">
  <div class="pub-container pub-footer__grid">
    <div class="pub-footer__brand">
      <span class="pub-logo">{html.escape(brand_slug(site.name))}</span>
      <p class="pub-footer__tagline">{html.escape(site.tagline)}</p>
    </div>
    {cols}
  </div>
  <div class="pub-container pub-footer__bar">© {datetime.now().year} {html.escape(site.name)}. All rights reserved. For informational purposes only.</div>
</footer>
<script src="{u('/assets/pub.js')}"></script>
<script>
(function(){{
  var p=document.getElementById('pub-progress');
  if(!p)return;
  window.addEventListener('scroll',function(){{
    var h=document.documentElement.scrollHeight-window.innerHeight;
    p.style.width=(h>0?(window.scrollY/h)*100:0)+'%';
  }},{{passive:true}});
}})();
</script>
</body></html>"""


def trending_strip(articles: list[Article]) -> str:
    items = ''.join(
        f'<a href="{html.escape(u(a.path))}">{html.escape(a.title)}</a>'
        f'<span class="pub-trending__dot" aria-hidden="true">•</span>'
        for a in articles[:12]
    )
    return f"""
<section class="pub-trending"><div class="pub-container pub-trending__inner">
  <span class="pub-trending__label">Trending Now</span>
  <div class="pub-trending__viewport">
    <div class="pub-trending__marquee">
      <div class="pub-trending__content">{items}</div>
      <div class="pub-trending__content" aria-hidden="true">{items}</div>
    </div>
  </div>
</div></section>"""


def collect_browse_links(
    hub: Optional[HubPage], articles: list[Article], hub_path: str, limit: int = 8,
) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(title: str, path: str) -> None:
        if len(links) >= limit or path in seen or path == hub_path:
            return
        if not path.startswith(hub_path):
            return
        seen.add(path)
        links.append((title, path))

    if hub:
        for topic in hub.topics:
            add(topic.title, topic.path)
        for art in hub.articles:
            add(art.title, art.path)
        for topic in hub.topics:
            for art in topic.articles:
                add(art.title, art.path)
    for art in articles:
        add(art.title, art.path)
    return links[:limit]


def collect_atoz_links(
    hub_by_path: dict[str, HubPage], articles: list[Article],
) -> list[tuple[str, str]]:
    """All hub topics + articles with content, sorted A–Z."""
    links: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(title: str, path: str) -> None:
        if not title.strip() or path in seen:
            return
        seen.add(path)
        links.append((title.strip(), path if path.endswith('/') else path + '/'))

    hub_paths = set(hub_by_path.keys())
    for hub in hub_by_path.values():
        add(hub.cat.title, hub.cat.path)
    for art in articles:
        if art.path not in hub_paths:
            add(art.title, art.path)

    links.sort(key=lambda x: x[0].lower())
    return links


def browse_grid_html(links: list[tuple[str, str]]) -> str:
    if not links:
        return ''
    ncols = min(4, max(2, (len(links) + 1) // 2))
    per_col = -(-len(links) // ncols)
    cols: list[str] = []
    for col in range(ncols):
        chunk = links[col * per_col:(col + 1) * per_col]
        if not chunk:
            continue
        items = ''.join(
            f'<a href="{html.escape(u(href))}" class="pub-browse__link">'
            f'<span class="pub-browse__arrow" aria-hidden="true">→</span>'
            f'{html.escape(title)}</a>'
            for title, href in chunk
        )
        cols.append(f'<div class="pub-browse__col">{items}</div>')
    return ''.join(cols)


def youtube_thumb_url(video_id: str) -> str:
    return f'https://img.youtube.com/vi/{video_id}/hqdefault.jpg'


def youtube_embed_html(video_id: str, title: str) -> str:
    return (
        f'<figure class="pub-article-hero pub-video-embed">'
        f'<iframe src="https://www.youtube-nocookie.com/embed/{html.escape(video_id)}?rel=0"'
        f' title="{html.escape(title)}"'
        f' allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"'
        f' allowfullscreen loading="lazy"></iframe></figure>'
    )


def video_play_icon() -> str:
    return (
        '<span class="pub-video-play" aria-hidden="true">'
        '<svg viewBox="0 0 24 24" width="12" height="12" focusable="false">'
        '<path fill="currentColor" d="M8 5v14l11-7z"/></svg></span>'
    )


def video_spotlight_title(entry: VideoSpotlight, articles_by_path: dict[str, Article]) -> str:
    if entry.label:
        return entry.label
    art = articles_by_path.get(entry.article_path)
    return art.title if art else entry.article_path.strip('/').split('/')[-1].replace('-', ' ').title()


def render_video_spotlight(site: SiteData) -> str:
    if not VIDEO_SPOTLIGHT:
        return ''
    articles_by_path = {a.path: a for a in site.articles}
    featured, *rest = VIDEO_SPOTLIGHT
    feat_title = video_spotlight_title(featured, articles_by_path)
    feat_href = html.escape(u(featured.article_path))
    feat_thumb = html.escape(youtube_thumb_url(featured.youtube_id))
    featured_html = f"""<a href="{feat_href}" class="pub-video-spotlight__featured">
  <div class="pub-video-spotlight__thumb pub-video-spotlight__thumb--lg">
    <img src="{feat_thumb}" alt="" loading="lazy">{video_play_icon()}
  </div>
  <h3 class="pub-video-spotlight__feat-title">{html.escape(feat_title)}</h3>
</a>"""
    list_html = ''
    for entry in rest[:4]:
        title = video_spotlight_title(entry, articles_by_path)
        href = html.escape(u(entry.article_path))
        thumb = html.escape(youtube_thumb_url(entry.youtube_id))
        list_html += f"""<a href="{href}" class="pub-video-spotlight__item">
  <div class="pub-video-spotlight__thumb">
    <img src="{thumb}" alt="" loading="lazy">{video_play_icon()}
  </div>
  <span class="pub-video-spotlight__item-title">{html.escape(title)}</span>
</a>"""
    return f"""<section class="pub-video-spotlight">
  <div class="pub-container">
    <div class="pub-video-spotlight__header">
      <h2 class="pub-video-spotlight__heading">Video Spotlight</h2>
      <a class="pub-video-spotlight__viewall" href="{html.escape(u('/skin-conditions/'))}">View All</a>
    </div>
    <div class="pub-video-spotlight__grid">
      {featured_html}
      <div class="pub-video-spotlight__list">{list_html}</div>
    </div>
  </div>
</section>"""


def render_browse_sections(site: SiteData, hub_by_path: dict[str, HubPage]) -> str:
    blocks: list[str] = []
    for title, hub_path in BROWSE_SECTIONS:
        hub = hub_by_path.get(hub_path)
        links = collect_browse_links(hub, site.articles, hub_path)
        if not links:
            continue
        grid = browse_grid_html(links)
        blocks.append(
            f'<section class="pub-browse-block"><div class="pub-container">'
            f'<div class="pub-browse__header">'
            f'<h2 class="pub-browse__title">{html.escape(title.upper())}</h2>'
            f'<a class="pub-browse__viewall" href="{html.escape(u(hub_path))}">View All</a>'
            f'</div>'
            f'<div class="pub-browse__panel"><div class="pub-browse__grid">{grid}</div></div>'
            f'</div></section>'
        )
    return ''.join(blocks)


def render_dermat_atoz(site: SiteData, hub_by_path: dict[str, HubPage]) -> str:
    links = collect_atoz_links(hub_by_path, site.articles)
    if not links:
        return ''
    grid = browse_grid_html(links)
    return (
        f'<section class="pub-browse-block pub-atoz-block"><div class="pub-container">'
        f'<div class="pub-browse__header">'
        f'<h2 class="pub-browse__title">Dermat A - Z</h2>'
        f'<a class="pub-browse__viewall" href="{html.escape(u("/skin-conditions/"))}">View All</a>'
        f'</div>'
        f'<div class="pub-browse__panel"><div class="pub-browse__grid">{grid}</div></div>'
        f'</div></section>'
    )


def card_featured(a: Article, i: int) -> str:
    img = article_thumb(a, i)
    return f"""<a href="{html.escape(u(a.path))}" class="pub-card pub-card--featured">
  <img class="pub-card__img" src="{html.escape(img)}" alt="" loading="lazy">
  <div class="pub-card__body">
    <span class="pub-card__kicker">{html.escape(a.kicker)}</span>
    <h3 class="pub-card__title">{html.escape(a.title)}</h3>
    <p class="pub-card__desc">{html.escape(a.desc[:140])}</p>
    <div class="pub-card__meta">{html.escape(a.time)} · {html.escape(a.author)}</div>
  </div>
</a>"""


def card_compact(a: Article, i: int) -> str:
    img = article_thumb(a, i + 3)
    return f"""<a href="{html.escape(u(a.path))}" class="pub-card pub-card--compact">
  <img class="pub-card__img" src="{html.escape(img)}" alt="" loading="lazy">
  <div><span class="pub-card__kicker">{html.escape(a.kicker)}</span>
  <h4 class="pub-card__title">{html.escape(a.title)}</h4></div>
</a>"""


def card_tile(a: Article, i: int, *, hero: bool = False) -> str:
    img = article_thumb(a, i)
    body = f'<h4 class="pub-card__title">{html.escape(a.title)}</h4>'
    if hero:
        body = (
            f'<span class="pub-card__kicker">{html.escape(a.kicker)}</span>'
            f'<h4 class="pub-card__title">{html.escape(a.title)}</h4>'
            f'<div class="pub-card__meta">{html.escape(a.time)} · {html.escape(a.author)}</div>'
        )
    return f"""<a href="{html.escape(u(a.path))}" class="pub-card pub-card--tile{" pub-card--tile-hero" if hero else ""}">
  <img class="pub-card__img" src="{html.escape(img)}" alt="" loading="lazy">
  <div class="pub-card__body">{body}</div>
</a>"""


def rail_spotlight(articles: list[Article], reverse: bool = False) -> str:
    if not articles:
        return ''
    rev = ' pub-rail--reverse' if reverse else ''
    featured = articles[0]
    rest = articles[1:5]
    list_html = ''.join(card_compact(a, i) for i, a in enumerate(rest))
    return f"""<div class="pub-rail pub-rail--spotlight{rev}">
  <div class="pub-rail__featured">{card_featured(featured, 0)}</div>
  <div class="pub-rail__list">{list_html}</div>
</div>"""


def rail_mosaic(articles: list[Article]) -> str:
    tiles = ''.join(card_tile(a, i) for i, a in enumerate(articles[:10]))
    return f'<div class="pub-rail pub-rail--mosaic"><div class="pub-tile-grid">{tiles}</div></div>'


def rail_digest(articles: list[Article]) -> str:
    feat = ''.join(card_featured(a, i) for i, a in enumerate(articles[:2]))
    headlines = ''.join(
        f'<a href="{html.escape(u(a.path))}" class="pub-card pub-card--headline"><div class="pub-card__body">'
        f'<span class="pub-card__kicker">{html.escape(a.kicker)}</span>'
        f'<h4 class="pub-card__title">{html.escape(a.title)}</h4></div></a>'
        for a in articles[2:5]
    )
    return f"""<div class="pub-rail pub-rail--digest">
  <div class="pub-digest__featured">{feat}</div>
  <div class="pub-digest__headlines">{headlines}</div>
</div>"""


def category_rail(section_title: str, articles: list[Article], idx: int, more_href: str) -> str:
    variant = idx % 4
    if variant == 0:
        body = rail_spotlight(articles)
    elif variant == 1:
        body = rail_mosaic(articles)
    elif variant == 2:
        body = rail_digest(articles)
    else:
        body = rail_spotlight(articles, reverse=True)
    return f"""
<section class="pub-section{" pub-section--alt" if idx % 2 else ""}" id="cat-{slugify(section_title)}">
  <div class="pub-container">
    <div class="pub-section__header">
      <h2 class="pub-section__title">{html.escape(section_title)}</h2>
      <a class="pub-section__more" href="{html.escape(u(more_href))}">View all →</a>
    </div>
    {body}
  </div>
</section>"""


def render_homepage(site: SiteData, hub_by_path: Optional[dict[str, HubPage]] = None) -> str:
    arts = site.articles
    if len(arts) < 12:
        arts = arts + arts  # cycle
    lead = arts[0]
    side = arts[1:5]
    hero = f"""
<section class="pub-hero"><div class="pub-container pub-hero__grid">
  <a href="{html.escape(u(lead.path))}" class="pub-hero__lead">
    <img src="{html.escape(img_for_index(0, lead.image))}" alt="">
    <div class="pub-hero__lead-overlay">
      <span class="pub-hero__kicker">Featured · {html.escape(lead.kicker)}</span>
      <h2>{html.escape(lead.title)}</h2>
      <p>{html.escape(lead.desc[:120])}</p>
      <div class="pub-hero__meta">{html.escape(lead.time)} · {html.escape(lead.author)}</div>
    </div>
  </a>
  <div class="pub-hero__side">{''.join(card_tile(a, i+1, hero=True) for i, a in enumerate(side))}</div>
</div></section>"""

    quick = ''.join(
        f'<a href="{html.escape(u(a.path))}" class="pub-quick-hit"><div class="pub-quick-hit__kicker">{html.escape(a.kicker)}</div>'
        f'<div class="pub-quick-hit__title">{html.escape(a.title[:50])}</div></a>'
        for a in arts[5:11]
    )

    rails = ''
    cat_groups: dict[str, list[Article]] = {}
    for a in arts:
        cat_groups.setdefault(a.cat, []).append(a)
    if not cat_groups:
        cat_groups = {'skin-care': arts}

    cat_by_path = {c.path: c for c in (site.categories or [])}
    idx = 0
    extra = ''
    for nav_label, hub_path in PRIMARY_NAV:
        cat_slug = hub_path.strip('/').split('/')[0]
        group = cat_groups.get(cat_slug, [])
        if not group:
            continue
        rails += category_rail(nav_label, group[:8], idx, hub_path)
        if idx == 1:
            cards = ''.join(
                f'<a href="{html.escape(u(path))}" class="pub-explore__card">'
                f'<img src="{html.escape(u(cat_by_path[path].image) if path in cat_by_path and cat_by_path[path].image else img_for_index(i))}" alt="">'
                f'<span class="pub-explore__label">{html.escape(lbl)}</span></a>'
                for i, (lbl, path) in enumerate(PRIMARY_NAV)
            )
            extra += (
                '<section class="pub-section"><div class="pub-container">'
                '<h2 class="pub-section__title">Explore Topics</h2>'
                f'<div class="pub-explore__track">{cards}</div></div></section>'
            )
        if idx == 3:
            spec = ''.join(card_featured(a, i) for i, a in enumerate(arts[12:15]))
            extra += (
                '<div class="pub-container"><div class="pub-special">'
                '<h2 class="pub-section__title">Special Features</h2>'
                f'<div class="pub-special__grid">{spec}</div></div></div>'
            )
        if idx == 4:
            tags = ''.join(
                f'<a href="{html.escape(u(path))}" class="pub-tag">{html.escape(lbl)}</a>'
                for lbl, path in PRIMARY_NAV
            )
            extra += (
                '<section class="pub-section pub-section--alt"><div class="pub-container">'
                '<h2 class="pub-section__title">Trending Topics</h2>'
                f'<div class="pub-tags">{tags}</div></div></section>'
            )
        rails += extra
        extra = ''
        idx += 1

    editors = ''.join(card_featured(a, i) for i, a in enumerate(arts[15:18]))
    ranked_l = ''.join(
        f'<div class="pub-ranked__item"><span class="pub-ranked__num">{i+1}</span>'
        f'<a href="{html.escape(u(a.path))}" class="pub-ranked__title">{html.escape(a.title)}</a></div>'
        for i, a in enumerate(arts[18:28])
    )
    ranked_r = ''.join(
        f'<div class="pub-ranked__item"><span class="pub-ranked__num">{i+1}</span>'
        f'<a href="{html.escape(u(a.path))}" class="pub-ranked__title">{html.escape(a.title)}</a></div>'
        for i, a in enumerate(arts[28:38])
    )
    experts = ''.join(
        f'<div class="pub-expert"><img src="{u(f"/assets/expert-{i+1}.jpg")}" alt=""><div class="pub-expert__name">Dr. {["Sarah Chen","James Okonkwo","Maria Santos","David Kim"][i]}</div>'
        f'<div class="pub-expert__cred">{["Board-Certified Dermatologist","Clinical Researcher","PharmD, Skincare Specialist","MD, Cosmetic Dermatology"][i]}</div></div>'
        for i in range(4)
    )

    browse = render_browse_sections(site, hub_by_path or {}) if hub_by_path else ''
    atoz = render_dermat_atoz(site, hub_by_path or {}) if hub_by_path else ''

    return (
        head_block(f'{site.name} — Health & Wellness', site.tagline)
        + shell_header(site, '/')
        + trending_strip(arts)
        + hero
        + f'<section class="pub-quick-hits"><div class="pub-container pub-quick-hits__grid">{quick}</div></section>'
        + browse
        + atoz
        + render_video_spotlight(site)
        + rails
        + f'<section class="pub-container"><div class="pub-editors"><h2 class="pub-section__title">Editor\'s Picks</h2><div class="pub-editors__grid">{editors}</div></div></section>'
        + f'<section class="pub-section"><div class="pub-container pub-ranked"><div class="pub-ranked__col"><h3>Most Read</h3>{ranked_l}</div><div class="pub-ranked__col"><h3>Latest</h3>{ranked_r}</div></div></section>'
        + f'<section class="pub-section pub-section--alt"><div class="pub-container"><h2 class="pub-section__title">Medical Review Board</h2><div class="pub-experts">{experts}</div></div></section>'
        + f"""<section class="pub-container"><div class="pub-newsletter">
      <h2>Stay informed</h2><p>Weekly dermatology tips, reviewed by experts.</p>
      <form class="pub-newsletter__form" onsubmit="return false">
        <input type="email" placeholder="Your email" aria-label="Email">
        <button class="pub-btn pub-btn--primary" type="submit">Subscribe</button>
      </form></div></section>"""
        + shell_footer(site)
    )


def hub_breadcrumb_html(crumbs: list[tuple[str, str]], fallback_title: str) -> str:
    if not crumbs:
        return f'<a href="{u("/")}">Home</a><span>/</span><span>{html.escape(fallback_title)}</span>'
    parts: list[str] = []
    for lbl, href in crumbs:
        if href and href not in ('', '/home'):
            parts.append(f'<a href="{html.escape(u(href))}">{html.escape(lbl)}</a>')
        elif href == '/':
            parts.append(f'<a href="{u("/")}">Home</a>')
        else:
            parts.append(f'<span>{html.escape(lbl)}</span>')
        parts.append('<span>/</span>')
    if parts and parts[-1] == '<span>/</span>':
        parts.pop()
    return ''.join(parts)


def hub_topic_section(topic: HubTopic, idx: int) -> str:
    img = u(topic.image) if topic.image else img_for_index(idx)
    art_cards = ''.join(hub_article_card(a, i) for i, a in enumerate(topic.articles[:6]))
    arts_block = ''
    if art_cards:
        arts_block = f'<div class="pub-hub-topic-articles">{art_cards}</div>'
    return f"""<section class="pub-hub-topic-block" id="topic-{hub_topic_slug(topic)}">
  <a href="{html.escape(u(topic.path))}" class="pub-hub-topic-banner">
    <img class="pub-hub-topic-banner__img" src="{html.escape(img)}" alt="" loading="lazy">
    <div class="pub-hub-topic-banner__overlay">
      <h3>{html.escape(topic.title)}</h3>
      <p>{html.escape(topic.desc)}</p>
      <span class="pub-hub-topic-banner__cta">View all →</span>
    </div>
  </a>
  {arts_block}
</section>"""


def hub_article_card(a: Article, i: int) -> str:
    img = article_thumb(a, i)
    return f"""<a href="{html.escape(u(a.path))}" class="pub-hub-article">
  <img class="pub-hub-article__img" src="{html.escape(img)}" alt="" loading="lazy">
  <div class="pub-hub-article__body">
    <span class="pub-card__kicker">{html.escape(a.kicker)}</span>
    <h3>{html.escape(a.title)}</h3>
    <p>{html.escape(a.desc[:160])}</p>
    <div class="pub-hub-article__meta">{html.escape(a.time)} · {html.escape(a.author)}</div>
    <span class="pub-hub-article__read">Read article →</span>
  </div>
</a>"""


def render_category_hub(site: SiteData, hub: HubPage) -> str:
    cat = hub.cat
    pills = ''.join(
        f'<a href="#topic-{hub_topic_slug(t)}" class="pub-topic-pill">{html.escape(t.title)}</a>'
        for t in hub.topics
    )
    main_parts: list[str] = []
    if hub.intro:
        main_parts.append(f'<div class="pub-hub-intro pub-prose">{hub.intro}</div>')
    if hub.topics:
        topic_sections = ''.join(hub_topic_section(t, i) for i, t in enumerate(hub.topics))
        main_parts.append(
            f'<div class="pub-hub-topic-stack">{topic_sections}</div>'
        )
    if hub.articles:
        art_cards = ''.join(hub_article_card(a, i) for i, a in enumerate(hub.articles))
        main_parts.append(
            f'<section class="pub-hub-articles"><h2 class="pub-section__title">Articles</h2>'
            f'<div class="pub-hub-article-grid">{art_cards}</div></section>'
        )
    main_html = ''.join(main_parts) or '<p class="pub-hub-empty">More guides coming soon.</p>'

    popular_arts: list[Article] = list(hub.articles)
    for t in hub.topics:
        popular_arts.extend(t.articles)
    popular = ''.join(
        f'<a href="{html.escape(u(a.path))}">{html.escape(a.title)}</a>'
        for a in popular_arts[:8]
    )
    crumb_html = hub_breadcrumb_html(hub.breadcrumbs, cat.title)
    topic_count = len(hub.topics)
    art_count = len(popular_arts)
    meta_bits = []
    if topic_count:
        meta_bits.append(f'{topic_count} topic{"s" if topic_count != 1 else ""}')
    if art_count:
        meta_bits.append(f'{art_count} article{"s" if art_count != 1 else ""}')
    meta_line = ' · '.join(meta_bits) if meta_bits else cat.meta

    hero_img = u(cat.image) if cat.image else ''
    hero_banner = ''
    if hero_img:
        hero_banner = f"""<div class="pub-hub-hero-banner">
      <img src="{html.escape(hero_img)}" alt="">
      <div class="pub-hub-hero-banner__overlay"></div>
    </div>"""

    return (
        head_block(f'{cat.title} | {site.name}', cat.meta or f'Expert guides on {cat.title.lower()}.')
        + shell_header(site, cat.path)
        + hero_banner
        + f"""<div class="pub-container pub-hub-hero">
      <nav class="pub-breadcrumb">{crumb_html}</nav>
      <h1>{html.escape(cat.title)}</h1>
      <p class="pub-hub-hero__desc">{html.escape(meta_line if meta_bits else (cat.meta or site.tagline))}</p>
      {f'<div class="pub-topic-pills">{pills}</div>' if pills else ''}
    </div>
    <div class="pub-container pub-hub-layout">
      <main>{main_html}</main>
      <aside class="pub-sidebar pub-sidebar--sticky">
        <div class="pub-sidebar-card"><h4>Popular in {html.escape(cat.title)}</h4>{popular or '<span style="font-size:0.8125rem;color:var(--pub-muted)">Browse topics above.</span>'}</div>
        <div class="pub-sidebar-card"><h4>Newsletter</h4><p style="font-size:0.875rem;color:var(--pub-muted)">Get weekly tips.</p>
        <button class="pub-btn pub-btn--primary" type="button" style="width:100%;margin-top:12px">Subscribe</button></div>
      </aside>
    </div>"""
        + shell_footer(site)
    )


def render_article(site: SiteData, article: Article, body: str, toc: list[tuple[str, str]], crumbs: list, related: list) -> str:
    crumb_html = f'<a href="{u("/")}">Home</a>'
    seen_crumbs: set[tuple[str, str]] = {('home', '/')}
    for lbl, href in crumbs:
        key = (lbl.lower().strip(), href or '')
        if key in seen_crumbs:
            continue
        seen_crumbs.add(key)
        if href and href != '/':
            crumb_html += f'<span>/</span><a href="{html.escape(u(href))}">{html.escape(lbl)}</a>'
        elif not href:
            crumb_html += f'<span>/</span><span>{html.escape(lbl)}</span>'

    toc_html = ''.join(
        f'<a href="#{html.escape(sid)}">{html.escape(lbl)}</a>' for sid, lbl in toc
    )
    if not toc_html:
        for m in re.finditer(r'<h2 id="([^"]+)">([^<]+)</h2>', body):
            toc_html += f'<a href="#{m.group(1)}">{html.escape(m.group(2))}</a>'

    takeaways = ''
    first_p = extract(r'<p>([^<]{40,200})</p>', body)
    if first_p:
        takeaways = f"""<div class="pub-takeaways"><h3>Key Takeaways</h3><ul><li>{html.escape(first_p[:120])}…</li>
        <li>Medically reviewed guidance for informed skincare decisions.</li></ul></div>"""

    rel_html = ''.join(
        card_featured(Article(t, '', u(h), 'Related', image=img or ''), i)
        for i, (t, h, img) in enumerate(related[:3])
    )

    return (
        head_block(f'{article.title} | {site.name}', article.desc)
        + shell_header(site)
        + f"""<div class="pub-container pub-article-wrap">
      <article class="pub-article-main">
        <nav class="pub-breadcrumb">{crumb_html}</nav>
        <header class="pub-article-header">
          <span class="pub-card__kicker">{html.escape(article.kicker)}</span>
          <h1>{html.escape(article.title)}</h1>
          <div class="pub-article-meta">
            <span>{html.escape(article.time)}</span>
            <span>·</span>
            <span>{html.escape(article.author)}</span>
            <span>·</span>
            <span>Updated {datetime.now().strftime("%b %Y")}</span>
          </div>
          <div class="pub-badges">
            <span class="pub-badge">Medically Reviewed</span>
            <span class="pub-badge">Fact-checked</span>
          </div>
          {takeaways}
        </header>
        {youtube_embed_html(VIDEO_BY_PATH[article.path], article.title) if article.path in VIDEO_BY_PATH else (f'<figure class="pub-article-hero"><img src="{html.escape(u(article.image) if article.image.startswith("/") else img_for_index(0, article.image))}" alt="{html.escape(article.title)}" loading="eager"></figure>' if article.image else '')}
        <div class="pub-share">
          <button type="button" data-pub-copy-link>Copy link</button>
        </div>
        <div class="pub-article-body pub-prose">{body}</div>
        <div class="pub-author-bio">
          <img src="{u(f'/assets/{article.author_img or "author.jpg"}')}" alt="">
          <div><strong>{html.escape(article.author)}</strong>
          <p style="margin:4px 0 0;font-size:0.8125rem;color:var(--pub-accent);font-weight:600">{html.escape(article.author_cred)}</p>
          <p style="margin:8px 0 0;font-size:0.9375rem;color:var(--pub-muted)">Medically reviewed content from board-certified specialists.</p></div>
        </div>
        <section class="pub-related"><h2>Related Reading</h2><div class="pub-related__grid">{rel_html}</div></section>
      </article>
      <aside class="pub-sidebar pub-sidebar--sticky">
        <div class="pub-sidebar-card"><h4>On this page</h4><nav class="pub-toc-vertical">{toc_html}</nav></div>
        <div class="pub-sidebar-card"><h4>Popular</h4>
          {''.join(f'<a href="{html.escape(u(a.path))}">{html.escape(a.title[:60])}</a>' for a in site.articles[:5])}
        </div>
        <div class="pub-sidebar-card"><h4>Newsletter</h4>
          <button class="pub-btn pub-btn--primary" type="button" style="width:100%">Subscribe</button>
        </div>
      </aside>
    </div>"""
        + shell_footer(site)
    )


def scan_site(raw_dir: Path, images: Optional[ImageRegistry] = None) -> SiteData:
    site = SiteData()
    seen_paths: set[str] = set()
    article_bodies: dict[str, tuple[str, list, list, list]] = {}

    html_files = sorted(raw_dir.rglob('index.html'))
    home_html = ''
    for fp in html_files:
        parent_rel = fp.parent.relative_to(raw_dir)
        if str(parent_rel) == '.':
            rel = '/'
        else:
            rel = '/' + str(parent_rel).replace('\\', '/') + '/'

        text = fp.read_text(encoding='utf-8', errors='replace')
        if rel == '/' or 'arch-site home' in text:
            home_html = text

        if images:
            images.ingest_html(text)

        art = parse_article_page(fp, text, rel, images)
        if art and rel not in seen_paths:
            site.articles.append(art)
            seen_paths.add(rel)
            article_bodies[rel] = (
                extract_article_body(text, images),
                extract_toc(text),
                extract_breadcrumb(text),
                extract_related(text, images),
            )

    if home_html:
        site.name = extract(r'class="arch-nav-brand"[^>]*>([^<]+)</a>', home_html) or extract(r'<title>([^|<]+)', home_html) or site.name
        site.tagline = extract(r'class="arch-footer-tagline">([^<]+)</p>', home_html) or site.tagline
        site.nav = PRIMARY_NAV
        site.footer_cols = parse_footer(home_html)
        site.categories = parse_categories(home_html, images)
        for a in parse_feed_cards(home_html, images):
            if a.path not in seen_paths:
                site.articles.insert(0, a)
                seen_paths.add(a.path)

    # Dedupe articles by path
    by_path: dict[str, Article] = {}
    for a in site.articles:
        by_path[a.path] = a
    site.articles = list(by_path.values())
    apply_reviewers(site.articles)
    site._article_bodies = article_bodies  # type: ignore
    return site


def ensure_theme_assets() -> list[Path]:
    shared = TRAIL_DIR / 'shared' / 'assets'
    if not shared.exists() or len(list(shared.glob('*.jpg'))) < 5:
        import generate_assets
        generate_assets.main()
    return sorted(shared.glob('*.jpg'))


def build(raw_dir: Path, out_dir: Path, fetch_remote: bool = False, base_url: str = '') -> None:
    global BASE_URL
    BASE_URL = (base_url or '').rstrip('/')
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    assets_out = out_dir / 'assets'
    assets_out.mkdir()
    shutil.copy(TRAIL_DIR / 'pub.css', assets_out / 'pub.css')
    shutil.copy(TRAIL_DIR / 'pub.js', assets_out / 'pub.js')
    placeholders = ensure_theme_assets()
    for f in placeholders:
        shutil.copy(f, assets_out / f.name)

    images_source = raw_dir.parent / 'images'
    if not images_source.is_dir():
        images_source = None
    images = ImageRegistry(
        assets_out / 'media',
        placeholders,
        fetch_remote=fetch_remote,
        images_source=images_source,
    )
    if images_source:
        print(f'  Using local images: {images_source} ({len(images._basename_index)} files)')
    for fp in raw_dir.rglob('index.html'):
        images.ingest_html(fp.read_text(encoding='utf-8', errors='replace'))

    site = scan_site(raw_dir, images)
    bodies: dict = getattr(site, '_article_bodies', {})

    # Category hubs
    cat_articles: dict[str, list[Article]] = {}
    for a in site.articles:
        cat_articles.setdefault(a.cat, []).append(a)

    top_category_paths = {c.path for c in site.categories}
    hub_by_path: dict[str, HubPage] = {}

    for cat in site.categories:
        raw_fp = raw_dir / cat.path.strip('/') / 'index.html'
        if raw_fp.is_file():
            hub = parse_hub_page(raw_fp.read_text(encoding='utf-8', errors='replace'), cat.path, images)
            if not hub.cat.image and cat.image:
                hub.cat.image = cat.image
        else:
            slug = cat.path.strip('/').split('/')[0]
            arts = cat_articles.get(slug, [x for x in site.articles if x.path.startswith(cat.path)])
            hub = HubPage(cat=cat, articles=arts[:20])
        hub_by_path[cat.path] = hub

    for fp in raw_dir.rglob('index.html'):
        parent_rel = fp.parent.relative_to(raw_dir)
        if str(parent_rel) == '.':
            continue
        rel = '/' + str(parent_rel).replace('\\', '/') + '/'
        if rel in top_category_paths or rel in bodies:
            continue
        text = fp.read_text(encoding='utf-8', errors='replace')
        if 'arch-hub-page' not in text:
            continue
        hub = parse_hub_page(text, rel, images)
        if not hub.articles:
            hub.articles = direct_child_articles(rel, site.articles)
            apply_reviewers(hub.articles)
        hub_by_path[rel] = hub

    by_path = {a.path: a for a in site.articles}
    backfill_article_images(site.articles, by_path, images)

    for rel in sorted(hub_by_path.keys(), key=lambda p: p.count('/'), reverse=True):
        enrich_hub(hub_by_path[rel], site, hub_by_path, images)

    for hub in hub_by_path.values():
        backfill_article_images(hub.articles, by_path, images)
        for topic in hub.topics:
            backfill_article_images(topic.articles, by_path, images)

    # Homepage (after hubs enriched for browse grids)
    (out_dir / 'index.html').write_text(render_homepage(site, hub_by_path), encoding='utf-8')

    for rel, hub in hub_by_path.items():
        parts = rel.strip('/').split('/')
        out_path = out_dir.joinpath(*parts) if parts != [''] else out_dir
        out_path.mkdir(parents=True, exist_ok=True)
        (out_path / 'index.html').write_text(render_category_hub(site, hub), encoding='utf-8')

    # Articles
    for rel, art in {a.path: a for a in site.articles}.items():
        body, toc, crumbs, related = bodies.get(rel, ('', [], [], []))
        if not body:
            continue
        parts = rel.strip('/').split('/')
        out_path = out_dir.joinpath(*parts)
        out_path.mkdir(parents=True, exist_ok=True)
        (out_path / 'index.html').write_text(
            render_article(site, art, body, toc, crumbs, related),
            encoding='utf-8',
        )

    # Policy / about pages — simple article shell
    for fp in raw_dir.rglob('index.html'):
        rel = '/' + str(fp.parent.relative_to(raw_dir)).replace('\\', '/')
        if rel in ('/', '/.') or rel.endswith('//'):
            continue
        rel = rel if rel.endswith('/') else rel + '/'
        if rel in bodies or rel in top_category_paths:
            continue
        if (out_dir / rel.strip('/')).exists():
            continue
        text = fp.read_text(encoding='utf-8', errors='replace')
        if 'arch-article-body' not in text and 'archetype-main' not in text:
            title = extract(r'<title>([^<]+)</title>', text) or 'Page'
            main = extract(r'<div class="arch-page-wrapper">(.*)</div>\s*<div class="arch-footer', text)
            if main:
                art = Article(title=title.split('|')[0].strip(), desc='', path=rel)
                parts = rel.strip('/').split('/')
                if parts and parts != ['']:
                    out_path = out_dir.joinpath(*parts)
                    out_path.mkdir(parents=True, exist_ok=True)
                    (out_path / 'index.html').write_text(
                        render_article(site, art, transform_content(main, images), [], [('Home', '/')], []),
                        encoding='utf-8',
                    )

    (out_dir / '.nojekyll').touch(exist_ok=True)

    n_media = len(list((assets_out / 'media').glob('*')))
    print(f'Built {len(list(out_dir.rglob("index.html")))} pages → {out_dir}')
    print(f'  Theme placeholders: {len(placeholders)} · Cached images: {n_media}')


def main() -> None:
    ap = argparse.ArgumentParser(description='Apply HEA-001 Trail 5 theme to Archetype site export')
    ap.add_argument('--site', type=Path, required=True, help='Path to raw Archetype export folder')
    ap.add_argument('--out', type=Path, help='Output directory (default: <site>-pub next to raw)')
    ap.add_argument(
        '--fetch-images',
        action='store_true',
        help='Try downloading images from WordPress (dermat.local). Requires local WP running.',
    )
    ap.add_argument(
        '--base-url',
        default='',
        help='URL prefix for hosting (e.g. /nexus-site-builder for GitHub project Pages)',
    )
    args = ap.parse_args()
    raw = args.site.resolve()
    if not raw.is_dir():
        raise SystemExit(f'Not a directory: {raw}')
    out = args.out or raw.parent / f'{raw.name}-pub'
    build(raw, out.resolve(), fetch_remote=args.fetch_images, base_url=args.base_url)


if __name__ == '__main__':
    main()
