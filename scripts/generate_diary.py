"""Build a dated Catalan news PDF from publisher RSS feeds, without an AI key."""
import argparse
import html
import io
import json
import logging
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

TZ = ZoneInfo('Europe/Madrid')
FEEDS = {
    '3CatInfo': 'https://api.3cat.cat/noticies?_format=rss&origen=frontal&frontal=n324-portada-noticia&version=2.0',
    'VilaWeb': 'https://www.vilaweb.cat/feed/',
}
PINK = colors.HexColor('#df5787')
INK = colors.HexColor('#282235')
MUTED = colors.HexColor('#665d69')


def download(url, max_bytes=6_000_000):
    req = urllib.request.Request(url, headers={'User-Agent': 'ElMeuDiari/1.0 (personal RSS digest)'})
    with urllib.request.urlopen(req, timeout=25) as response:
        data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError('Response exceeds size limit')
    return data


def clean(value):
    return ' '.join(html.unescape(re.sub('<[^>]+>', ' ', value or '')).split())


def parse_feed(data, source, now):
    items = []
    for node in ET.fromstring(data).findall('./channel/item'):
        try:
            published = parsedate_to_datetime(node.findtext('pubDate', ''))
            if published.tzinfo is None:
                continue
            published = published.astimezone(TZ)
        except (ValueError, TypeError):
            continue
        if published.date() != now.date() or published > now:
            continue
        link = node.findtext('link', '').strip()
        if not link.startswith('https://'):
            continue
        title_words = clean(node.findtext('title')).split()
        if not title_words:
            continue
        # Limit combined quotations from each article to 25 words.
        title = ' '.join(title_words[:24]) + ('…' if len(title_words) > 24 else '')
        description = node.findtext('description', '')
        desc_words = clean(description).split()
        budget = max(0, 25 - min(len(title_words), 24))
        excerpt = ' '.join(desc_words[:budget])
        if excerpt and len(desc_words) > budget:
            excerpt += '…'
        image = re.search(r'<img[^>]+src=[\"\x27]([^\"\x27]+)', description)
        items.append({'source': source, 'title': title, 'excerpt': excerpt,
                      'url': link, 'published': published.isoformat(),
                      'category': clean(node.findtext('category', 'Actualitat')),
                      'image': html.unescape(image.group(1)) if image else None})
    return items


def select_items(feeds, limit=20):
    # Alternate sources; keep the editorial ordering supplied by each publisher.
    chosen, seen = [], set()
    for index in range(max((len(items) for items in feeds.values()), default=0)):
        for items in feeds.values():
            if index >= len(items):
                continue
            item = items[index]
            key = item['url'].split('?')[0]
            if key not in seen:
                chosen.append(item)
                seen.add(key)
            if len(chosen) >= limit:
                return chosen
    return chosen


def fonts():
    import reportlab
    directory = Path(reportlab.__file__).parent / 'fonts'
    pdfmetrics.registerFont(TTFont('Diary', str(directory / 'Vera.ttf')))
    pdfmetrics.registerFont(TTFont('DiaryBold', str(directory / 'VeraBd.ttf')))


def text(c, value, x, top, width, size=16, leading=None, color=INK, bold=False):
    style = ParagraphStyle('diary', fontName='DiaryBold' if bold else 'Diary',
                           fontSize=size, leading=leading or size * 1.3,
                           textColor=color)
    paragraph = Paragraph(html.escape(value), style)
    _, height = paragraph.wrap(width, 800)
    paragraph.drawOn(c, x, top - height)
    return top - height


