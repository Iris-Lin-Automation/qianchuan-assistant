import asyncio, json, subprocess, wave
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import edge_tts

OUT = Path(r"D:\qianchuan-feishu-analytics\docs\demo_video_90s")
FF = r"C:\\Users\\AA129\\AppData\\Local\\Microsoft\\WinGet\\Packages\\yt-dlp.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\\ffmpeg-N-124716-g054dffd133-win64-gpl\\bin\\ffmpeg.exe"
VOICE = "zh-CN-YunxiNeural"
RATE = "+25%"
W, H = 1080, 1920

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
]

SHOTS = [
    {"id": "01", "img": "shot01.png", "text": "每天早上，经营日报自动进飞书群。", "sub": "每天早上，经营日报自动进飞书群"},
    {"id": "02", "img": "shot02.png", "text": "不用写代码，解压点一下就能用。", "sub": "不用写代码，解压点一下就能用"},
    {"id": "03", "img": "shot03.png", "text": "填一次机器人地址，立刻出卡片。", "sub": "填一次机器人地址，立刻出卡片"},
    {"id": "04", "img": "shot04.png", "text": "图表在操作台点打开经营看板就能看。", "sub": "操作台打开经营看板看图表"},
    {"id": "05", "img": "shot05.png", "text": "需要的老板，私信千川日报开通。", "sub": "私信「千川日报」开通"},
]


def font_path():
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return p
    raise FileNotFoundError("no Chinese font")


def run(cmd):
    print("+", " ".join(str(c) for c in cmd))
    subprocess.check_call(cmd)


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def wrap_text(draw, text, font, max_width):
    lines, cur = [], ""
    for ch in text:
        trial = cur + ch
        if draw.textlength(trial, font=font) <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines or [text]


def make_frame(src: Path, sub: str, dst: Path, fontfile: str):
    im = Image.open(src).convert("RGBA")
    # fit into 1080x1920
    im.thumbnail((W, H), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (W, H), (10, 14, 20, 255))
    canvas.paste(im, ((W - im.width) // 2, (H - im.height) // 2), im)

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = ImageFont.truetype(fontfile, 44)
    bar_top, bar_h = 1560, 260
    draw.rounded_rectangle((36, bar_top, W - 36, bar_top + bar_h), radius=24, fill=(0, 0, 0, 170))
    lines = wrap_text(draw, sub, font, W - 120)
    # vertical center text in bar
    line_h = 58
    total_h = line_h * len(lines)
    y = bar_top + (bar_h - total_h) // 2
    for line in lines:
        tw = draw.textlength(line, font=font)
        x = (W - tw) / 2
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_h

    out = Image.alpha_composite(canvas, overlay).convert("RGB")
    out.save(dst, quality=95)


async def synth(text: str, mp3: Path):
    await edge_tts.Communicate(text, VOICE, rate=RATE).save(str(mp3))


async def main():
    fpath = font_path()
    print("FONT", fpath)
    meta, clips = [], []
    for s in SHOTS:
        frame = OUT / f"fast_frame_{s['id']}.jpg"
        make_frame(OUT / s["img"], s["sub"], frame, fpath)

        mp3 = OUT / f"fast_narr_{s['id']}.mp3"
        wav = OUT / f"fast_narr_{s['id']}.wav"
        await synth(s["text"], mp3)
        run([FF, "-y", "-i", str(mp3), "-ar", "44100", "-ac", "1", str(wav)])
        d = wav_duration(wav)
        hold = d + 0.25
        audio = OUT / f"fast_seg_{s['id']}_a.wav"
        run([
            FF, "-y", "-i", str(wav),
            "-f", "lavfi", "-t", f"{max(0.05, hold - d):.3f}", "-i", "anullsrc=r=44100:cl=mono",
            "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[a]",
            "-map", "[a]", str(audio),
        ])

        clip = OUT / f"fast_seg_{s['id']}.mp4"
        run([
            FF, "-y",
            "-loop", "1", "-i", str(frame),
            "-i", str(audio),
            "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-vf", "fps=30",
            "-t", f"{hold:.3f}",
            "-shortest",
            "-movflags", "+faststart",
            str(clip),
        ])
        meta.append({"id": s["id"], "text": s["text"], "sub": s["sub"], "seconds": round(hold, 2)})
        clips.append(clip)

    lst = OUT / "fast_concat.txt"
    lst.write_text("\n".join(f"file '{c.name}'" for c in clips), encoding="utf-8")
    final = OUT / "千川经营助手_加快版_带字幕.mp4"
    run([
        FF, "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
        "-c:v", "libx264", "-preset", "fast", "-crf", "19",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(final),
    ])
    (OUT / "fast_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("DONE", final)
    print("TOTAL_SEC", round(sum(m["seconds"] for m in meta), 1))


asyncio.run(main())
