"""Language resources for the skill's own tools."""

import argparse
from contextvars import ContextVar
from functools import lru_cache
import json
import locale
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("zh-CN", "ja", "en")
_active = ContextVar("pet_my_cat_language", default=None)


def environment_language():
    setting = next((os.environ[key] for key in ("LC_ALL", "LC_MESSAGES", "LANG")
                    if os.environ.get(key)), None)
    if not setting:
        setting = locale.getlocale()[0] or "en"
    base = setting.split(".", 1)[0].replace("_", "-").split("-", 1)[0].lower()
    if base == "zh" or base.startswith("chinese"):
        return "zh-CN"
    return "ja" if base in ("ja", "japanese") else "en"


def language():
    return _active.get() or environment_language()


@lru_cache(maxsize=len(LANGUAGES))
def catalog(lang):
    if lang not in LANGUAGES:
        raise ValueError(f"Unsupported --lang: {lang}")
    return json.loads((ROOT / "locales" / (lang + ".json")).read_text(encoding="utf-8"))


def msg(key, *, lang=None, **fields):
    return catalog(lang or language())["cli"][key].format(**fields)


def argument_parser(description):
    # A Windows console accepts Unicode. Its redirected streams may otherwise use
    # an ANSI code page that cannot represent the selected language or file paths.
    if os.name == "nt" and not os.environ.get("PYTHONIOENCODING"):
        for stream in (sys.stdout, sys.stderr):
            if stream is not None and not stream.isatty() and hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8")
    # --help and errors about the input files should use the same language as the output.
    probe = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    probe.add_argument("--lang", choices=LANGUAGES)
    args, _ = probe.parse_known_args()
    _active.set(args.lang or environment_language())
    parser = argparse.ArgumentParser(description=msg(description), add_help=False, allow_abbrev=False)
    parser.add_argument("-h", "--help", action="help", help=msg("help"))
    parser.add_argument("--lang", choices=LANGUAGES, default=language(), help=msg("langHelp"))
    parser._optionals.title = msg("options")
    parser._positionals.title = msg("positionals")
    return parser
