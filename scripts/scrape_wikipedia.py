#!/usr/bin/env python3
"""Scrape Wikipedia pages and save as clean, self-contained HTML with dark theme."""

import os
import time
import requests
from bs4 import BeautifulSoup

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'content', 'library', 'wikipedia')
os.makedirs(OUTPUT_DIR, exist_ok=True)

DARK_CSS = """
* { box-sizing: border-box; }
body {
  background: #0a0a0a;
  color: #e8e8e8;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 16px;
  line-height: 1.7;
  margin: 0;
  padding: 0;
}
.container {
  max-width: 800px;
  margin: 0 auto;
  padding: 24px 20px 60px;
}
.back-link {
  display: inline-block;
  color: #ff8700;
  text-decoration: none;
  font-size: 14px;
  margin-bottom: 24px;
  padding: 6px 12px;
  border: 1px solid #ff8700;
  border-radius: 4px;
}
.back-link:hover { background: #ff870020; }
h1 { color: #fff; font-size: 2em; margin: 0 0 8px; border-bottom: 2px solid #e10600; padding-bottom: 12px; }
h2 { color: #ff8700; font-size: 1.4em; margin: 32px 0 12px; border-bottom: 1px solid #333; padding-bottom: 8px; }
h3 { color: #ffaa44; font-size: 1.15em; margin: 24px 0 8px; }
h4, h5, h6 { color: #ccc; margin: 16px 0 8px; }
p { margin: 0 0 16px; }
a { color: #ff8700; }
a:hover { color: #ffaa44; }
img { max-width: 100%; height: auto; border-radius: 4px; margin: 8px 0; }
table { border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 14px; }
th { background: #1a1a1a; color: #ff8700; padding: 8px 12px; text-align: left; border: 1px solid #333; }
td { padding: 6px 12px; border: 1px solid #222; }
tr:nth-child(even) td { background: #0f0f0f; }
ul, ol { margin: 0 0 16px; padding-left: 28px; }
li { margin-bottom: 4px; }
blockquote { border-left: 3px solid #ff8700; margin: 16px 0; padding: 8px 16px; background: #111; color: #ccc; }
code { font-family: monospace; background: #1a1a1a; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }
.source-notice { font-size: 12px; color: #666; margin-top: 40px; padding-top: 16px; border-top: 1px solid #222; }
/* Hide Wikipedia UI elements */
.mw-editsection, .mw-jump-link, .noprint, .navbox, .navbar,
.catlinks, .mbox-small, .ambox, .tmbox, .ombox, .fmbox,
.stub, .sistersitebox, .hatnote { display: none !important; }
figure { margin: 16px 0; }
figcaption { font-size: 13px; color: #888; }
.infobox { float: right; clear: right; margin: 0 0 16px 20px; background: #111; border: 1px solid #333; font-size: 14px; max-width: 300px; width: 100%; }
@media (max-width: 600px) { .infobox { float: none; max-width: 100%; } }
.infobox th { background: #1a1a1a; }
sup { font-size: 0.75em; }
"""

PAGES = [
    ("Formula_One", "formula-one.html"),
    ("2026_Formula_One_World_Championship", "2026-f1-season.html"),
    ("Miami_International_Autodrome", "miami-circuit.html"),
    ("Hard_Rock_Stadium", "hard-rock-stadium.html"),
    ("Miami_Gardens", "miami-gardens.html"),
    ("Miami", "miami-city.html"),
    ("George_Russell_(racing_driver)", "george-russell.html"),
    ("Lewis_Hamilton", "lewis-hamilton.html"),
    ("Max_Verstappen", "max-verstappen.html"),
    ("Lando_Norris", "lando-norris.html"),
    ("Charles_Leclerc", "charles-leclerc.html"),
    ("McLaren", "mclaren.html"),
    ("Ferrari_in_Formula_One", "ferrari-f1.html"),
    ("Mercedes-Benz_in_Formula_One", "mercedes-f1.html"),
    ("Red_Bull_Racing", "red-bull-racing.html"),
    ("Williams_Racing", "williams-racing.html"),
    ("Drag_reduction_system", "drs.html"),
    ("Energy_recovery_system_(motorsport)", "ers-motorsport.html"),
    ("Formula_One_car", "f1-car.html"),
    ("Artificial_intelligence", "artificial-intelligence.html"),
    ("Large_language_model", "large-language-model.html"),
    ("Machine_learning", "machine-learning.html"),
    ("Formula_Two_Championship", "formula-2.html"),
    ("Porsche_Carrera_Cup", "porsche-carrera-cup.html"),
    ("History_of_Formula_One", "f1-history.html"),
    ("Aerodynamics", "aerodynamics.html"),
]

