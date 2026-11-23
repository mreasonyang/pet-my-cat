"""Language resources for the skill's own tools."""

import argparse
from contextvars import ContextVar
from functools import lru_cache
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("zh-CN", "ja", "en")
_active = ContextVar("pet_my_cat_language", default=None)


def environment_language():
    locale = next((os.environ[key] for key in ("LC_ALL", "LC_MESSAGES", "LANG")
                   if os.environ.get(key)), "en")
    base = locale.split(".", 1)[0].replace("_", "-").split("-", 1)[0].lower()
    return {"zh": "zh-CN", "ja": "ja"}.get(base, "en")


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
