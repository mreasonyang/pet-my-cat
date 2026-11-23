import re
from string import Formatter
import unittest

from scripts import build_bookmark, build_session
from scripts.skill_i18n import LANGUAGES, ROOT, catalog


def fields(value):
    return sorted(field for _, field, _, _ in Formatter().parse(value) if field)


class LocaleTests(unittest.TestCase):
    def test_translations_preserve_fields_and_links(self):
        source = catalog("en")
        for lang in LANGUAGES:
            with self.subTest(lang=lang):
                copy = catalog(lang)
                self.assertEqual(copy.keys(), source.keys())
                for section, entries in source.items():
                    self.assertEqual(copy[section].keys(), entries.keys())
                    for key, original in entries.items():
                        value = copy[section][key]
                        self.assertTrue(value.strip(), key)
                        self.assertEqual(fields(value), fields(original), key)
                self.assertEqual(fields(copy["setup"]["stepBookmark"]), ["bookmark"])
                self.assertEqual(fields(copy["setup"]["stepOpen"]), ["site"])

    def test_offline_bookmark_matches_its_sources(self):
        self.assertEqual(build_bookmark.render(), (ROOT / "assets/current-tab.html").read_bytes())

    def test_localizing_a_session_preserves_the_upstream_payload(self):
        # A small synthetic page in the public format keeps this test independent of the site.
        hook = build_session.RENDERER_HOOK
        if len(hook) % 2:
            hook += " "
        pairs = [chr(0x3000 + (ord(a) << 7) + ord(b)) for a, b in zip(hook[::2], hook[1::2])]
        pack = chr(0x3000 + len(pairs)) + "".join(pairs) + "X"
        packed_script = build_session.PACK_TAG + pack + "</script>"
        html = ('<!doctype html>\n<html lang="ja">\n' + build_session.CHARSET_TAG +
                '<title>もとのページ</title></head><body><p>もとの案内</p>' + packed_script +
                '<script>' + build_session.LOADER_HOOK + '</script></body></html>')
        for lang in LANGUAGES:
            with self.subTest(lang=lang):
                page = build_session.build_session(html.encode("utf-16"), "小七", "", "", lang)
                self.assertIn('<html lang="ja">', page)
                self.assertIn('<title>もとのページ</title></head><body><p>もとの案内</p>', page)
                self.assertIn(packed_script, page)
                self.assertIn(f'<meta name="pet-my-cat-language" content="{lang}">', page)
                with self.assertRaisesRegex(ValueError, re.escape(catalog(lang)["cli"]["pageEncoding"])):
                    build_session.build_session(b"invalid", "小七", "", "", lang)
