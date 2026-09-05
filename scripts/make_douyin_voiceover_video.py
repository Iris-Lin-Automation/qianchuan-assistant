from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT / ".codex_video_deps"
SOURCE = Path(r"E:\video\7月29日.mp4")
OUT_DIR = ROOT / "release"
VOICE_TEXT_FILE = OUT_DIR / "7月29日_口播文案.txt"
VOICE = OUT_DIR / "7月29日_口播.wav"
ASS = OUT_DIR / "7月29日_高级字幕.ass"
OUTPUT = OUT_DIR / "7月29日_抖音竖版_专业口播版.mp4"
TARGET_SECONDS = 63.44


VOICE_TEXT = """
很多老板不是不懂数据，是没时间每天登录抖店、千川，对表、算数、再判断。
今天看一套结果：电脑到点自动算完，手机飞书群，直接收到经营日报。
指标、评级、异常预警和操作建议，一张卡片就能看清楚。

客户这边不用敲任何代码。
把交付包解压，双击一键安装依赖，等它显示安装完成就行。
已经装过依赖的客户，这一步可以直接跳过。

然后双击启动控制台，操作台会自动弹出来。
第一次只需要保存一次飞书群机器人地址，后面就不用反复配置。

点一下立即推送日报，系统会读取数据，自动生成经营摘要。
早上老板打开飞书群，先看这张决策卡片，就知道今天该盯什么。

如果要看趋势图，就回到操作台，点打开经营看板。
图表会在本机打开，更稳定，也更适合看消耗、GMV、ROI 和账户变化。

这套交付包含开箱软件、飞书配置协助和影刀对接指导。
想要同款自动日报，私信：千川日报。
""".strip()


ASS_EVENTS = [
    (0.0, 4.0, "Top", "结果先给老板看"),
    (0.4, 5.1, "Sub", "很多老板不是不懂数据，是没时间每天登录抖店、千川对表。"),
    (5.1, 10.6, "Sub", "今天看一套：电脑到点自动算完，手机飞书群直接收到经营日报。"),
    (10.6, 17.6, "Sub", "指标、评级、异常预警和操作建议，一张卡片就能看清楚。"),
    (17.6, 20.0, "Hint", "经营日报 | 飞书群自动推送"),
    (20.0, 23.0, "Top", "开箱安装"),
    (20.4, 25.8, "Sub", "客户这边不用敲任何代码。解压，双击一键安装依赖。"),
    (25.8, 30.8, "Sub", "等它显示安装完成就行。已装过依赖的，这一步可以跳过。"),
    (30.8, 34.5, "Top", "启动操作台"),
    (31.0, 36.6, "Sub", "然后双击启动控制台，操作台会自动弹出来。"),
    (36.6, 43.6, "Sub", "第一次只需要保存一次飞书群机器人地址，后面不用反复配置。"),
    (43.6, 47.0, "Top", "一键推送日报"),
    (44.0, 50.8, "Sub", "点一下立即推送日报，系统读取数据，自动生成经营摘要。"),
    (50.8, 55.6, "Sub", "早上老板打开飞书群，先看这张决策卡片。"),
    (55.6, 58.4, "Top", "图表在本机看"),
    (55.8, 61.2, "Sub", "要看趋势图，回到操作台，点打开经营看板。"),
    (58.4, 63.2, "Hint", "飞书卡片不直接打开本地文件，图表统一在操作台打开，更稳定。"),
    (61.2, 63.4, "Sub", "想要同款自动日报，私信：千川日报。"),
]


def ffmpeg_exe() -> str:
    sys.path.insert(0, str(DEPS))
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def make_voice() -> None:
    VOICE_TEXT_FILE.write_text(VOICE_TEXT, encoding="utf-8")
    ps = f"""
$text = Get-Content -Path '{VOICE_TEXT_FILE}' -Raw -Encoding UTF8
$voice = New-Object -ComObject SAPI.SpVoice
$voice.Voice = $voice.GetVoices() | Where-Object {{ $_.GetDescription() -like '*Huihui*Chinese*' }} | Select-Object -First 1
$voice.Rate = 5
$voice.Volume = 100
$stream = New-Object -ComObject SAPI.SpFileStream
$stream.Open('{VOICE}', 3, $false)
$voice.AudioOutputStream = $stream
$voice.Speak($text) | Out-Null
$stream.Close()
"""
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)


def ass_time(seconds: float) -> str:
    cs = round(seconds * 100)
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def ass_escape(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace(":", "\\:")


def make_ass() -> None:
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub, Microsoft YaHei UI, 50, &H00FFFFFF, &H00FFFFFF, &H7A000000, &HC0000000, -1, 0, 0, 0, 100, 100, 0, 0, 3, 2, 0, 2, 84, 84, 150, 1
Style: Top, Microsoft YaHei UI, 48, &H00F7F7F7, &H00FFFFFF, &H85000000, &HB8000000, -1, 0, 0, 0, 100, 100, 0, 0, 3, 1, 0, 8, 96, 96, 86, 1
Style: Hint, Microsoft YaHei UI, 32, &H00DCE7F7, &H00FFFFFF, &H90000000, &HA822242A, 0, 0, 0, 0, 100, 100, 0, 0, 3, 1, 0, 2, 100, 100, 84, 1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    rows = []
    for start, end, style, text in ASS_EVENTS:
        rows.append(
            f"Dialogue: 0,{ass_time(start)},{ass_time(end)},{style},,0,0,0,,{text}"
        )
    ASS.write_text(header + "\n".join(rows) + "\n", encoding="utf-8-sig")


def render() -> None:
    ffmpeg = ffmpeg_exe()
    vf = (
        "[0:v]setpts=PTS,scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,gblur=sigma=28,eq=brightness=-0.12:saturation=0.8[bg];"
        "[0:v]scale=1030:-2:force_original_aspect_ratio=decrease,setsar=1,"
        "pad=1030:588:(ow-iw)/2:(oh-ih)/2:color=0x111318[fg];"
        "[bg][fg]overlay=(W-w)/2:285,"
        "drawbox=x=0:y=0:w=iw:h=192:color=0x090B10@0.68:t=fill,"
        "drawbox=x=0:y=1528:w=iw:h=392:color=0x090B10@0.58:t=fill,"
        f"subtitles='{ass_escape(ASS)}'[v]"
    )
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-y",
            "-i",
            str(SOURCE),
            "-i",
            str(VOICE),
            "-filter_complex",
            vf,
            "-map",
            "[v]",
            "-map",
            "1:a",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "19",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(OUTPUT),
        ],
        check=True,
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    make_voice()
    make_ass()
    render()
    print(OUTPUT)


if __name__ == "__main__":
    main()
