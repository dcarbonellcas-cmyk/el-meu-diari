"""Read dated weather news from 3Cat's published section data."""
import html
import json
import re
from datetime import datetime
from urllib.parse import urljoin
from zoneinfo import ZoneInfo
from video_links import Scripts, walk

TZ = ZoneInfo('Europe/Madrid')


def weather_section(data, now):
    document = data.decode('utf-8', 'replace')
    # Use actual published links, never infer a headline slug.
    links = {}
    for href in re.findall(r'href=[\"\x27]([^\"\x27]+)[\"\x27]', document):
        url = urljoin('https://www.3cat.cat', html.unescape(href))
        match = re.search(r'^https://www\.3cat\.cat/3catinfo/[^?#]+/noticia/(\d+)/', url)
        if match:
            links[match[1]] = url
    parser = Scripts()
    parser.feed(document)
    result, seen = [], set()
    for attrs, raw in parser.blocks:
        if attrs.get('id') != '__NEXT_DATA__':
            continue
        try:
            payload = json.loads(raw)
        except ValueError:
            continue
        for obj in walk(payload):
            article_id = str(obj.get('id', ''))
            if obj.get('tipologia') != 'NOT_NOTICIA' or obj.get('domini') != 'MET' or article_id not in links or article_id in seen:
                continue
            try:
                published = datetime.strptime(obj['data_publicacio'], '%d/%m/%Y %H:%M:%S').replace(tzinfo=TZ)
                updated = datetime.strptime(obj.get('data_modificacio', obj['data_publicacio']), '%d/%m/%Y %H:%M:%S').replace(tzinfo=TZ)
            except (KeyError, ValueError, TypeError):
                continue
            if updated.date() != now.date() or published > now or updated > now:
                continue
            title = html.unescape(obj.get('titol', '')).strip()
            if not title:
                continue
            item = {'source': '3CatInfo · El temps', 'title': title,
                    'excerpt': html.unescape(obj.get('entradeta', '')).strip(),
                    'url': links[article_id], 'published': published.isoformat(),
                    'updated': updated.isoformat(), 'category': 'El temps',
                    'image': next((image.get('text') for image in obj.get('imatges', [])
                                   if image.get('mida') == 'MASTER'), None)}
            for video in obj.get('videos', []):
                video_id = str(video.get('id', ''))
                if re.fullmatch(r'\d+', video_id):
                    item['video'] = {'url': 'https://www.3cat.cat/3cat/video/' + video_id + '/embed/',
                                     'source': '3CatInfo · El temps', 'articleUrl': item['url']}
                    break
            seen.add(article_id)
            result.append(item)
    return result


def merge_day_items(current, previous, now):
    combined = {}
    for item in previous + current:
        try:
            stamp = datetime.fromisoformat(item.get('updated') or item['published']).astimezone(TZ)
            if stamp.date() != now.date() or stamp > now:
                continue
            key = item['url'].split('?')[0]
            old = combined.get(key, {})
            merged = {**item}
            if not merged.get('video') and old.get('video'):
                merged['video'] = old['video']
            combined[key] = merged
        except (ValueError, KeyError, TypeError):
            continue
    return sorted(combined.values(), key=lambda item: item.get('updated') or item['published'], reverse=True)
