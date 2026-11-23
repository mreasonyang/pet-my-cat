"""Run a downloaded upstream page and a packaged skill in a fresh desktop project."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
import zipfile

from playwright.sync_api import expect, sync_playwright
from .test_portable import run_script, write_fixture


def checked(result):
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace"))


def open_session(page, path, name):
    page.goto(path.as_uri())
    expect(page.locator('#stage[data-ready="true"]')).to_be_visible(timeout=30000)
    buttons = page.locator("button[data-cat]")
    expect(buttons).to_have_count(14)
    guest = page.get_by_role("button", name=name, exact=True)
    expect(guest).to_have_attribute("aria-pressed", "true")
    page.get_by_role("button", name="白猫", exact=True).click()
    expect(guest).to_have_attribute("aria-pressed", "false")
    guest.click()
    expect(guest).to_have_attribute("aria-pressed", "true")
    expect(page.locator("#proportions-toggle")).to_have_attribute("aria-label", "猫の体格を調整")
    expect(page.locator("#sound")).to_have_attribute("aria-label", "ゴロゴロ音")
    page.locator("#stage").focus()
    page.keyboard.press("Space")
    page.keyboard.press("t")


def main(archive, upstream):
    with tempfile.TemporaryDirectory(prefix="pet smoke ") as work:
        project = Path(work) / "猫 project"
        install = project / ".agents" / "skills"
        install.mkdir(parents=True)
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(install)
        skill = install / "pet-my-cat"
        assert (skill / "SKILL.md").is_file()
        source, layout = write_fixture(project)
        annotation = project / "标注 レイアウト.json"
        annotation.write_text(json.dumps(layout, ensure_ascii=False), encoding="utf-8-sig")
        layers = project / "画像 layers"
        checked(run_script(skill, "prepare_photo.py", source, annotation, layers, "--lang", "ja"))
        sessions = []
        for lang, name in (("zh-CN", "我家的猫"), ("ja", "うちの猫"), ("en", "My cat")):
            out = project / (name + " session.html")
            args = ("--page", upstream, "--body", layers / "body.png", "--tail", layers / "tail.png",
                    "--lang", lang, "--out", out)
            checked(run_script(skill, "build_session.py", *args))
            original = out.read_bytes()
            assert run_script(skill, "build_session.py", *args).returncode != 0
            assert out.read_bytes() == original
            sessions.append((out, name, lang))

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = browser.new_context(offline=True, viewport={"width": 1000, "height": 720})
            page = context.new_page()
            remote = []
            page.on("request", lambda req: remote.append(req.url) if req.url.startswith(("http://", "https://")) else None)
            for path, name, lang in sessions:
                open_session(page, path, name)
                expect(page.locator('meta[name="pet-my-cat-language"]')).to_have_attribute("content", lang)
                print(f"{lang}: standalone session rendered and switched cats")
            shutil.rmtree(skill)
            assert install.is_dir() and not skill.exists()
            page.close()
            page = context.new_page()
            page.on("request", lambda req: remote.append(req.url) if req.url.startswith(("http://", "https://")) else None)
            open_session(page, sessions[1][0], sessions[1][1])
            assert not remote, remote
            print("Uninstalled: a fresh offline page still opens the saved session.")
            browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("upstream", type=Path)
    args = parser.parse_args()
    main(args.archive.resolve(), args.upstream.resolve())
