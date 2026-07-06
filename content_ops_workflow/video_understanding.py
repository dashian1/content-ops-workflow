from __future__ import annotations

import glob
import os
import shutil
import subprocess
import time
from dataclasses import dataclass

from content_ops_workflow.config import SETTINGS


MAX_FRAMES = 36
SCENE_THRESHOLD = 0.30
FPS_FLOOR_SECONDS = 1.0
DEDUP_THRESHOLD = 8.0
DEDUP_WINDOW = 4

TRANSCRIBE_MODEL = os.environ.get("WHISPER_MODEL", "medium")
TRANSCRIBE_LANGUAGE = os.environ.get("WHISPER_LANGUAGE", "zh")
TRANSCRIBE_DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
TRANSCRIBE_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")
TRANSCRIBE_VAD = os.environ.get("WHISPER_VAD", "").strip() == "1"
NO_SPEECH_THRESHOLD = float(os.environ.get("WHISPER_NO_SPEECH_THRESHOLD", "0.75"))
MIN_LOGPROB = float(os.environ.get("WHISPER_MIN_LOGPROB", "-1.2"))

VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}


@dataclass
class VideoPackage:
    package_dir: str
    manifest_path: str
    transcript: str
    transcript_source: str
    transcript_warning: str
    transcript_path: str
    duration: float
    fps: float
    extracted_count: int
    frame_count: int
    frames_dir: str
    audio_path: str


def is_video(path: str) -> bool:
    return os.path.splitext(path or "")[1].lower() in VIDEO_EXTENSIONS


def media_tool(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        os.path.join(SETTINGS.root, "tools", "ffmpeg", "bin", f"{name}.exe"),
        os.path.join(os.path.dirname(SETTINGS.root), "tools", "ffmpeg", "bin", f"{name}.exe"),
        os.path.join(local_app_data, "Microsoft", "WinGet", "Packages", "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe", "ffmpeg-8.1.1-full_build", "bin", f"{name}.exe"),
        os.path.join("C:\\", "ffmpeg", "bin", f"{name}.exe"),
    ]
    winget_root = os.path.join(local_app_data, "Microsoft", "WinGet", "Packages")
    candidates.extend(glob.glob(os.path.join(winget_root, "Gyan.FFmpeg_*", "ffmpeg-*", "bin", f"{name}.exe")))
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return name


def run_tool(cmd: list[str], label: str) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError as exc:
        raise RuntimeError(f"{label}：没有找到 {os.path.basename(cmd[0])}。") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"{label}：{detail[:1200] or '命令执行失败'}")
    return result


def run_frame_command(cmd: list[str], log_path: str) -> None:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError as exc:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"没有找到 {os.path.basename(cmd[0])}")
        raise RuntimeError(f"没有找到 {os.path.basename(cmd[0])}。") from exc
    text = (result.stderr or result.stdout or "").strip()
    if text:
        with open(log_path, "w", encoding="utf-8", errors="replace") as f:
            f.write(text)


