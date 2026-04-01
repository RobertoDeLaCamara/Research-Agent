"""
Demo recording script for Research-Agent.
Uses Playwright's built-in video capture (bypasses GPU/compositor issues in WSL2).
Outputs docs/demo.gif via ffmpeg conversion.
"""
import subprocess
import time
import sys
import shutil
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO    = Path(__file__).parent.parent
URL     = "http://localhost:8501"
VID_DIR = Path("/tmp/pw-video")
OUT_GIF = str(REPO / "docs" / "demo.gif")

TOPIC   = "LangGraph multi-agent architectures"
PERSONA = "Arquitecto de Software"
W, H    = 1280, 800


def webm_to_gif(webm_path: Path, gif_path: str):
    palette = "/tmp/palette.png"
    subprocess.run([
        "ffmpeg", "-y", "-i", str(webm_path),
        "-vf", "fps=8,scale=1280:-1:flags=lanczos,palettegen",
        palette,
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(webm_path), "-i", palette,
        "-filter_complex", "fps=8,scale=1280:-1:flags=lanczos[x];[x][1:v]paletteuse",
        gif_path,
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    size = Path(gif_path).stat().st_size / 1024
    print(f"GIF saved → {gif_path}  ({size:.0f} KB)")


def run_demo():
    VID_DIR.mkdir(exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--no-default-browser-check", "--disable-extensions"],
        )
        context = browser.new_context(
            viewport={"width": W, "height": H},
            record_video_dir=str(VID_DIR),
            record_video_size={"width": W, "height": H},
        )
        page = context.new_page()

        try:
            # ── 1. Load the app ───────────────────────────────────────────
            print("Opening Research-Agent...")
            page.goto(URL, wait_until="networkidle", timeout=30000)
            time.sleep(3)

            # ── 2. Type the topic ─────────────────────────────────────────
            print("Typing topic...")
            topic_input = page.get_by_placeholder("Ej. Explainable AI, Docker Orchestration...")
            topic_input.click()
            time.sleep(0.5)
            topic_input.type(TOPIC, delay=70)
            time.sleep(2)

            # ── 3. Select persona ─────────────────────────────────────────
            print("Selecting persona...")
            persona_combo = page.get_by_role("combobox", name="Persona del agente", exact=False)
            persona_combo.click()
            time.sleep(0.5)
            page.get_by_role("option", name=PERSONA).click()
            time.sleep(1.5)

            # ── 4. Start research ─────────────────────────────────────────
            print("Starting research...")
            page.get_by_text("Iniciar Investigación").click()
            time.sleep(2)

            # ── 5. Wait for report ────────────────────────────────────────
            print("Waiting for report (up to 60s)...")
            try:
                page.wait_for_selector("text=Informe", timeout=60000)
                print("  Report appeared!")
            except Exception:
                print("  Timeout — recording current state")
            time.sleep(2)

            # ── 6. Scroll through the report ──────────────────────────────
            print("Scrolling...")
            for _ in range(7):
                page.mouse.wheel(0, 380)
                time.sleep(1.2)

            # ── 7. Pause on export section ────────────────────────────────
            time.sleep(3)

        finally:
            print("Closing browser and saving video...")
            video_path = Path(page.video.path())
            context.close()
            browser.close()

    # Find the recorded webm
    webm = video_path
    if not webm.exists():
        webms = sorted(VID_DIR.glob("*.webm"))
        if not webms:
            print("ERROR: No video file found.")
            sys.exit(1)
        webm = webms[-1]

    print(f"Video recorded: {webm} ({webm.stat().st_size/1024:.0f} KB)")
    print("Converting to GIF...")
    webm_to_gif(webm, OUT_GIF)


if __name__ == "__main__":
    import urllib.request
    try:
        urllib.request.urlopen(f"{URL}/healthz", timeout=5)
    except Exception:
        print(f"ERROR: Streamlit app not running at {URL}")
        sys.exit(1)

    if VID_DIR.exists():
        shutil.rmtree(VID_DIR)

    run_demo()
