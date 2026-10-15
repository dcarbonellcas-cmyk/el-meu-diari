"""Build a dated Catalan news PDF from publisher RSS feeds, without an AI key."""
import argparse
import hashlib
import shutil
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
from video_links import attach_video_links, media_manifest
from news_sources import weather_section, merge_day_items
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
    'ARA': 'https://www.ara.cat/rss/latest/',
    'betevé': 'https://beteve.cat/feed/',
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
        title = ' '.join(title_words[:24]) + ('…' if len(title_words) > 24 else '')
        description = node.findtext('description', '')
        desc_words = clean(description).split()
        # Use the available RSS description for a readable half-page summary.
        # Do not invent missing facts when the feed supplies little text.
        excerpt = ' '.join(desc_words[:85])
        if excerpt and len(desc_words) > 85:
            excerpt += '…'
        image = re.search(r'<img[^>]+src=[\"\x27]([^\"\x27]+)', description)
        items.append({'source': source, 'title': title, 'excerpt': excerpt,
                      'url': link, 'published': published.isoformat(),
                      'category': clean(node.findtext('category', 'Actualitat')),
                      'image': html.unescape(image.group(1)) if image else None})
    return items


def is_weather_news(item):
    # Select reported weather events and warnings, not routine forecasts.
    headline = (item.get('title', '') + ' ' + item.get('category', '')).casefold()
    return bool(re.search(
        r'\b(inundacions?|tempestes?|nevades?|huracans?|tifons?|'
        r'sequer[ae]s?|dana|aiguats?|pedregades?|esllavissades?)\b|'
        r'temporals? (de|amb) (pluja|vent|neu|mar)|onad[ae]s? de (calor|fred)|'
        r'(alerta|avís|avisos|emergència).*(pluja|pluges|vent|neu|calor|fred|meteorol)|'
        r'(pluja|pluges|vent|neu|calor|fred|meteorol).*(alerta|avís|avisos|emergència)',
        headline))


def select_items(feeds, limit=None):
    # Keep publisher ordering and alternate sources.
    ordered, seen = [], set()
    for index in range(max((len(items) for items in feeds.values()), default=0)):
        for items in feeds.values():
            if index >= len(items):
                continue
            item = items[index]
            key = item['url'].split('?')[0]
            if key not in seen:
                ordered.append(item)
                seen.add(key)
    if limit is None:
        return ordered
    if limit <= 0:
        return []
    chosen = ordered[:limit]
    # Reserve up to three places for significant weather reporting from today's feeds.
    for item in [item for item in ordered if is_weather_news(item)][:min(3, limit)]:
        if item in chosen:
            continue
        replace = next((i for i in range(len(chosen) - 1, -1, -1)
                        if not is_weather_news(chosen[i])), None)
        if replace is not None:
            chosen[replace] = item
    return chosen



def news_priority(item):
    """Approximate editorial priority from explicit headline topics, not truth or popularity."""
    import unicodedata
    title = ''.join(c for c in unicodedata.normalize('NFKD', item.get('title', '').casefold())
                    if not unicodedata.combining(c))
    category = ''.join(c for c in unicodedata.normalize('NFKD', item.get('category', '').casefold())
                       if not unicodedata.combining(c))
    retrospective = bool(re.search(r'\b(homenatge|aniversari|commemoracio|recorda|historia)\b|fa \d+ anys', title))
    opinion = bool(re.search(r'\b(opinio|editorial|critica|horoscop)\b', category))
    urgent = re.search(r'\b(evacuacio|evacuen|evacuar|confinament|confinar|tsunami|terratremol|atemptat|bombardeig|inundacions|aiguats)\b|alerta (vermella|maxima)|risc extrem|emergencia (quimica|nuclear)', title)
    serious = re.search(r'\b(morts|mortals|victimes|assassinat|guerra|incendi|huraca|temporal|rescat)\b', title)
    public_impact = re.search(r'\b(pensions|impostos|pressupostos|eleccions|govern|parlament|congres|tribunal|habitatge|lloguers|sanitat|educacio|inflacio|atur|salari|salaris|energia|vaga|transport|rodalies|seguretat)\b', title + ' ' + category)
    culture = re.search(r'\b(cultura|esports|esport|gastronomia|gent|estils|curiositats|oci)\b', category)
    if opinion:
        level = 6
    elif urgent and not retrospective:
        level = 0
    elif serious and not retrospective:
        level = 1
    elif public_impact and not retrospective:
        level = 2
    elif culture or retrospective:
        level = 5
    else:
        level = 3
    # Daily weather remains easy to find ahead of lighter stories.
    if item.get('category') == 'El temps' and level > 2:
        level = 3
    try:
        timestamp = datetime.fromisoformat(item.get('updated') or item['published']).timestamp()
    except (KeyError, ValueError, TypeError):
        timestamp = 0
    return (level, -timestamp, item.get('url', ''))


