"""Run a downloaded upstream page and a packaged skill in a fresh desktop project."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import zipfile

from playwright.sync_api import expect, sync_playwright
from .test_portable import run_script, write_fixture


def checked(result):
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace"))


def run_powershell(shell, command, **variables):
    env = {**os.environ, **{key: str(value) for key, value in variables.items()}}
    result = subprocess.run([shell, "-NoProfile", "-NonInteractive", "-Command",
                             "$ErrorActionPreference='Stop'\n" + command], env=env, capture_output=True)
    checked(result)


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


def discover(project, codex_cli):
    request = {"cwds": [str(project)], "forceReload": True}
    with subprocess.Popen(["node", str(codex_cli), "app-server"], cwd=project, stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8") as server:
        timer = threading.Timer(30, server.kill)
        timer.start()
        try:
            def send(message):
                server.stdin.write(json.dumps(message) + "\n")
                server.stdin.flush()

            def response(request_id):
                for line in server.stdout:
                    message = json.loads(line)
                    if message.get("id") == request_id:
                        return message["result"]
                raise RuntimeError("Codex app-server exited before answering skills/list")

            send({"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "desktop_test", "version": "1"}}})
            response(1)
            send({"method": "initialized"})
            send({"id": 2, "method": "skills/list", "params": request})
            records = response(2)["data"]
            expected = project / ".agents" / "skills" / "pet-my-cat" / "SKILL.md"
            found = [skill for record in records for skill in record["skills"] if skill["name"] == "pet-my-cat"]
            print("Codex discovery", json.dumps({"project": str(project),
                  "matches": [(skill["scope"], skill["path"]) for skill in found],
                  "errors": [error for record in records for error in record.get("errors", [])]}), flush=True)
            # Windows may return the long form of an 8.3 temp path or a verbatim path.
            return [s["scope"] for s in found if expected.is_file() and expected.samefile(s["path"])]
        finally:
            timer.cancel()
            server.stdin.close()
            server.terminate()


def check_current_tab(browser, upstream, guide_path, session_path):
    context = browser.new_context(viewport={"width": 1000, "height": 720})
    page = context.new_page()
    page.goto(guide_path.as_uri())
    mount = page.locator("#mount-session").text_content()
    original = "https://pet-the-cat.pages.dev/"
    page.route(original, lambda route: route.fulfill(path=upstream, content_type="text/html; charset=utf-16le"))
    page.goto(original)
    expect(page.locator('#stage[data-ready="true"]')).to_be_visible(timeout=30000)
    page.get_by_role("button", name="三毛猫", exact=True).click()
    page.evaluate("([fn, doc]) => (0, eval)('(' + fn + ')')(doc, 'ja')",
                  [mount, session_path.read_text(encoding="utf-8")])
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        frames = [frame for frame in page.frames[1:] if frame.locator('#stage[data-ready="true"]').count()]
        if frames:
            break
        page.wait_for_timeout(100)
    else:
        raise AssertionError("Guest frame failed to load")
    guest = frames[0]
    expect(guest.get_by_role("button", name="うちの猫", exact=True)).to_have_attribute("aria-pressed", "true")
    white_cat = guest.get_by_role("button", name="白猫", exact=True)
    white_cat.click()
    # A real Chromium chooser cancel bubbles from the input. Reopening the bookmark invokes it.
    if browser.browser_type.name == "chromium":
        cdp = context.new_cdp_session(page)
        cdp.send("Page.enable")
        cdp.send("Page.setInterceptFileChooserDialog", {"enabled": True, "cancel": True})
        opened = []
        cdp.once("Page.fileChooserOpened", lambda event: opened.append(event))
        cdp.send("Runtime.evaluate", {"expression": "(" + mount + ")(undefined, 'ja')", "userGesture": True})
        deadline = time.monotonic() + 8
        while not opened and time.monotonic() < deadline:
            page.wait_for_timeout(50)
        assert opened, "Cancel did not reach the Chromium file chooser"
        expect(white_cat).to_have_attribute("aria-pressed", "true")
    guest.locator("#stage").focus()
    page.keyboard.press("Escape")
    page.wait_for_function("() => !window[Symbol.for('pet-the-cat-local.current-tab.v1')]")
    expect(page.get_by_role("button", name="三毛猫", exact=True)).to_have_attribute("aria-pressed", "true")
    assert page.url == original
    context.close()


def main(archive, upstream, codex_cli):
    with tempfile.TemporaryDirectory(prefix="pet smoke ") as work:
        project = Path(work) / "猫 project"
        install = project / ".agents" / "skills"
        install.mkdir(parents=True)
        subprocess.run(["git", "init", "--quiet", str(project)], check=True)
        assert not discover(project, codex_cli)
        if os.name == "nt":
            run_powershell("powershell", "Expand-Archive -LiteralPath $env:QA_ZIP -DestinationPath $env:QA_DEST",
                           QA_ZIP=archive, QA_DEST=install)
        else:
            with zipfile.ZipFile(archive) as bundle:
                bundle.extractall(install)
        skill = install / "pet-my-cat"
        assert (skill / "SKILL.md").is_file()
        assert discover(project, codex_cli) == ["repo"]
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

        if os.name == "nt":
            name = '-猫 "みけ" 🐈'
            for shell in ("powershell", "pwsh"):
                out = project / (shell + ".html")
                run_powershell(shell, """
$env:QA_NAME | Set-Content -LiteralPath $env:QA_TEXT -Encoding UTF8
& $env:QA_PY $env:QA_BUILD --page $env:QA_PAGE --body $env:QA_BODY --tail $env:QA_TAIL --name-file $env:QA_TEXT --lang ja --out $env:QA_OUT
exit $LASTEXITCODE
""", QA_NAME=name, QA_TEXT=project / "猫名.txt", QA_PY=sys.executable, QA_BUILD=skill / "scripts/build_session.py",
                               QA_PAGE=upstream, QA_BODY=layers / "body.png", QA_TAIL=layers / "tail.png", QA_OUT=out)
                sessions.append((out, name, "ja"))
                print(shell + ": constructed a named session through the native shell")

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            check_current_tab(browser, upstream, skill / "assets/current-tab.html", sessions[1][0])
            print("Chromium: replaced-file cancellation and Esc preserve both selections.")
            firefox = playwright.firefox.launch()
            check_current_tab(firefox, upstream, skill / "assets/current-tab.html", sessions[1][0])
            fx = firefox.new_context(offline=True)
            open_session(fx.new_page(), sessions[1][0], sessions[1][1])
            firefox.close()
            print("Firefox: same-tab and standalone sessions passed.")
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
            assert not discover(project, codex_cli)
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
    parser.add_argument("codex_cli", type=Path, help="Path to the npm Codex bin/codex.js launcher")
    args = parser.parse_args()
    main(args.archive.resolve(), args.upstream.resolve(), args.codex_cli.resolve())
