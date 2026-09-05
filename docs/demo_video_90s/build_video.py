import asyncio, json, subprocess, wave
from pathlib import Path
import edge_tts

OUT = Path(r"D:\qianchuan-feishu-analytics\docs\demo_video_90s")
FF = r"C:\\Users\\AA129\\AppData\\Local\\Microsoft\\WinGet\\Packages\\yt-dlp.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\\ffmpeg-N-124716-g054dffd133-win64-gpl\\bin\\ffmpeg.exe"
VOICE = "zh-CN-YunxiNeural"

SHOTS = [
    {
        "id": "01",
        "img": "shot01.png",
        "text": "每天早上，经营日报自动进飞书群。",
        "target": 8,
    },
    {
        "id": "02",
        "img": "shot02.png",
        "text": "不用写代码，解压点一下就能用。",
        "target": 12,
    },
    {
        "id": "03",
        "img": "shot03.png",
        "text": "填一次机器人地址，立刻出卡片。群里这张卡片，就是早上的经营决策摘要。",
        "target": 25,
    },
    {
        "id": "04",
        "img": "shot04.png",
        "text": "要看图表，在操作台点打开经营看板，本机就会打开可视化页面。",
        "target": 25,
    },
    {
        "id": "05",
        "img": "shot05.png",
        "text": "需要的老板，私信千川日报，按店铺数量报价开通。",
        "target": 20,
    },
]


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


async def synth(text: str, mp3: Path):
    communicate = edge_tts.Communicate(text, VOICE, rate="-5%")
    await communicate.save(str(mp3))


def run(cmd):
    print("+", " ".join(cmd))
    subprocess.check_call(cmd)


async def main():
    meta = []
    for s in SHOTS:
        mp3 = OUT / f"narr_{s['id']}.mp3"
        wav = OUT / f"narr_{s['id']}.wav"
        await synth(s["text"], mp3)
        # normalize to wav for duration measure
        run([FF, "-y", "-i", str(mp3), "-ar", "44100", "-ac", "1", str(wav)])
        d = wav_duration(wav)
        # pad silence so segment matches target timing (stillimage holds)
        hold = max(s["target"], d + 0.6)
        silent_tail = max(0.0, hold - d)
        audio = OUT / f"seg_{s['id']}_a.wav"
        if silent_tail > 0.05:
            run([
                FF, "-y",
                "-i", str(wav),
                "-f", "lavfi", "-t", f"{silent_tail:.3f}", "-i", "anullsrc=r=44100:cl=mono",
                "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[a]",
                "-map", "[a]", str(audio),
            ])
        else:
            run([FF, "-y", "-i", str(wav), str(audio)])

        clip = OUT / f"seg_{s['id']}.mp4"
        run([
            FF, "-y",
            "-loop", "1", "-i", str(OUT / s["img"]),
            "-i", str(audio),
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,format=yuv420p,fps=30",
            "-shortest",
            "-movflags", "+faststart",
            str(clip),
        ])
        meta.append({"id": s["id"], "text": s["text"], "seconds": hold, "file": clip.name})

    # concat list
    lst = OUT / "concat.txt"
    lst.write_text("\n".join(f"file '{m['file']}'" for m in meta), encoding="utf-8")
    final = OUT / "千川经营助手_90秒演示.mp4"
    run([
        FF, "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
        "-c", "copy", str(final),
    ])
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("DONE", final)


asyncio.run(main())
