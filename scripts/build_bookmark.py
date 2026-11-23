"""Embed the bookmark's translations so the distributed HTML also works as a single local file."""

import argparse
from html import escape
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

if __package__:
    from .skill_i18n import LANGUAGES, ROOT, catalog
else:
    from skill_i18n import LANGUAGES, ROOT, catalog


def render():
    template = (ROOT / "src/current-tab.html").read_text(encoding="utf-8")
    helper = (ROOT / "src/language.js").read_text(encoding="utf-8").strip()
    template = template.replace("@@LANGUAGE_FUNCTION@@", helper)
    for section in ("setup", "overlay"):
        messages = {lang: catalog(lang)[section] for lang in LANGUAGES}
        encoded = json.dumps(messages, ensure_ascii=False, separators=(",", ":")).replace("<", r"\u003c")
        template = template.replace("@@" + section.upper() + "@@", encoded)
    no_script = "\n".join(
        f'<p lang="{lang}">{escape(catalog(lang)["setup"]["noScript"])}</p>' for lang in LANGUAGES
    )
    template = template.replace("@@NO_SCRIPT@@", no_script)
    template = template.replace("@@TITLE@@", escape(catalog("en")["setup"]["title"]))
    template = template.replace("@@LANGUAGE_LABEL@@", escape(catalog("en")["setup"]["language"]))
    if "@@" in template:
        raise ValueError("Unresolved template token in src/current-tab.html")
    return template.encode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check the shipped HTML without writing it")
    args = parser.parse_args()
    output = ROOT / "assets/current-tab.html"
    data = render()
    if args.check:
        if not output.is_file() or output.read_bytes() != data:
            parser.exit(1, "Regenerate assets/current-tab.html with scripts/build_bookmark.py\n")
        return
    handle = NamedTemporaryFile(dir=output.parent, delete=False)
    path = Path(handle.name)
    try:
        with handle:
            handle.write(data)
        path.chmod(0o644)
        path.replace(output)
    finally:
        path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
