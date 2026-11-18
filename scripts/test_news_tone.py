"""Offline checks for conservative grouping and reader page correspondence."""
import unittest
from generate_diary import news_tone, rank_news
from video_links import media_manifest


class NewsToneTests(unittest.TestCase):
    def test_headlines(self):
        cases = [
            ('Rescaten amb vida una dona atrapada', 'good'),
            ('Un nou tractament eficaç contra una malaltia', 'good'),
            ('Baixa l’atur a Catalunya', 'good'),
            ('Tres morts en un incendi', 'bad'),
            ('Evacuen cent veïns per les inundacions', 'bad'),
            ('El museu presenta una nova exposició', 'other'),
            ('Podria baixar l’atur aquest any', 'other'),
            ('Un acord de pau després de la guerra', 'other'),
            ('Un tractament eficaç: què en sabem?', 'other'),
            ('No baixa l’atur a Catalunya', 'other'),
            ('Un incendi sense ferits', 'other'),
            ('Un municipi cedeix solars per fer pisos protegits de lloguer assequible', 'good'),
            ('Posa en marxa una prova pilot per atendre persones amb TEA', 'good'),
            ('El club confirma una lesió greu del davanter', 'bad'),
            ('Denuncien assetjament laboral en una empresa', 'bad'),
            ('Els experts investiguen un cas d’abús sexual', 'bad'),
        ]
        for title, expected in cases:
            with self.subTest(title=title):
                self.assertEqual(news_tone({'title': title}), expected)

    def test_order_and_page_metadata(self):
        items = rank_news([
            {'title': title, 'url': f'https://example.org/{i}',
             'source': 'Test', 'published': '2026-11-18T12:00:00+01:00'}
            for i, title in enumerate([
                'Tres morts en un incendi', 'El museu presenta una exposició',
                'Rescaten amb vida una dona atrapada',
            ])
        ])
        self.assertEqual([item['tone'] for item in items], ['good', 'bad', 'other'])
        self.assertTrue(all(item.get('priority') for item in items))
        pages = media_manifest(items)['pages']
        self.assertEqual([entry['page'] for entry in pages], [2, 3, 4])
        self.assertEqual([entry['articleUrl'] for entry in pages], [item['url'] for item in items])
        self.assertEqual([entry['tone'] for entry in pages], ['good', 'bad', 'other'])


if __name__ == '__main__':
    unittest.main()
