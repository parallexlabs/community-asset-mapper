#!/usr/bin/env python3
"""Regenerate showcase docs, images, and demo video from built demo outputs."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import textwrap
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
FFMPEG = os.environ.get("FFMPEG") or shutil.which("ffmpeg") or "ffmpeg"
EXIFTOOL = os.environ.get("EXIFTOOL") or shutil.which("exiftool") or "exiftool"
DOCS = ROOT / "docs"
MEDIA = DOCS / "media"
SHOWCASE_MEDIA = ROOT / "showcase-media"
DEMO_WORK = ROOT / ".cam" / "demo"
DIST = ROOT / "dist"


def run(cmd: list[str], **kwargs: object) -> None:
    subprocess.run(cmd, check=True, cwd=ROOT, **kwargs)


def ensure_demo_outputs() -> None:
    if not (DEMO_WORK / "state.json").is_file():
        raise SystemExit("Run cam run-demo first (or ensure .cam/demo/state.json exists).")
    if not DIST.joinpath("index.html").is_file():
        run([sys.executable, str(ROOT / "scripts" / "build_dist_from_state.py")])


def sync_docs_site() -> None:
    ensure_demo_outputs()
    for name in ("index.html", "services.csv", "data-licences.md"):
        shutil.copy2(DIST / name, DOCS / name)
    assets_src = DIST / "assets"
    assets_dst = DOCS / "assets"
    if assets_dst.exists():
        shutil.rmtree(assets_dst)
    shutil.copytree(assets_src, assets_dst)


def chrome_screenshot(
    url: str,
    dest: Path,
    width: int = 1400,
    height: int = 900,
    budget_ms: int = 8000,
) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            CHROME,
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--hide-scrollbars",
            f"--window-size={width},{height}",
            f"--virtual-time-budget={budget_ms}",
            f"--screenshot={dest}",
            url,
        ]
    )


def step_html(name: str, extra_script: str) -> Path:
    steps_dir = MEDIA / "steps"
    steps_dir.mkdir(parents=True, exist_ok=True)
    html = (DOCS / "index.html").read_text(encoding="utf-8")
    inject = f"<script>{extra_script}</script>"
    if "</body>" in html:
        html = html.replace("</body>", inject + "\n</body>", 1)
    else:
        html += inject
    path = steps_dir / name
    path.write_text(html, encoding="utf-8")
    return path


def capture_page_screenshots() -> list[Path]:
    MEDIA.mkdir(parents=True, exist_ok=True)
    base = (DOCS / "index.html").resolve().as_uri()
    hero = MEDIA / "hero.png"
    chrome_screenshot(base, hero)

    table = MEDIA / "example-table.png"
    chrome_screenshot(base, table, height=1200)

    filtered_page = step_html(
        "filtered.html",
        "window.addEventListener('load', () => {"
        "const city = document.getElementById('filter-city');"
        "city.value = 'Vancouver';"
        "city.dispatchEvent(new Event('input', {bubbles: true}));"
        "});",
    )
    filtered = MEDIA / "example-filtered.png"
    chrome_screenshot(filtered_page.resolve().as_uri(), filtered)

    popup_page = step_html(
        "popup.html",
        "window.addEventListener('load', () => {"
        "const btn = document.querySelector('button[data-feature=\"0\"]');"
        "if (btn) btn.click();"
        "});",
    )
    popup = MEDIA / "example-map-popup.png"
    chrome_screenshot(popup_page.resolve().as_uri(), popup, budget_ms=10000)

    quality_page = DEMO_WORK / "quality_backlog.md"
    quality_copy = MEDIA / "quality_backlog.md"
    shutil.copy2(quality_page, quality_copy)
    csv_shot = MEDIA / "example-quality-backlog.png"
    chrome_screenshot(quality_copy.resolve().as_uri(), csv_shot, height=900)

    return [hero, table, filtered, popup, csv_shot]


def svg_to_png(svg_path: Path, png_path: Path) -> Path:
    chrome_screenshot(svg_path.resolve().as_uri(), png_path, width=1000, height=520, budget_ms=2000)
    return png_path


def chart_gap_rates() -> Path:
    gap = json.loads((DEMO_WORK / "gap_report.json").read_text(encoding="utf-8"))
    ids = [m["geography_id"][-4:] for m in gap["metrics"]]
    counts = [m["service_count"] for m in gap["metrics"]]
    rates = [m["rate_per_1000"] for m in gap["metrics"]]
    max_count = max(counts) or 1
    bars = []
    for index, (label, count, rate) in enumerate(zip(ids, counts, rates, strict=True)):
        x = 60 + index * 110
        bar_h = 180 * count / max_count
        bars.append(f'<rect x="{x}" y="{300 - bar_h}" width="70" height="{bar_h}" fill="#005fcc"/>')
        bars.append(f'<text x="{x}" y="320" font-size="12">{label}</text>')
        bars.append(f'<text x="{x}" y="{280 - bar_h}" font-size="12" fill="#005fcc">{count}</text>')
        bars.append(f'<circle cx="{x + 35}" cy="{250 - bar_h - rate * 80}" r="5" fill="#c45c00"/>')
    svg = MEDIA / "chart-gap-rates.svg"
    svg.write_text(
        textwrap.dedent(
            f"""<svg xmlns="http://www.w3.org/2000/svg" width="900" height="360">
            <rect width="100%" height="100%" fill="white"/>
            <text x="20" y="28" font-size="16">Gap metrics from bundled demo (illustrative)</text>
            {''.join(bars)}
            <text x="20" y="350" font-size="12" fill="#555">
            Bars: service count. Orange dots: rate per 1000 residents.</text>
            </svg>"""
        ),
        encoding="utf-8",
    )
    return svg_to_png(svg, MEDIA / "chart-gap-rates.png")


def chart_quality_rules() -> Path:
    backlog = json.loads((DEMO_WORK / "quality_backlog.json").read_text(encoding="utf-8"))
    counts = Counter(item["rule"] for item in backlog["issues"])
    rules = list(counts.keys())
    values = [counts[r] for r in rules]
    max_val = max(values) or 1
    rows = []
    for index, (rule, value) in enumerate(zip(rules, values, strict=True)):
        y = 50 + index * 34
        bar_w = 420 * value / max_val
        rows.append(f'<text x="20" y="{y + 14}" font-size="13">{rule}</text>')
        rows.append(f'<rect x="220" y="{y}" width="{bar_w}" height="18" fill="#2a6f3a"/>')
        rows.append(f'<text x="{230 + bar_w}" y="{y + 14}" font-size="13">{value}</text>')
    svg = MEDIA / "chart-quality-rules.svg"
    svg.write_text(
        textwrap.dedent(
            f"""<svg xmlns="http://www.w3.org/2000/svg" width="820" height="320">
            <rect width="100%" height="100%" fill="white"/>
            <text x="20" y="28" font-size="16">
            Quality backlog rules ({backlog['issue_count']} issues, demo)</text>
            {''.join(rows)}
            </svg>"""
        ),
        encoding="utf-8",
    )
    return svg_to_png(svg, MEDIA / "chart-quality-rules.png")


def chart_architecture() -> Path:
    steps = ["Import", "Validate", "Geocode", "Dedup", "Gap", "Quality", "Export", "Site"]
    parts = []
    x = 20
    for index, label in enumerate(steps):
        parts.append(f'<rect x="{x}" y="70" width="95" height="44" fill="#eef3fa" stroke="#333"/>')
        parts.append(f'<text x="{x + 8}" y="98" font-size="13">{label}</text>')
        if index < len(steps) - 1:
            parts.append(f'<line x1="{x + 95}" y1="92" x2="{x + 115}" y2="92" stroke="#333"/>')
            parts.append(f'<polygon points="{x + 115},92 {x + 107},87 {x + 107},97" fill="#333"/>')
        x += 117
    svg = MEDIA / "diagram-architecture.svg"
    svg.write_text(
        textwrap.dedent(
            f"""<svg xmlns="http://www.w3.org/2000/svg" width="980" height="160">
            <rect width="100%" height="100%" fill="white"/>
            <text x="20" y="28" font-size="16">Pipeline components (demo)</text>
            {''.join(parts)}
            </svg>"""
        ),
        encoding="utf-8",
    )
    return svg_to_png(svg, MEDIA / "diagram-architecture.png")


def strip_image_metadata(paths: list[Path]) -> None:
    if not paths:
        return
    if Path(EXIFTOOL).is_file():
        run([EXIFTOOL, "-all=", "-overwrite_original", *[str(p) for p in paths]])


def write_vtt(cues: list[tuple[str, str, str]], path: Path) -> None:
    lines = ["WEBVTT", ""]
    for start, end, text in cues:
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def build_demo_video(step_images: list[Path]) -> None:
    SHOWCASE_MEDIA.mkdir(parents=True, exist_ok=True)
    MEDIA.mkdir(parents=True, exist_ok=True)
    cues = [
        ("00:00:00.000", "00:00:05.000", "Map and table built from illustrative demo services."),
        ("00:00:05.000", "00:00:10.000", "Scroll to the service directory table and CSV download."),
        ("00:00:10.000", "00:00:15.000", "Filter by city; the map markers update with the table."),
        ("00:00:15.000", "00:00:20.000", "Open a service on the map from the table."),
        ("00:00:20.000", "00:00:25.000", "Exported HSDS package folder from the same demo run."),
        ("00:00:25.000", "00:00:30.000", "Gap rates and service counts by dissemination area."),
        ("00:00:30.000", "00:00:35.000", "Quality backlog counts grouped by rule."),
        ("00:00:35.000", "00:00:40.000", "Pipeline from import through static site output."),
    ]
    vtt = MEDIA / "demo.en.vtt"
    write_vtt(cues[: len(step_images)], vtt)

    silent = SHOWCASE_MEDIA / "demo-silent.mp4"
    cmd: list[str] = [FFMPEG, "-y"]
    for image in step_images:
        cmd.extend(["-loop", "1", "-t", "5", "-i", str(image.resolve())])
    scale_parts = [
        f"[{i}:v]scale=1400:900:force_original_aspect_ratio=decrease,"
        f"pad=1400:900:(ow-iw)/2:(oh-ih)/2,setsar=1[v{i}]"
        for i in range(len(step_images))
    ]
    concat_in = "".join(f"[v{i}]" for i in range(len(step_images)))
    n = len(step_images)
    filter_complex = ";".join(scale_parts) + f";{concat_in}concat=n={n}:v=1:a=0[outv]"
    cmd.extend(
        [
            "-filter_complex",
            filter_complex,
            "-map",
            "[outv]",
            "-r",
            "30",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(silent),
        ]
    )
    run(cmd)

    captioned = SHOWCASE_MEDIA / "demo-captioned.mp4"
    vtt_rel = vtt.relative_to(ROOT).as_posix().replace(":", "\\:")
    run(
        [
            FFMPEG,
            "-y",
            "-i",
            str(silent),
            "-vf",
            f"subtitles={vtt_rel}:force_style='FontSize=22,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,BorderStyle=3'",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(captioned),
        ]
    )

    demo_mp4 = SHOWCASE_MEDIA / "demo.mp4"
    shutil.copy2(captioned, demo_mp4)
    stripped = SHOWCASE_MEDIA / "demo-stripped.mp4"
    run([FFMPEG, "-y", "-i", str(demo_mp4), "-map_metadata", "-1", "-c", "copy", str(stripped)])
    shutil.move(SHOWCASE_MEDIA / "demo-stripped.mp4", demo_mp4)

    poster = MEDIA / "demo-poster.png"
    run([FFMPEG, "-y", "-i", str(demo_mp4), "-frames:v", "1", str(poster)])

    preview = MEDIA / "demo-preview.gif"
    run(
        [
            FFMPEG,
            "-y",
            "-i",
            str(demo_mp4),
            "-vf",
            "fps=8,scale=700:-1:flags=lanczos",
            "-loop",
            "0",
            str(preview),
        ]
    )


def main() -> None:
    sync_docs_site()
    shots = capture_page_screenshots()
    charts = [chart_gap_rates(), chart_quality_rules(), chart_architecture()]
    strip_image_metadata(shots + charts)
    video_steps = shots[:5] + charts
    build_demo_video(video_steps)
    strip_image_metadata([MEDIA / "demo-poster.png"])
    print("Showcase media refreshed under docs/media/ and showcase-media/demo.mp4")


if __name__ == "__main__":
    main()