def rank_news(items):
    return sorted(items, key=news_priority)


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
    c.setAuthor('El meu diari · recull de mitjans periodístics')
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
    y = text(c, f'{len(items)} notícies del dia', 38, y - 34, 510, 19, bold=True)
    y = text(c, 'Notícies d’avui explicades amb els resums disponibles dels mitjans consultats.', 38, y - 22, 500, 14, color=MUTED)
    y = text(c, 'Fonts: ' + ' · '.join(dict.fromkeys(item['source'] for item in items)), 38, y - 24, 500, 12)
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
        y = text(c, ('Actualitzat avui a les ' + datetime.fromisoformat(item['updated']).strftime('%H:%M') if published.date() != now.date() and item.get('updated') else 'Publicat avui a les ' + published.strftime('%H:%M')), 38, y - 18, 510, 10, color=MUTED)
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
            # Approximately 5–8 lines when the RSS feed provides enough text.
            # Reduce the font slightly only if needed to keep the page legible.
            summary_top = y - 25
            summary = item['excerpt']
            for font_size in (17, 16, 15):
                style = ParagraphStyle('summary', fontName='Diary',
                                       fontSize=font_size, leading=font_size * 1.45,
                                       textColor=INK)
                paragraph = Paragraph(html.escape(summary), style)
                _, summary_height = paragraph.wrap(510, 800)
                if summary_top - summary_height >= 88:
                    paragraph.drawOn(c, 38, summary_top - summary_height)
                    break
        c.showPage()
    c.save()




def prune_finished_days(output, catalog, today):
    """Keep only the most complete edition for each previous day."""
    groups = {}
    for entry in catalog['editions']:
        day = entry.get('date', '')
        if day and day < today:
            groups.setdefault(day, []).append(entry)
    selected = {
        max(entries, key=lambda e: (e.get('count', 0), e.get('updatedAt', '')))['pdf']
        for entries in groups.values()
    }
    retained = []
    for entry in catalog['editions']:
        day = entry.get('date', '')
        if not day or day >= today or entry['pdf'] in selected:
            retained.append(entry)
        elif re.fullmatch(r'diaris/arxiu/\d{4}-\d{2}-\d{2}/\d{2}-\d{2}-\d{2}-\d{6}\.pdf', entry['pdf']):
            (output.parent / entry['pdf']).unlink(missing_ok=True)
            (output.parent / entry['pdf']).with_suffix('.media.json').unlink(missing_ok=True)
    catalog['editions'] = retained


def save_edition(output, items, metadata, now, with_images=True):
    catalog_path = output / 'archive.json'
    catalog = json.loads(catalog_path.read_text()) if catalog_path.exists() else {'editions': []}
    fingerprint = hashlib.sha256(json.dumps({
        'date': metadata['date'], 'items': items, 'readerFormat': 'priority-order-v3',
        'unavailableSources': sorted(metadata['unavailableSources'])
    }, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    latest_path = output / 'latest.json'
    previous = json.loads(latest_path.read_text()) if latest_path.exists() else {}
    if (previous.get('fingerprint') == fingerprint and
            (output / 'avui.pdf').exists() and
            (not items or any(entry.get('fingerprint') == fingerprint and
                             (output.parent / entry['pdf']).exists()
                             for entry in catalog['editions']))):
        prune_finished_days(output, catalog, metadata['date'])
        catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n')
        return {**previous, 'archiveChanged': False}
    metadata['fingerprint'] = fingerprint
    if items:
        relative_path = f"arxiu/{metadata['date']}/{now.strftime('%H-%M-%S-%f')}.pdf"
        archived_pdf = output / relative_path
        archived_pdf.parent.mkdir(parents=True, exist_ok=True)
        build_pdf(archived_pdf, items, now, metadata['unavailableSources'], with_images)
        archived_pdf.with_suffix('.media.json').write_text(json.dumps(media_manifest(items), ensure_ascii=False, indent=2) + '\n')
        shutil.copyfile(archived_pdf, output / 'avui.pdf')
        shutil.copyfile(archived_pdf.with_suffix('.media.json'), output / 'avui.media.json')
        entry = {**metadata, 'pdf': 'diaris/' + relative_path}
        catalog['editions'].insert(0, entry)
    else:
        build_pdf(output / 'avui.pdf', items, now, metadata['unavailableSources'], with_images)
        (output / 'avui.media.json').write_text(json.dumps(media_manifest(items)) + '\n')
    prune_finished_days(output, catalog, metadata['date'])
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n')
    latest_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n')
    return {**metadata, 'archiveChanged': bool(items)}


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
                file = {'3CatInfo': '3cat.xml', 'VilaWeb': 'vilaweb.xml', 'ARA': 'ara.xml', 'betevé': 'beteve.xml'}[source]
                data = (Path(args.fixtures) / file).read_bytes()
            else:
                data = download(url)
            feeds[source] = parse_feed(data, source, now)
        except Exception as error:
            logging.warning('%s unavailable: %s', source, error)
            failures.append(source)
    if len(failures) == len(FEEDS):
        raise RuntimeError('No news source available; do not replace the previous edition')
    if not args.fixtures:
        try:
            feeds['3CatInfo · El temps'] = weather_section(download('https://www.3cat.cat/3catinfo/el-temps/noticies/'), now)
        except Exception as error:
            logging.warning('Weather section unavailable: %s', error)
            failures.append('3CatInfo · El temps')
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    day_path = output / 'items-today.json'
    previous_items = []
    if day_path.exists():
        try:
            saved = json.loads(day_path.read_text())
            if saved.get('date') == now.date().isoformat():
                previous_items = saved.get('items', [])
        except (ValueError, TypeError):
            pass
    items = rank_news(merge_day_items(select_items(feeds), previous_items, now))
    if not args.fixtures:
        attach_video_links(items, feeds, download)
    day_path.write_text(json.dumps({'date': now.date().isoformat(), 'items': items}, ensure_ascii=False, indent=2) + '\n')
    metadata = {'date': now.date().isoformat(), 'updatedAt': now.isoformat(),
                'pdf': 'diaris/avui.pdf', 'count': len(items),
                'sources': list(feeds), 'unavailableSources': failures}
    result = save_edition(output, items, metadata, now, not args.no_images)
    print(json.dumps(result, ensure_ascii=False))

if __name__ == '__main__':
    main()