session = requests.Session()
session.headers.update({
    'User-Agent': 'OutpostLibrary/1.0 (offline-server; educational use)'
})

def scrape_page(wiki_slug, output_file):
    url = f"https://en.wikipedia.org/wiki/{wiki_slug}"
    print(f"  Fetching: {url}")
    
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  ERROR fetching {wiki_slug}: {e}")
        return False
    
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    # Get page title
    title_tag = soup.find('h1', id='firstHeading') or soup.find('h1')
    title = title_tag.get_text() if title_tag else wiki_slug.replace('_', ' ')
    
    # Get main content
    content = soup.find('div', id='mw-content-text')
    if not content:
        print(f"  ERROR: No content found for {wiki_slug}")
        return False
    
    # Remove unwanted elements
    for selector in [
        '.mw-editsection', '.mw-jump-link', '.noprint', '.navbox', '.navbar',
        '.catlinks', '.mbox-small', '.ambox', '.tmbox', '.ombox', '.fmbox',
        '.stub', '.sistersitebox', '[class*="reflist"]', '.references',
        '#toc', '.toc', 'script', 'style', '.mw-references-wrap',
        '.hatnote', '[class*="banner"]', '.shortdescription',
    ]:
        for el in content.select(selector):
            el.decompose()
    
    # Fix internal links to point to Wikipedia (they won't work offline but at least show the target)
    for a in content.find_all('a', href=True):
        href = a['href']
        if href.startswith('/wiki/'):
            a['href'] = f"https://en.wikipedia.org{href}"
            a['target'] = '_blank'
        elif href.startswith('#'):
            pass  # anchor links fine
    
    # Remove image srcset (saves bandwidth, keeps src)
    for img in content.find_all('img'):
        if img.get('srcset'):
            del img['srcset']
        if img.get('src') and img['src'].startswith('//'):
            img['src'] = 'https:' + img['src']
    
    content_html = content.decode_contents()
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — Outpost Library</title>
  <style>
{DARK_CSS}
  </style>
</head>
<body>
  <div class="container">
    <a href="/library" class="back-link">← Library</a>
    <h1>{title}</h1>
    {content_html}
    <div class="source-notice">Source: Wikipedia — <a href="{url}" target="_blank">{url}</a><br>Saved for offline use at the 2026 Miami F1 Grand Prix.</div>
  </div>
</body>
</html>"""
    
    out_path = os.path.join(OUTPUT_DIR, output_file)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    size = os.path.getsize(out_path)
    print(f"  Saved: {output_file} ({size:,} bytes)")
    return True


if __name__ == '__main__':
    print(f"Scraping {len(PAGES)} Wikipedia pages...")
    ok = 0
    fail = 0
    
    for i, (slug, filename) in enumerate(PAGES):
        print(f"\n[{i+1}/{len(PAGES)}] {slug}")
        if scrape_page(slug, filename):
            ok += 1
        else:
            fail += 1
        
        if i < len(PAGES) - 1:
            time.sleep(1.0)  # be polite to Wikipedia
    
    print(f"\nDone: {ok} succeeded, {fail} failed")
