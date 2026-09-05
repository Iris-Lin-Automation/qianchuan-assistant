from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT / ".codex_video_deps"
SOURCE = Path(r"C:\Users\AA129\Downloads\千川日报_抖音竖版样片_90秒.mp4")
OUT_DIR = ROOT / "release"
OUTPUT = OUT_DIR / "千川日报_抖音竖版样片_90秒_快节奏版.mp4"
SRT_RAW = OUT_DIR / "千川日报_字幕_原始.srt"
SRT_FAST = OUT_DIR / "千川日报_字幕_快节奏.srt"
SPEED = 1.35


def ffmpeg_exe() -> str:
    sys.path.insert(0, str(DEPS))
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def parse_time(value: str) -> float:
    h, m, rest = value.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def format_time(seconds: float) -> str:
    ms_total = round(seconds * 1000)
    h, rem = divmod(ms_total, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def retime_srt() -> None:
    text = SRT_RAW.read_text(encoding="utf-8-sig")
    pattern = re.compile(
        r"(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})"
    )

    def replace(match: re.Match[str]) -> str:
        start = parse_time(match.group(1)) / SPEED
        end = parse_time(match.group(2)) / SPEED
        return f"{format_time(start)} --> {format_time(end)}"

    SRT_FAST.write_text(pattern.sub(replace, text), encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ffmpeg = ffmpeg_exe()
    run([ffmpeg, "-hide_banner", "-y", "-i", str(SOURCE), "-map", "0:2", str(SRT_RAW)])
    retime_srt()
    run(
        [
            ffmpeg,
            "-hide_banner",
            "-y",
            "-i",
            str(SOURCE),
            "-i",
            str(SRT_FAST),
            "-filter_complex",
            f"[0:v]setpts=PTS/{SPEED},scale=1080:1920:force_original_aspect_ratio=decrease,"
            f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1[v];[0:a]atempo={SPEED}[a]",
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-map",
            "1:0",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-c:s",
            "mov_text",
            "-movflags",
            "+faststart",
            str(OUTPUT),
        ]
    )
    print(f"speed={SPEED} output={OUTPUT}")


if __name__ == "__main__":
    main()