def build_pdf(path, items, now, failures, with_images=True):
    fonts()
    width, height = 595, 842
    c = canvas.Canvas(str(path), pagesize=(width, height))
    c.setTitle('El meu diari - ' + now.strftime('%d/%m/%Y'))
    c.setAuthor('El meu diari · recull de 3CatInfo i VilaWeb')
    date = now.strftime('%d/%m/%Y')
    def page_header(number):
        c.setFillColor(colors.HexColor('#fff8f7'))
        c.rect(0, 0, width, height, fill=1, stroke=0)
        c.setFillColor(PINK)
        c.rect(38, height - 45, 32, 4, fill=1, stroke=0)
        text(c, 'EL MEU DIARI', 80, height - 32, 320, 10, color=PINK, bold=True)
        text(c, date, 448, height - 32, 110, 10, color=MUTED)
        c.setStrokeColor(colors.HexColor('#e7c8d3'))
        c.line(38, 44, width - 38, 44)
        text(c, 'Actualitzat a les ' + now.strftime('%H:%M') + ' · Europe/Madrid', 38, 33, 420, 8, color=MUTED)
        text(c, str(number), width - 60, 33, 25, 8, color=MUTED)
    page_header(1)
    text(c, 'LA TEVA REVISTA D’ACTUALITAT', 38, 744, 510, 12, color=PINK, bold=True)
    y = text(c, 'Què passa\navui?', 38, 695, 510, 48, leading=57, bold=True)
    y = text(c, date, 38, y - 24, 510, 25, color=PINK)
    y = text(c, f'{len(items)} notícies publicades avui', 38, y - 34, 510, 19, bold=True)
    y = text(c, 'Titulars i fragments breus dels canals dels mitjans. Obre els enllaços per llegir els articles complets.', 38, y - 22, 500, 14, color=MUTED)
    y = text(c, 'Fonts: ' + ' · '.join(FEEDS), 38, y - 24, 500, 12)
    if failures:
        y = text(c, 'Cobertura parcial: no s’ha pogut consultar ' + ', '.join(failures) + '.', 38, y - 20, 500, 12, color=MUTED)
    if not items:
        text(c, 'Encara no hi ha notícies d’avui disponibles als canals consultats. El document es tornarà a actualitzar automàticament.', 38, y - 32, 500, 17)
    c.showPage()
    for index, item in enumerate(items, 2):
        page_header(index)
        text(c, item['source'] + ' · ' + item['category'], 38, 757, 510, 11, color=PINK, bold=True)
        y = text(c, item['title'], 38, 710, 510, 29, leading=37, bold=True)
        published = datetime.fromisoformat(item['published'])
        y = text(c, 'Publicat avui a les ' + published.strftime('%H:%M'), 38, y - 18, 510, 10, color=MUTED)
        if with_images and item.get('image') and item['image'].startswith('https://img.3cat.cat/'):
            try:
                photo = ImageReader(io.BytesIO(download(item['image'])))
                iw, ih = photo.getSize()
                ph = min(230, 510 * ih / iw)
                c.drawImage(photo, 38, y - 24 - ph, width=510, height=ph, preserveAspectRatio=True, anchor='c', mask='auto')
                y -= 24 + ph
                y = text(c, 'Imatge de la font · ' + item['source'], 38, y - 8, 510, 8, color=MUTED)
            except Exception as error:
                logging.warning('Photo unavailable: %s', error)
        if item['excerpt']:
            y = text(c, item['excerpt'], 38, y - 25, 510, 16, color=MUTED)
        text(c, 'Llegeix la notícia completa a ' + item['source'], 38, min(y - 35, 220), 510, 14, color=PINK, bold=True)
        link_top = min(y - 35, 220)
        c.linkURL(item['url'], (38, link_top - 25, 548, link_top + 3), relative=0, thickness=0)
        text(c, item['url'], 38, link_top - 38, 510, 8, color=MUTED)
        c.showPage()
    c.save()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='diaris')
    parser.add_argument('--fixtures', help='Directory with 3cat.xml and vilaweb.xml for deterministic checks')
    parser.add_argument('--now', help='ISO datetime for checks')
    parser.add_argument('--no-images', action='store_true')
    args = parser.parse_args()
    now = datetime.fromisoformat(args.now).astimezone(TZ) if args.now else datetime.now(TZ)
    feeds, failures = {}, []
    for source, url in FEEDS.items():
        try:
            if args.fixtures:
                file = '3cat.xml' if source == '3CatInfo' else 'vilaweb.xml'
                data = (Path(args.fixtures) / file).read_bytes()
            else:
                data = download(url)
            feeds[source] = parse_feed(data, source, now)
        except Exception as error:
            logging.warning('%s unavailable: %s', source, error)
            failures.append(source)
    if len(failures) == len(FEEDS):
        raise RuntimeError('No news source available; do not replace the previous edition')
    items = select_items(feeds)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    build_pdf(output / 'avui.pdf', items, now, failures, not args.no_images)
    metadata = {'date': now.date().isoformat(), 'updatedAt': now.isoformat(),
                'pdf': 'diaris/avui.pdf', 'count': len(items),
                'sources': list(feeds), 'unavailableSources': failures}
    (output / 'latest.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(metadata, ensure_ascii=False))

if __name__ == '__main__':
    main()
