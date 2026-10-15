"""Find individual news videos, excluding related stories and full broadcasts."""
import html
import json
import logging
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from urllib.parse import urlparse


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.blocks = []
        self.active = None
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'script' and (attrs.get('id') == '__NEXT_DATA__' or
                                attrs.get('type') == 'application/ld+json'):
            self.active = [attrs, '']
    def handle_data(self, data):
        if self.active is not None:
            self.active[1] += data
    def handle_endtag(self, tag):
        if tag == 'script' and self.active is not None:
            self.blocks.append(self.active)
            self.active = None


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def words(title):
    value = ''.join(c for c in unicodedata.normalize('NFKD', title.casefold())
                    if not unicodedata.combining(c))
    stop = set('a amb avui com contra de del dels des el els en es ha hi i la les mes no on per pel que qui s se ser si un una uns unes al als els les sobre fins ara seva seu'.split())
    return {w for w in re.findall(r'\w+', value) if len(w) > 2 and w not in stop}


def same_story(first, second):
    a, b = words(first), words(second)
    overlap = len(a & b)
    return bool(a and b and (a == b or
                (overlap >= 5 and overlap / min(len(a), len(b)) >= .75 and
                 overlap / max(len(a), len(b)) >= .55)))


def player_url(url):
    """Only return embeddable player URLs, never article or search pages."""
    if not isinstance(url, str):
        return None
    parsed = urlparse(html.unescape(url))
    if parsed.scheme != 'https':
        return None
    host, path = parsed.hostname or '', parsed.path
    if host in ('www.3cat.cat', '3cat.cat'):
        match = re.search(r'/video/(\d+)(?:/|$)', path)
        if match:
            return 'https://www.3cat.cat/3cat/video/' + match[1] + '/embed/'
    if host in ('www.youtube.com', 'youtube.com', 'www.youtube-nocookie.com', 'youtu.be'):
        match = re.search(r'/(?:embed/|shorts/)?([\w-]{11})(?:/|$)', path)
        if host == 'youtu.be' and match:
            return 'https://www.youtube-nocookie.com/embed/' + match[1]
        if path.startswith('/embed/') and match:
            return 'https://www.youtube-nocookie.com/embed/' + match[1]
        from urllib.parse import parse_qs
        video_id = parse_qs(parsed.query).get('v', [''])[0]
        if re.fullmatch(r'[\w-]{11}', video_id):
            return 'https://www.youtube-nocookie.com/embed/' + video_id
    if host == 'player.vimeo.com' and re.fullmatch(r'/video/\d+/?', path):
        return 'https://player.vimeo.com' + path
    if host in ('www.rtve.es', 'rtve.es') and re.fullmatch(r'/play/embed/video/\d+/?', path):
        return 'https://www.rtve.es' + path
    return None


def extract_video(document, item):
    parser = Scripts()
    parser.feed(document)
    for attrs, raw in parser.blocks:
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            continue
        if attrs.get('id') == '__NEXT_DATA__' and urlparse(item['url']).hostname in ('www.3cat.cat', '3cat.cat'):
            match = re.search(r'/noticia/(\d+)', item['url'])
            if not match:
                continue
            # Match the article's exact ID; sidebar recommendations have other IDs.
            for obj in walk(data):
                if str(obj.get('id')) != match[1] or not isinstance(obj.get('cos'), list):
                    continue
                ids = [v.get('id') for v in obj.get('videos', []) if isinstance(v, dict)]
                for block in obj['cos']:
                    if block.get('tipus') == 'video':
                        ids.append(block.get('props', {}).get('id'))
                for video_id in ids:
                    if re.fullmatch(r'\d+', str(video_id)):
                        return 'https://www.3cat.cat/3cat/video/' + str(video_id) + '/embed/'
        if attrs.get('type') == 'application/ld+json':
            for obj in walk(data):
                kinds = obj.get('@type', [])
                if isinstance(kinds, str):
                    kinds = [kinds]
                if 'VideoObject' not in kinds or not same_story(item['title'], obj.get('name', '')):
                    continue
                url = player_url(obj.get('embedUrl')) or player_url(obj.get('url'))
                if url:
                    return url
    return None


def attach_video_links(items, feeds, download, extra_items=()):
    candidates = [entry for batch in feeds.values() for entry in batch] + list(extra_items)
    by_url = {entry['url']: entry for entry in items}
    matches = {}
    for item in items:
        alternatives = [candidate for candidate in candidates
                        if candidate['url'] != item['url'] and
                        same_story(item['title'], candidate['title'])][:2]
        matches[item['url']] = alternatives
        for candidate in alternatives:
            by_url[candidate['url']] = candidate
    def find(item):
        try:
            document = download(item['url']).decode('utf-8', 'replace')
            return item['url'], extract_video(document, item)
        except Exception as error:
            logging.warning('Video lookup unavailable: %s', error)
            return item['url'], None
    with ThreadPoolExecutor(max_workers=4) as pool:
        found = dict(pool.map(find, by_url.values()))
    for item in items:
        item.pop('video', None)
        for candidate in [item] + matches[item['url']]:
            if found.get(candidate['url']):
                item['video'] = {'url': found[candidate['url']],
                                 'source': candidate['source'],
                                 'articleUrl': candidate['url']}
                break


def media_manifest(items):
    return {'version': 1, 'pages': [
        {'page': index + 2, 'title': item['title'], 'video': item['video']}
        for index, item in enumerate(items) if item.get('video')
    ]}