def video_duration(path: str) -> float:
    result = run_tool(
        [media_tool("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path],
        "读取视频时长失败",
    )
    raw = result.stdout.strip()
    return float(raw) if raw else 30.0


def video_fps(path: str) -> float:
    result = run_tool(
        [media_tool("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=avg_frame_rate", "-of", "default=nw=1:nk=1", path],
        "读取视频帧率失败",
    )
    raw = result.stdout.strip()
    if "/" in raw:
        left, right = raw.split("/", 1)
        try:
            return float(left) / float(right)
        except (ValueError, ZeroDivisionError):
            return 25.0
    try:
        return float(raw)
    except ValueError:
        return 25.0


def has_audio_stream(path: str) -> bool:
    try:
        result = run_tool(
            [media_tool("ffprobe"), "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=index", "-of", "csv=p=0", path],
            "检测音频失败",
        )
    except RuntimeError:
        return False
    return bool(result.stdout.strip())


def format_timecode(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    minutes = int(seconds // 60)
    remain = seconds - minutes * 60
    return f"{minutes:02d}:{remain:04.1f}"


def extract_audio(video_path: str, package_dir: str) -> str:
    audio_dir = os.path.join(package_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    audio_path = os.path.join(audio_dir, "speech.wav")
    run_tool(
        [media_tool("ffmpeg"), "-y", "-i", video_path, "-map", "0:a:0", "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", audio_path],
        "提取口播音频失败",
    )
    return audio_path


def transcribe_audio(audio_path: str) -> str:
    try:
        from faster_whisper import WhisperModel
    except Exception as exc:
        raise RuntimeError("本机没有可用的 faster-whisper，无法自动提取口播。") from exc
    try:
        model = WhisperModel(
            TRANSCRIBE_MODEL,
            device=TRANSCRIBE_DEVICE,
            compute_type=TRANSCRIBE_COMPUTE_TYPE,
            local_files_only=os.environ.get("WHISPER_ALLOW_DOWNLOAD", "").strip() != "1",
        )
        segments, _info = model.transcribe(
            audio_path,
            language=TRANSCRIBE_LANGUAGE or None,
            vad_filter=TRANSCRIBE_VAD,
            beam_size=5,
            best_of=5,
        )
        lines: list[str] = []
        for segment in segments:
            text = (segment.text or "").strip()
            no_speech = float(getattr(segment, "no_speech_prob", 0.0) or 0.0)
            logprob = float(getattr(segment, "avg_logprob", 0.0) or 0.0)
            if text and no_speech <= NO_SPEECH_THRESHOLD and logprob >= MIN_LOGPROB:
                lines.append(f"[{format_timecode(segment.start)}-{format_timecode(segment.end)}] {text}")
        return "\n".join(lines).strip()
    except Exception as exc:
        raise RuntimeError(f"自动提取口播失败：{exc}") from exc


def prepare_transcript(video_path: str, package_dir: str, manual_transcript: str) -> dict[str, str]:
    transcript_path = os.path.join(package_dir, "transcript.txt")
    manual = (manual_transcript or "").strip()
    if manual:
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(manual)
        return {"text": manual, "source": "manual", "warning": "", "path": transcript_path, "audio_path": ""}
    if not has_audio_stream(video_path):
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write("")
        return {"text": "", "source": "none", "warning": "视频没有检测到音频轨。", "path": transcript_path, "audio_path": ""}
    try:
        audio_path = extract_audio(video_path, package_dir)
        text = transcribe_audio(audio_path)
    except RuntimeError as exc:
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write("")
        return {"text": "", "source": "failed", "warning": str(exc), "path": transcript_path, "audio_path": ""}
    with open(transcript_path, "w", encoding="utf-8") as f:
        f.write(text)
    warning = "" if text else "自动转写完成，但没有识别到有效口播。"
    return {"text": text, "source": f"faster-whisper:{TRANSCRIBE_MODEL}", "warning": warning, "path": transcript_path, "audio_path": audio_path}


def frame_signature(path: str) -> list[tuple[int, int, int]]:
    from PIL import Image

    with Image.open(path) as img:
        img = img.convert("RGB").resize((64, 36))
        return list(img.getdata())


def signature_diff_percent(a: list[tuple[int, int, int]], b: list[tuple[int, int, int]]) -> float:
    if not a or not b or len(a) != len(b):
        return 100.0
    changed = 0
    for left, right in zip(a, b):
        delta = (abs(left[0] - right[0]) + abs(left[1] - right[1]) + abs(left[2] - right[2])) / 3
        if delta > 18:
            changed += 1
    return changed * 100.0 / len(a)


def extract_raw_frames(video_path: str, raw_dir: str, fps: float) -> list[str]:
    os.makedirs(raw_dir, exist_ok=True)
    every_n = max(1, int(fps * FPS_FLOOR_SECONDS))
    out_pattern = os.path.join(raw_dir, "raw_%05d.jpg")
    run_frame_command(
        [
            media_tool("ffmpeg"),
            "-y",
            "-i",
            video_path,
            "-vf",
            f"select='gt(scene,{SCENE_THRESHOLD})+not(mod(n,{every_n}))',scale=720:-1",
            "-vsync",
            "vfr",
            "-q:v",
            "5",
            out_pattern,
        ],
        os.path.join(raw_dir, "extract.log"),
    )
    return sorted(glob.glob(os.path.join(raw_dir, "raw_*.jpg")))


def dedup_frames(raw_frames: list[str], frames_dir: str) -> tuple[list[str], list[dict[str, object]]]:
    os.makedirs(frames_dir, exist_ok=True)
    kept: list[str] = []
    records: list[dict[str, object]] = []
    recent: list[list[tuple[int, int, int]]] = []
    for raw in raw_frames:
        try:
            sig = frame_signature(raw)
        except Exception as exc:
            records.append({"source": os.path.basename(raw), "kept": False, "diff": 0, "reason": str(exc)})
            continue
        diffs = [signature_diff_percent(sig, old) for old in recent[-DEDUP_WINDOW:]]
        min_diff = min(diffs) if diffs else 100.0
        keep = not recent or min_diff >= DEDUP_THRESHOLD
        if keep:
            target = os.path.join(frames_dir, f"frame_{len(kept) + 1:03d}.jpg")
            shutil.copyfile(raw, target)
            kept.append(target)
            recent.append(sig)
        records.append({"source": os.path.basename(raw), "kept": keep, "diff": round(min_diff, 2), "reason": "keep" if keep else "duplicate"})
    if len(kept) > MAX_FRAMES:
        selected_indexes = {int(i * len(kept) / MAX_FRAMES) for i in range(MAX_FRAMES)}
        selected = [path for index, path in enumerate(kept) if index in selected_indexes]
        for path in kept:
            if path not in selected and os.path.exists(path):
                os.remove(path)
        for index, path in enumerate(selected, start=1):
            target = os.path.join(frames_dir, f"frame_{index:03d}.jpg")
            if path != target:
                os.replace(path, target)
        kept = sorted(glob.glob(os.path.join(frames_dir, "frame_*.jpg")))
    return kept, records


def write_manifest(
    package_dir: str,
    video_path: str,
    duration: float,
    fps: float,
    raw_count: int,
    frames: list[str],
    transcript: dict[str, str],
    title: str,
    source_url: str,
    records: list[dict[str, object]],
) -> str:
    manifest = os.path.join(package_dir, "MANIFEST.md")
    lines = [
        "# 内容运营视频理解包",
        "",
        f"- 标题: {title or os.path.splitext(os.path.basename(video_path))[0]}",
        f"- 来源: {source_url or '本地上传'}",
        f"- 视频: {video_path}",
        f"- 时长: {duration:.1f} 秒",
        f"- 帧率: {fps:.2f}",
        f"- 抽取帧: {raw_count}",
        f"- 去重后关键帧: {len(frames)}",
        f"- 抽帧策略: scene-change({SCENE_THRESHOLD}) + density-floor({FPS_FLOOR_SECONDS}s) + sliding-window-dedup({DEDUP_WINDOW})",
        f"- 口播来源: {transcript.get('source', '')}",
    ]
    if transcript.get("warning"):
        lines.append(f"- 口播提示: {transcript['warning']}")
    lines.extend(["", "## 关键帧"])
    for index, frame in enumerate(frames, start=1):
        lines.append(f"{index:03d}. frames/{os.path.basename(frame)}")
    lines.extend(["", "## 口播/字幕", transcript.get("text", "").strip() or "未提供", "", "## 去重记录"])
    for record in records[:180]:
        lines.append(f"- {record['source']} | {'keep' if record['kept'] else 'drop'} | diff={record['diff']} | {record['reason']}")
    with open(manifest, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")
    return manifest


def build_video_package(video_path: str, manual_transcript: str, title: str, source_url: str) -> VideoPackage:
    duration = video_duration(video_path)
    fps = video_fps(video_path)
    name = safe_package_name(title or os.path.splitext(os.path.basename(video_path))[0] or "video")
    package_dir = os.path.join(SETTINGS.output_dir, "video_understanding", time.strftime("%Y-%m-%d"), f"{time.strftime('%H%M%S')}_{name}")
    raw_dir = os.path.join(package_dir, "raw")
    frames_dir = os.path.join(package_dir, "frames")
    os.makedirs(package_dir, exist_ok=True)
    transcript = prepare_transcript(video_path, package_dir, manual_transcript)
    raw_frames = extract_raw_frames(video_path, raw_dir, fps)
    if not raw_frames:
        raise RuntimeError("没有成功抽取视频关键帧，请确认 ffmpeg 可用且视频可播放。")
    frames, records = dedup_frames(raw_frames, frames_dir)
    if not frames:
        raise RuntimeError("抽帧后全部被判定为重复画面。")
    manifest = write_manifest(package_dir, video_path, duration, fps, len(raw_frames), frames, transcript, title, source_url, records)
    return VideoPackage(
        package_dir=package_dir,
        manifest_path=manifest,
        transcript=transcript.get("text", ""),
        transcript_source=transcript.get("source", ""),
        transcript_warning=transcript.get("warning", ""),
        transcript_path=transcript.get("path", ""),
        duration=duration,
        fps=fps,
        extracted_count=len(raw_frames),
        frame_count=len(frames),
        frames_dir=frames_dir,
        audio_path=transcript.get("audio_path", ""),
    )


def safe_package_name(text: str) -> str:
    text = "".join("_" if ch in '\\/:*?"<>|\r\n\t' else ch for ch in text)
    text = "_".join(text.split()).strip("._ ")
    return text[:80] or "video"

