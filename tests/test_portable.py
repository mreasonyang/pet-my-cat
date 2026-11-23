import concurrent.futures
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import build_session, skill_i18n


def write_fixture(directory):
    from PIL import Image, ImageChops, ImageDraw

    # An original drawing with a separate tail, small enough for a desktop smoke test.
    source = directory / "茶猫 photo.png"
    photo = Image.new("RGB", (300, 160), "#528781")
    draw = ImageDraw.Draw(photo)
    draw.line([(178, 78), (225, 78), (254, 86), (270, 88)], fill="#774e34", width=16)
    draw.ellipse((262, 80, 278, 96), fill="#774e34")
    draw.ellipse((59, 42, 194, 116), fill="#d9a560")
    draw.ellipse((24, 50, 87, 110), fill="#ca8246")
    for ear in ([(34, 64), (29, 41), (54, 56)], [(51, 57), (67, 39), (70, 68)]):
        draw.polygon(ear, fill="#814c37")
    photo.save(source)
    # In this fixture color segmentation is exact and avoids including the floor.
    difference = ImageChops.difference(photo, Image.new("RGB", photo.size, "#528781"))
    body = difference.convert("L").point(lambda value: 255 if value else 0)
    ImageDraw.Draw(body).rectangle((194, 0, 299, 159), fill=0)
    body.save(directory / "身体 mask.png")
    layout = {"head": [55, 74], "body": "身体 mask.png",
              "tail": [[182, 78, 16], [225, 78, 16], [254, 86, 16], [271, 88, 13], [277, 88, 0]]}
    return source, layout


def run_script(skill, script, *args):
    return subprocess.run([sys.executable, str(skill / "scripts" / script), *map(str, args)],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


class PortableFileTests(unittest.TestCase):
    def test_annotation_encodings_and_unicode_paths(self):
        try:
            import PIL
        except ImportError:
            self.skipTest("Pillow is needed for photo preparation")
        with tempfile.TemporaryDirectory(prefix="pet test ") as tmp:
            directory = Path(tmp) / "猫 フォト"
            directory.mkdir()
            source, layout = write_fixture(directory)
            for encoding in ("utf-8", "utf-8-sig", "utf-16"):
                with self.subTest(encoding=encoding):
                    annotation = directory / (encoding + ".json")
                    annotation.write_text(json.dumps(layout, ensure_ascii=False), encoding=encoding)
                    output = directory / ("圖層 " + encoding)
                    result = run_script(skill_i18n.ROOT, "prepare_photo.py", source, annotation, output, "--lang", "ja")
                    self.assertEqual(result.returncode, 0, result.stderr)
                    for name, size in (("body.png", (1517, 935)), ("tail.png", (684, 200))):
                        build_session.validate_png((output / name).read_bytes(), size)

    def test_concurrent_output_preserves_first_complete_document(self):
        with tempfile.TemporaryDirectory(prefix="pet test ") as tmp:
            dest = Path(tmp) / "我的 猫.html"
            documents = ["猫" * 10000, "みけ" * 10000]

            def write(document):
                try:
                    build_session.write_new(dest, document)
                except ValueError:
                    return False
                return True

            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                successes = list(pool.map(write, documents))
            self.assertEqual(successes.count(True), 1)
            self.assertEqual(dest.read_text(encoding="utf-8"), documents[successes.index(True)])
            self.assertEqual(list(dest.parent.iterdir()), [dest])

    def test_system_language_without_shell_locale_variables(self):
        with patch.dict(os.environ, {}, clear=True):
            for setting, expected in (("Japanese_Japan", "ja"), ("Chinese (Simplified)_China", "zh-CN"),
                                      ("zh_CN", "zh-CN"), ("de_DE", "en")):
                with self.subTest(setting=setting), patch.object(skill_i18n.locale, "getlocale", return_value=(setting, None)):
                    self.assertEqual(skill_i18n.environment_language(), expected)
