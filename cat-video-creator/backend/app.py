import os
import sys
import uuid
import json
import shutil
import contextlib
from contextlib import asynccontextmanager
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List

import asyncio
from collections import defaultdict
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.background import BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


ROOT = Path(__file__).resolve().parents[1]
# Ensure a unified output directory for all generators
DEFAULT_OUTPUT_DIR = (ROOT / "output").resolve()
os.environ.setdefault("VIDEOHELPER_OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR))
DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
# Vendored copies live under backend/vendors/
# Use the current file's directory to locate the vendors folder reliably.
VENDOR_ROOT = Path(__file__).resolve().parent / "vendors"
MONEYPRINTER_BACKEND = VENDOR_ROOT / "moneyprinter"
BRAINROT_ROOT = VENDOR_ROOT / "brainrot"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context to manage background broadcaster task."""
    global MAIN_LOOP
    MAIN_LOOP = asyncio.get_running_loop()

    async def _broadcast_loop():
        while True:
            try:
                job_id, payload = await ASYNC_QUEUE.get()
            except asyncio.CancelledError:
                # Exit cleanly on shutdown
                break
            subscribers = list(WS_SUBSCRIBERS.get(job_id, set()))
            if not subscribers:
                continue
            dead = []
            for ws in subscribers:
                try:
                    await ws.send_json(payload)
                except Exception:
                    dead.append(ws)
            # Cleanup dead sockets
            for ws in dead:
                try:
                    WS_SUBSCRIBERS[job_id].discard(ws)
                except Exception:
                    pass

    broadcaster_task = asyncio.create_task(_broadcast_loop())
    try:
        yield
    finally:
        broadcaster_task.cancel()
        # In Python 3.12+ asyncio.CancelledError may not inherit from Exception
        with contextlib.suppress(Exception, asyncio.CancelledError):
            await broadcaster_task


app = FastAPI(title="Cat Video Creator API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class MoneyPrinterRequest(BaseModel):
    videoSubject: str
    aiModel: str = "gemini-2.0-flash"
    paragraphNumber: int = 1
    threads: Optional[int] = None
    subtitlesPosition: str = "center,bottom"
    color: str = "#FFFF00"
    useMusic: bool = False
    zipUrl: Optional[str] = None
    automateYoutubeUpload: bool = False
    useGPU: bool = True
    voice: str = "af_bella"
    customPrompt: Optional[str] = None


class BrainrotRequest(BaseModel):
    youtubeUrl: str
    numCompilations: int = 1
    minDuration: int = 60
    maxDuration: int = 110
    maxReuse: int = 3


JOBS: Dict[str, Dict[str, Any]] = {}
JOBS_FILE = DEFAULT_OUTPUT_DIR / "jobs.json"
JOBS_LOCK = threading.Lock()
JOB_CONTROLS: Dict[str, Dict[str, Any]] = {}

# WebSocket pub-sub for job updates
WS_SUBSCRIBERS: Dict[str, set] = defaultdict(set)
ASYNC_QUEUE: "asyncio.Queue[tuple[str, Dict[str, Any]]]" = asyncio.Queue()
MAIN_LOOP: "asyncio.AbstractEventLoop | None" = None

def _enqueue_job_update(job_id: str) -> None:
    """Thread-safe enqueue of a job update for websocket broadcast."""
    global MAIN_LOOP
    try:
        payload: Dict[str, Any]
        with JOBS_LOCK:
            payload = dict(JOBS.get(job_id, {}))
        if MAIN_LOOP is not None:
            MAIN_LOOP.call_soon_threadsafe(ASYNC_QUEUE.put_nowait, (job_id, payload))
    except Exception:
        # Best-effort only
        pass


def _load_jobs_from_disk() -> None:
    if JOBS_FILE.exists():
        try:
            data = json.loads(JOBS_FILE.read_text("utf-8"))
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, dict):
                        # Mark previously running jobs as stale after restart
                        if v.get("status") == "running":
                            v["status"] = "stale"
                            v["step"] = "stale"
                        JOBS[k] = v
        except Exception:
            pass


def _save_jobs_to_disk() -> None:
    try:
        with JOBS_LOCK:
            JOBS_FILE.write_text(json.dumps(JOBS, indent=2), encoding="utf-8")
    except Exception:
        pass


def _update_job(job_id: str, **fields: Any) -> None:
    with JOBS_LOCK:
        job = JOBS.get(job_id, {})
        job.update(fields)
        JOBS[job_id] = job
    _save_jobs_to_disk()
    _enqueue_job_update(job_id)


def _check_cancel(job_id: str) -> None:
    ctrl = JOB_CONTROLS.get(job_id)
    if ctrl and ctrl.get("cancel") and ctrl["cancel"].is_set():
        raise RuntimeError("cancelled")


# Load persisted jobs at import time
_load_jobs_from_disk()


@contextlib.contextmanager
def pushd(path: Path):
    prev = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)


def ensure_on_path(path: Path):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "cwd": str(Path.cwd()),
        "root": str(ROOT),
        "moneyprinter_present": MONEYPRINTER_BACKEND.exists(),
        "brainrot_present": BRAINROT_ROOT.exists(),
    }


@app.post("/api/moneyprinter/generate")
def moneyprinter_generate(req: MoneyPrinterRequest):
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {"status": "running", "step": "init", "result": None, "error": None, "logs": []}
    JOB_CONTROLS[job_id] = {"cancel": threading.Event()}
    _save_jobs_to_disk()
    _enqueue_job_update(job_id)

    def _log_job(message: str) -> None:
        try:
            with JOBS_LOCK:
                job = JOBS.get(job_id, {})
                logs = job.get("logs")
                if not isinstance(logs, list):
                    logs = []
                logs.append(message)
                job["logs"] = logs
                JOBS[job_id] = job
        finally:
            # Always persist log updates
            _save_jobs_to_disk()
            _enqueue_job_update(job_id)

    def _run_job():
        try:
            ensure_on_path(MONEYPRINTER_BACKEND)
            with pushd(MONEYPRINTER_BACKEND):
                # Lazy imports from vendored MoneyPrinter project
                from vendors.moneyprinter.utils import fetch_songs, check_env_vars
                from vendors.moneyprinter.gpt import generate_script, get_search_terms
                from vendors.moneyprinter.search import search_for_stock_videos
                from vendors.moneyprinter.tiktokvoice import tts
                from vendors.moneyprinter.video import generate_subtitles, combine_videos, generate_video
                from vendors.moneyprinter.video import save_video as mp_save_video
                from moviepy import AudioFileClip, CompositeAudioClip, VideoFileClip, concatenate_audioclips  # type: ignore

                _update_job(job_id, step="validate_env")
                _log_job("validate_env: checking MoneyPrinter environment variables")
                try:
                    check_env_vars()
                except SystemExit:
                    raise RuntimeError("Missing required MoneyPrinter environment variables")

                _check_cancel(job_id)
                if req.useMusic and req.zipUrl:
                    _update_job(job_id, step="fetch_music")
                    _log_job(f"fetch_music: downloading songs from zipUrl={req.zipUrl}")
                    fetch_songs(req.zipUrl)

                _check_cancel(job_id)
                _update_job(job_id, step="script_generation")
                _log_job(f"script_generation: model={req.aiModel} voice={req.voice} paragraphs={req.paragraphNumber}")
                script = generate_script(req.videoSubject, req.paragraphNumber, req.aiModel, req.voice, req.customPrompt or "")
                if not script:
                    raise RuntimeError("Script generation failed")

                _check_cancel(job_id)
                _update_job(job_id, step="search_terms")
                terms = get_search_terms(req.videoSubject, 10, script, req.aiModel)
                _log_job(f"search_terms: {len(terms)} terms -> {terms[:5]}{'...' if len(terms) > 5 else ''}")

                _check_cancel(job_id)
                _update_job(job_id, step="stock_download")
                voice_prefix = req.voice

                # Download several videos per term locally, filter by duration >= 4
                video_paths: list[str] = []
                for term in terms:
                    urls = search_for_stock_videos(term, os.getenv("PEXELS_API_KEY", ""), 5, 4)
                    for url in urls[:2]:
                        _check_cancel(job_id)
                        try:
                            local_path = mp_save_video(url, directory="../temp")
                            video_paths.append(local_path)
                        except Exception:
                            continue
                if not video_paths:
                    raise RuntimeError("No stock videos downloaded")
                else:
                    _log_job(f"stock_download: downloaded {len(video_paths)} clips")

                _check_cancel(job_id)
                _update_job(job_id, step="tts")
                _log_job(f"tts: generating {len([s for s in script.split('. ') if s])} audio segments using voice={voice_prefix}")
                sentences = [s for s in script.split(". ") if s]
                audio_clips = []
                temp_dir = Path("../temp")
                temp_dir.mkdir(exist_ok=True)
                for s in sentences:
                    _check_cancel(job_id)
                    current_tts_path = temp_dir / f"{uuid.uuid4()}.mp3"
                    tts(s, req.voice, filename=str(current_tts_path))
                    audio_clips.append(AudioFileClip(str(current_tts_path)))

                if not audio_clips:
                    raise RuntimeError("No audio clips generated")

                tts_path = str(temp_dir / f"{uuid.uuid4()}.mp3")
                concatenate_audioclips(audio_clips).write_audiofile(tts_path)
                _log_job(f"tts: concatenated audio -> {tts_path}")

                _check_cancel(job_id)
                _update_job(job_id, step="subtitles")
                subtitles_path = generate_subtitles(audio_path=tts_path, sentences=sentences, audio_clips=audio_clips, voice=voice_prefix)
                try:
                    sp = Path(subtitles_path)
                    head = ""
                    if sp.exists():
                        with sp.open("r", encoding="utf-8", errors="ignore") as fh:
                            # Read first ~3 lines to help debug format
                            for _ in range(3):
                                line = fh.readline()
                                if not line:
                                    break
                                head += line.strip() + " | "
                    _log_job(f"subtitles: path={subtitles_path} exists={sp.exists()} size={sp.stat().st_size if sp.exists() else 'n/a'} head={head[:200]}")
                except Exception as e:
                    _log_job(f"subtitles: failed to inspect file ({e})")

                _check_cancel(job_id)
                _update_job(job_id, step="compose_video")
                _log_job(
                    f"compose_video: threads={req.threads or 2} useGPU={req.useGPU} color={req.color or '#FFFF00'} position={req.subtitlesPosition}"
                )
                temp_audio = AudioFileClip(tts_path)
                combined_video_path = combine_videos(video_paths, int(temp_audio.duration), 5, req.threads or 2, req.useGPU)
                _log_job(f"compose_video: combined video -> {combined_video_path}")

                # Log environment versions helpful for font/TextClip issues
                try:
                    import platform  # type: ignore
                    import moviepy  # type: ignore
                    from PIL import Image, ImageFont, __version__ as PIL_VERSION  # type: ignore
                    _log_job(
                        f"env: python={platform.python_version()} moviepy={getattr(moviepy, '__version__', 'unknown')} pillow={PIL_VERSION}"
                    )
                    _log_job(f"PIL ImageFont module file={getattr(ImageFont, '__file__', 'unknown')}")
                except Exception as e:
                    _log_job(f"env: failed to get version info ({e})")

                try:
                    final_video_path = generate_video(
                        combined_video_path,
                        tts_path,
                        subtitles_path or "",
                        req.threads or 2,
                        req.subtitlesPosition,
                        req.color or "#FFFF00",
                        req.useGPU,
                    )
                except Exception as ge:
                    import traceback
                    tb = traceback.format_exc()
                    _log_job(f"compose_video: generate_video failed: {ge}")
                    _log_job(f"traceback: {tb}")
                    raise

                # Optional background music
                if req.useMusic:
                    _check_cancel(job_id)
                    from vendors.moneyprinter.utils import choose_random_song
                    song_path = choose_random_song()
                    codec_settings = {"codec": "h264_nvenc" if req.useGPU else "libx264", "audio_codec": "aac"}
                    video_clip_path = Path(str(final_video_path))
                    if not video_clip_path.is_absolute():
                        video_clip_path = Path("..") / str(final_video_path)
                    video_clip = VideoFileClip(str(video_clip_path))
                    original_duration = video_clip.duration
                    original_audio = video_clip.audio
                    song_clip = AudioFileClip(song_path).with_fps(44100).with_volume_scaled(0.1)
                    comp_audio = CompositeAudioClip([original_audio, song_clip])
                    video_clip = (
                        video_clip
                        .with_audio(comp_audio)
                        .with_fps(30)
                        .with_duration(original_duration)
                    )
                    video_clip.write_videofile(str(video_clip_path), threads=req.threads or 1, **codec_settings)

                if not JOB_CONTROLS[job_id]["cancel"].is_set():
                    _log_job(f"done: final video -> {final_video_path}")
                    _update_job(job_id, status="done", result={"output": str(final_video_path), "subtitles": subtitles_path})
        except Exception as e:
            if str(e) == "cancelled":
                _update_job(job_id, status="cancelled", error="cancelled")
            else:
                # Preserve the last known step in the error and include a hint if it's a font/TextClip issue
                hint = ""
                msg = str(e)
                if any(k in msg.lower() for k in ["font", "pillow", "textclip"]):
                    hint = " (possible font/Pillow/TextClip configuration issue)"
                _log_job(f"error: {msg}{hint}")
                _update_job(job_id, status="error", error=msg)

    # Run the long-running job in a detached daemon thread rather than Starlette BackgroundTasks.
    # This avoids noisy asyncio.CancelledError tracebacks on server shutdown (Ctrl+C)
    # when Starlette awaits background tasks during request teardown.
    threading.Thread(target=_run_job, name=f"moneyprinter-job-{job_id}", daemon=True).start()
    return {"status": "queued", "jobId": job_id}


class SuggestSubjectRequest(BaseModel):
    aiModel: str | None = None
    examples: list[str] | None = None
    topicHint: str | None = None


@app.post("/api/moneyprinter/suggest-subject")
def suggest_subject(req: SuggestSubjectRequest) -> Dict[str, str]:
    """Suggest a short content subject using Gemini.

    Returns a JSON object: {"subject": "..."}
    """
    ensure_on_path(MONEYPRINTER_BACKEND)
    with pushd(MONEYPRINTER_BACKEND):
        try:
            from vendors.moneyprinter.gpt import generate_response  # type: ignore
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to initialize Gemini backend: {e}")

    examples = req.examples or [
        "Good foods for cats",
        "How to calm your dog",
        "How to fix a broken pipe",
    ]
    hint = (req.topicHint or "").strip()

    prompt_lines = [
        "Suggest one short, catchy subject for a short-form video.",
        "- 3 to 6 words.",
        "- No quotes, no emojis, minimal punctuation.",
        "- Return ONLY the subject text.",
        "",
        "Examples:",
    ]
    prompt_lines += [f"- {e}" for e in examples if e]
    if hint:
        prompt_lines += ["", f"Topic hint: {hint}"]
    prompt = "\n".join(prompt_lines)

    try:
        model = req.aiModel or "gemini-2.0-flash"
        raw = generate_response(prompt, model)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini request failed: {e}")

    text = (raw or "").strip().splitlines()[0] if raw else ""
    # light cleanup: drop surrounding quotes and trailing punctuation
    text = text.strip().strip('"\'').strip()
    if text.endswith(('.', '!', '?')):
        text = text[:-1].strip()
    if not text:
        raise HTTPException(status_code=502, detail="Empty subject from model")
    return {"subject": text}

@app.get("/api/models")
def list_models() -> Dict[str, List[str]]:
    """List available Gemini models (static list; can be swapped to dynamic)."""
    # Use a curated list compatible with current SDK; replace with API discovery if desired
    models = [
        "gemini-2.0-flash",
        "gemini-2.0-pro-exp",
        "gemini-2.0-pro",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        "gemini-2.0-flash-lite",
    ]
    return {"models": models}


@app.get("/api/voices")
def list_voices() -> Dict[str, List[str]]:
    """Expose Kokoro voices used by the AI video workflow."""
    ensure_on_path(MONEYPRINTER_BACKEND)
    with pushd(MONEYPRINTER_BACKEND):
        from vendors.moneyprinter.tiktokvoice import list_voices as kokoro_voices  # type: ignore
        return {"voices": kokoro_voices()}


@app.get("/api/voice-sample")
def voice_sample(voice: str, text: Optional[str] = None):
    """Generate and return a short MP3 sample for a given voice.

    Query params:
      - voice: Voice id from Kokoro voices
      - text: Optional custom sample text
    """
    ensure_on_path(MONEYPRINTER_BACKEND)
    # Load TTS functions within moneyprinter context
    with pushd(MONEYPRINTER_BACKEND):
        try:
            from vendors.moneyprinter.tiktokvoice import tts, list_voices as kokoro_voices  # type: ignore
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to load TTS backend: {e}")

    voices = set(kokoro_voices())
    if voice not in voices:
        raise HTTPException(status_code=400, detail="Invalid voice")

    # Use a stable absolute temp path under vendors/temp
    temp_dir = (VENDOR_ROOT / "temp").resolve()
    temp_dir.mkdir(parents=True, exist_ok=True)
    target = (temp_dir / f"voice_sample_{voice}.mp3").resolve()
    sample_text = text or "This is a short sample of this voice."

    # If no custom text requested and a sample already exists, reuse it
    if text is None and target.exists() and target.is_file() and target.stat().st_size > 0:
        return FileResponse(str(target), filename=target.name, media_type="audio/mpeg")

    try:
        # Call TTS with absolute output path
        with pushd(MONEYPRINTER_BACKEND):
            tts(sample_text, voice, filename=str(target))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {e}")

    return FileResponse(str(target), filename=target.name, media_type="audio/mpeg")


@app.post("/api/brainrot/generate")
def brainrot_generate(req: BrainrotRequest):
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {"status": "running", "step": "init", "result": None, "error": None}
    JOB_CONTROLS[job_id] = {"cancel": threading.Event()}
    _save_jobs_to_disk()
    _enqueue_job_update(job_id)

    def _run_job():
        try:
            ensure_on_path(BRAINROT_ROOT)
            with pushd(BRAINROT_ROOT):
                from tikyou_video_generator.generator import TikYouGenerator  # type: ignore

                _check_cancel(job_id)
                _update_job(job_id, step="process_video")
                unified_output_dir = os.getenv("VIDEOHELPER_OUTPUT_DIR")
                if unified_output_dir:
                    output_dir = str(Path(unified_output_dir).resolve())
                else:
                    output_dir = str((ROOT / "brainrot_output").resolve())
                Path(output_dir).mkdir(parents=True, exist_ok=True)

                generator = TikYouGenerator(output_dir=output_dir)
                video_clips = generator.process_single_video(req.youtubeUrl)
                if not video_clips:
                    raise RuntimeError("No clips generated from source video")

                _check_cancel(job_id)
                _update_job(job_id, step="generate_compilations")
                generator.generate_tikyou_videos(
                    req.youtubeUrl,
                    num_compilations=req.numCompilations,
                    min_duration=req.minDuration,
                    max_duration=req.maxDuration,
                )

                if not JOB_CONTROLS[job_id]["cancel"].is_set():
                    _update_job(job_id, status="done", result={"output_dir": output_dir})
        except Exception as e:
            if str(e) == "cancelled":
                _update_job(job_id, status="cancelled", error="cancelled")
            else:
                _update_job(job_id, status="error", error=str(e))

    # Run the job in a detached daemon thread to avoid shutdown cancellation noise
    threading.Thread(target=_run_job, name=f"brainrot-job-{job_id}", daemon=True).start()
    return {"status": "queued", "jobId": job_id}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    ctrl = JOB_CONTROLS.get(job_id)
    if not ctrl:
        raise HTTPException(status_code=404, detail="Job not found")
    ctrl["cancel"].set()
    _update_job(job_id, status="cancelled")
    return {"status": "cancelled", "jobId": job_id}


@app.websocket("/ws/jobs/{job_id}")
async def websocket_job_updates(websocket: WebSocket, job_id: str):
    await websocket.accept()
    # Add to subscribers
    WS_SUBSCRIBERS[job_id].add(websocket)
    # Send the current job state immediately if exists
    try:
        initial = JOBS.get(job_id)
        if initial is not None:
            await websocket.send_json(initial)
    except Exception:
        pass
    try:
        # Keep the connection open; simple ping-pong to detect disconnect
        while True:
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                break
            except Exception:
                # Ignore malformed frames; continue until disconnect
                await asyncio.sleep(0.5)
    finally:
        try:
            WS_SUBSCRIBERS[job_id].discard(websocket)
        except Exception:
            pass


 


def _is_allowed_path(p: Path) -> bool:
    p_resolved = p.resolve()
    allowed_roots = [DEFAULT_OUTPUT_DIR.resolve(), (ROOT / "brainrot_output").resolve()]
    for root in allowed_roots:
        try:
            if p_resolved.is_relative_to(root):
                return True
        except Exception:
            # Fallback for older Python versions or edge cases
            if str(p_resolved).startswith(str(root) + os.sep):
                return True
    return False


@app.get("/api/download")
def download_file(path: str):
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    if not _is_allowed_path(file_path):
        raise HTTPException(status_code=403, detail="Access denied")
    media_type = "application/octet-stream"
    if file_path.suffix.lower() == ".mp4":
        media_type = "video/mp4"
    return FileResponse(str(file_path), filename=file_path.name, media_type=media_type)


@app.get("/api/list-videos")
def list_videos(dir: str):
    """List mp4 videos inside a directory under the allowed output roots.

    Returns a JSON object: { "files": [{"path": str, "name": str, "size": int, "mtime": float}] }
    """
    directory = Path(dir)
    if not directory.exists() or not directory.is_dir():
        raise HTTPException(status_code=404, detail="Directory not found")
    if not _is_allowed_path(directory):
        raise HTTPException(status_code=403, detail="Access denied")

    files = []
    try:
        for p in sorted(directory.glob("*.mp4")):
            try:
                stat = p.stat()
                files.append({
                    "path": str(p.resolve()),
                    "name": p.name,
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                })
            except Exception:
                continue
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list videos: {e}")

    return {"files": files}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8080, reload=True)


