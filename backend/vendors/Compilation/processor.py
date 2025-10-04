"""
Cat Video Processor (Backend) - Clean implementation.
See repository history for previous verbose version. This version eliminates
duplicate method definitions and adds manual explicit cleanup.
"""

from __future__ import annotations

import os, sys, re, time, shutil, logging, subprocess
from pathlib import Path
from typing import List, Tuple, Dict, Any
import cv2  # type: ignore
import numpy as np  # type: ignore
from scenedetect import open_video, SceneManager  # type: ignore
from scenedetect.detectors import ContentDetector  # type: ignore
from moviepy import VideoFileClip  # type: ignore
from moviepy.video.tools.cuts import detect_scenes  # type: ignore

logger = logging.getLogger("backend.compilation.processor")

class SimpleScene:
    def __init__(self, start_time: float, end_time: float):
        self.start_time = start_time; self.end_time = end_time
    def get_seconds(self) -> float: return self.start_time

def clean_text_for_filename(text: str) -> str:
    cleaned = re.sub(r'[^\w\s-]', '', text); cleaned = re.sub(r'\s+', '_', cleaned.strip()); return cleaned[:50]

class CatVideoProcessor:
    def __init__(self, output_dir: str = "final_videos", ffmpeg_path: str | None = None,
                 crop_verbose: bool | None = None, crop_debug_frames: bool | None = None,
                 enable_yolo: bool | None = None):
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
        try:
            from utils.ffmpeg_utils import setup_ffmpeg_environment  # type: ignore
            setup_ffmpeg_environment()
        except Exception:
            logger.warning("FFmpeg environment setup skipped")
        os.environ.setdefault("FFMPEG_7_COMPAT", "1"); os.environ.setdefault("FFMPEG_DISABLE_SHOW_FORMAT", "1")
        self.output_dir = output_dir; Path(self.output_dir).mkdir(exist_ok=True)
        self.ffmpeg_path = ffmpeg_path or os.getenv('FFMPEG_PATH') or shutil.which('ffmpeg') or 'ffmpeg'
        if crop_verbose is None: crop_verbose = os.getenv("CROP_VERBOSE", "0") == "1"
        if crop_debug_frames is None: crop_debug_frames = os.getenv("CROP_DEBUG_FRAMES", "0") == "1"
        if enable_yolo is None: enable_yolo = os.getenv("CROP_ENABLE_YOLO", "1") != "0"
        self.crop_verbose = crop_verbose; self.crop_debug_frames = crop_debug_frames; self.enable_yolo = enable_yolo
        self._yolo_model=None; self._yolo_device=None; self._protected_files: List[str] = []
        self.check_dependencies()

    # ------------------------------------------------------------------
    # Dependency / environment
    # ------------------------------------------------------------------
    def _crop_log(self, msg: str, always: bool = False):
        if always or self.crop_verbose: print(msg)

    def check_dependencies(self) -> bool:
        try: subprocess.run([self.ffmpeg_path, '-version'], capture_output=True, text=True, timeout=5)
        except Exception: logger.warning("ffmpeg missing at %s", self.ffmpeg_path)
        return True

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------
    def download_video(self, video_id: str, max_retries: int = 5):
        logger.info("Downloading video %s", video_id)
        try:
            from utils.youtube import download_video as unified_download  # type: ignore
            out_dir = os.path.join(self.output_dir, video_id); url=f"https://www.youtube.com/watch?v={video_id}"
            result = unified_download(url, out_dir, max_retries=max_retries)
            res = getattr(result,'resolution',None)
            if res and isinstance(res,(tuple,list)) and len(res)==2:
                w,h=res; print(f"✅ Downloaded {video_id}: {w}x{h}, duration={getattr(result,'duration','?')}s")
            return result.video_path, getattr(result,'title',video_id)
        except Exception as e:  # noqa
            print(f"Download error for {video_id}: {e}"); return None, None

    # ------------------------------------------------------------------
    # Basic info helpers
    # ------------------------------------------------------------------
    def get_video_duration(self, video_path: str) -> float:
        try:
            r=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',video_path], capture_output=True, text=True, timeout=5)
            if r.returncode==0 and r.stdout.strip(): return float(r.stdout.strip())
        except Exception: pass
        return 0.0

    def get_video_info(self, video_path: str) -> Dict[str, Any] | None:
        try:
            ffprobe=os.environ.get('FFPROBE_BINARY','ffprobe')
            base=subprocess.run([ffprobe,'-v','error',video_path], capture_output=True, text=True, timeout=3)
            if base.returncode!=0: return None
            r=subprocess.run([ffprobe,'-v','error','-show_entries','stream=width,height,duration,r_frame_rate,codec_name,codec_type','-of','json',video_path], capture_output=True, text=True, timeout=7)
            if r.returncode==0:
                import json
                data=json.loads(r.stdout or '{}'); streams=data.get('streams') if isinstance(data.get('streams'),list) else []
                vs=next((s for s in streams if s.get('codec_type')=='video'), None)
                if vs:
                    def _safe(v, cast, default):
                        try: return cast(v) if v not in (None,'N/A') else default
                        except Exception: return default
                    width=_safe(vs.get('width'),int,0); height=_safe(vs.get('height'),int,0); duration=_safe(vs.get('duration'),float,0.0)
                    fps_str=vs.get('r_frame_rate','30/1')
                    try: num,den=fps_str.split('/'); fps=float(num)/float(den) if float(den)!=0 else 30.0
                    except Exception: fps=30.0
                    return {'duration':duration,'width':width,'height':height,'fps':fps,'codec':vs.get('codec_name','unknown')}
        except Exception: pass
        try:
            cap=cv2.VideoCapture(video_path)
            if cap.isOpened():
                w=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); h=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)); fps=cap.get(cv2.CAP_PROP_FPS) or 30.0; frames=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); dur=frames/fps if fps>0 else 0.0; cap.release(); return {'duration':dur,'width':w,'height':h,'fps':fps,'codec':'unknown'}
        except Exception: pass
        return None

    def get_video_orientation(self, info: Dict[str, Any] | None) -> str:
        if not info: return 'unknown'
        w=info.get('width',0); h=info.get('height',0)
        if not w or not h: return 'unknown'
        ar=w/h
        if ar>1.2: return 'horizontal'
        if ar<0.8: return 'vertical'
        return 'square'

    # ------------------------------------------------------------------
    # Pillarbox detection methods
    # ------------------------------------------------------------------
    def detect_pillarboxes_edge_detection(self, video_path: str, sample_frames: int = 10) -> Tuple[int, int]:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return 0, 0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_indices = np.linspace(0, max(total_frames - 1, 0), sample_frames, dtype=int)
        left_bounds = []
        right_bounds = []
        for idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            vert = np.sum(edges, axis=0)
            thr = np.max(vert) * 0.3 if np.max(vert) > 0 else 0
            lb = 0
            for x in range(width // 4):
                win = vert[max(0, x - 5):min(width, x + 5)]
                if np.mean(win) > thr:
                    lb = x
                    break
            rb = width - 1
            for x in range(width - 1, width * 3 // 4, -1):
                win = vert[max(0, x - 5):min(width, x + 5)]
                if np.mean(win) > thr:
                    rb = x
                    break
            left_bounds.append(lb)
            right_bounds.append(width - rb - 1)
        cap.release()
        if not left_bounds:
            return 0, 0
        import statistics
        return int(statistics.median(left_bounds)), int(statistics.median(right_bounds))

    def detect_pillarboxes_transition_based(self, video_path: str, sample_frames: int = 10) -> Tuple[int, int]:
        return self.detect_pillarboxes_edge_detection(video_path, sample_frames)

    def detect_pillarboxes_yolov8(self, video_path: str, sample_frames: int = 10) -> Tuple[int, int]:
        if not self.enable_yolo:
            return 0, 0
        try:
            from ultralytics import YOLO  # type: ignore
            import torch  # type: ignore
        except Exception:
            return self.detect_pillarboxes_transition_based(video_path, sample_frames)
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return 0, 0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        idxs = np.linspace(0, max(total - 1, 0), sample_frames, dtype=int)
        if self._yolo_model is None:
            model_name = os.getenv("CROP_YOLO_MODEL", "yolov8n.pt")
            try:
                self._yolo_model = YOLO(model_name)
                self._yolo_device = 'cuda' if torch.cuda.is_available() else 'cpu'
                self._yolo_model.to(self._yolo_device)
            except Exception:
                cap.release(); return self.detect_pillarboxes_transition_based(video_path, sample_frames)
        all_boxes = []
        for i in idxs:
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = cap.read()
            if not ret:
                continue
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            try:
                res = self._yolo_model(rgb, verbose=False)
                boxes = res[0].boxes.xyxy.cpu().numpy() if len(res) > 0 and hasattr(res[0], 'boxes') else []
                for b in boxes:
                    all_boxes.append((b[0], b[2]))
            except Exception:
                pass
        cap.release()
        if not all_boxes:
            return self.detect_pillarboxes_transition_based(video_path, sample_frames)
        min_x = min(b[0] for b in all_boxes)
        max_x = max(b[1] for b in all_boxes)
        pad = int(width * 0.05)
        left = max(0, int(min_x) - pad)
        right = min(width, int(max_x) + pad)
        l = left
        r = width - right
        if abs(l - r) < width * 0.05:
            avg = (l + r) // 2
            l = r = avg
        return l, r

    # ------------------------------------------------------------------
    # Cropping
    # ------------------------------------------------------------------
    def crop_video_if_vertical_with_blur(self, video_path: str) -> str:
        if not os.path.exists(video_path):
            return video_path
        info = self.get_video_info(video_path)
        if not info:
            return video_path
        w = info.get('width', 0)
        h = info.get('height', 0)
        if h >= w:
            return video_path  # Already vertical or square
        left, right = self.detect_pillarboxes_edge_detection(video_path)
        if left == 0 and right == 0:
            left, right = self.detect_pillarboxes_yolov8(video_path)
            if left == 0 and right == 0:
                left, right = self.detect_pillarboxes_transition_based(video_path)
        crop_width = w - left - right
        if crop_width <= 0 or left + right < max(w * 0.1, 60):
            return video_path
        new_ratio = crop_width / h if h else 1
        orig_ratio = w / h if h else 1
        if new_ratio >= orig_ratio * 0.85 or new_ratio > 1.5:
            return video_path
        out_path = video_path.replace('.mp4', '_cropped.mp4')
        cmd = [self.ffmpeg_path, '-y', '-i', video_path, '-filter:v', f'crop={crop_width}:{h}:{left}:0',
               '-c:v', 'libx264', '-preset', 'fast', '-c:a', 'copy', '-avoid_negative_ts', 'make_zero', out_path]
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if os.path.exists(out_path) and os.path.getsize(out_path) > 1024:
                return out_path
        except Exception:
            pass
        return video_path

    # ------------------------------------------------------------------
    # Splitting
    # ------------------------------------------------------------------
    def split_video_with_ffmpeg(self, video_path: str, start_time: float, end_time: float, output_path: str) -> bool:
        try:
            if not os.path.exists(self.ffmpeg_path):
                return False
            if not os.path.exists(video_path):
                return os.path.exists(output_path)  # Assume already produced
            duration = max(0.01, end_time - start_time)
            copy_cmd = [self.ffmpeg_path, '-y', '-loglevel', 'error', '-ss', str(start_time), '-i', video_path,
                        '-t', str(duration), '-c:v', 'copy', '-c:a', 'copy', '-avoid_negative_ts', 'make_zero',
                        '-fflags', '+genpts', '-start_at_zero', '-err_detect', 'ignore_err', output_path]
            r = subprocess.run(copy_cmd, capture_output=True, text=True)
            if (r.returncode != 0) or (not os.path.exists(output_path)) or os.path.getsize(output_path) < 1024:
                if os.path.exists(output_path):
                    try:
                        os.remove(output_path)
                    except OSError:
                        pass
                enc_cmd = [self.ffmpeg_path, '-y', '-loglevel', 'error', '-i', video_path, '-ss', str(start_time),
                           '-t', str(duration), '-c:v', 'libx264', '-c:a', 'aac', '-preset', os.getenv('SPLIT_ENCODE_PRESET', 'fast'),
                           '-crf', os.getenv('SPLIT_ENCODE_CRF', '23'), '-pix_fmt', 'yuv420p', '-movflags', 'faststart',
                           '-avoid_negative_ts', 'make_zero', '-fflags', '+genpts', '-start_at_zero', '-err_detect', 'ignore_err', output_path]
                r = subprocess.run(enc_cmd, capture_output=True, text=True)
            return r.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1024
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Scene detection
    # ------------------------------------------------------------------
    def analyze_video_scenes(self, video_path: str, threshold: float = 17.0, method: str = 'scenedetect') -> Dict[str, Any]:
        if method.lower() == 'moviepy':
            return self.analyze_video_scenes_moviepy(video_path, 10 if threshold == 17.0 else int(threshold))
        try:
            video = open_video(video_path)
            sm = SceneManager(); sm.add_detector(ContentDetector(threshold=threshold))
            sm.detect_scenes(video, show_progress=False)
            scene_list = sm.get_scene_list()
            dur = self.get_video_duration(video_path)
            spm = len(scene_list) / (dur / 60) if dur > 0 else 0
            is_comp = len(scene_list) > 5 and spm > 3 if dur > 0 else len(scene_list) > 5
            return {
                'scenes': scene_list,
                'is_compilation': is_comp,
                'duration': dur,
                'scenes_per_minute': spm,
                'scene_count': len(scene_list),
                'method': 'scenedetect'
            }
        except Exception as e:  # noqa
            return {'scenes': [], 'is_compilation': False, 'duration': 0, 'scenes_per_minute': 0, 'scene_count': 0, 'method': 'scenedetect', 'error': str(e)}

    def analyze_video_scenes_moviepy(self, video_path: str, luminosity_threshold: int = 10) -> Dict[str, Any]:
        try:
            with VideoFileClip(video_path) as clip:
                cuts, _ = detect_scenes(clip=clip, luminosity_threshold=luminosity_threshold, logger=None)
                scene_list = [(SimpleScene(s, s), SimpleScene(e, e)) for s, e in cuts]
                dur = clip.duration
                spm = len(scene_list) / (dur / 60) if dur > 0 else 0
            is_comp = len(scene_list) > 5 and spm > 3 if dur > 0 else len(scene_list) > 5
            return {
                'scenes': scene_list,
                'is_compilation': is_comp,
                'duration': dur,
                'scenes_per_minute': spm,
                'scene_count': len(scene_list),
                'method': 'moviepy'
            }
        except Exception as e:  # noqa
            return {'scenes': [], 'is_compilation': False, 'duration': 0, 'scenes_per_minute': 0, 'scene_count': 0, 'method': 'moviepy', 'error': str(e)}

    # ------------------------------------------------------------------
    # Splitting from scenes
    # ------------------------------------------------------------------
    def split_video_from_scenes(self, video_path: str, source_video_id: str, scene_list) -> Tuple[str, List[Dict[str, Any]]]:
        backend_dir = Path(__file__).resolve().parent.parent.parent.parent
        temp_dir = backend_dir / "temp_vertical"
        os.makedirs(temp_dir, exist_ok=True)
        if not os.path.exists(video_path):
            print(f"❌ Source video missing: {video_path}")
            return str(temp_dir), []
        try:
            initial_size = os.path.getsize(video_path)
            print(f"🎬 Splitting {len(scene_list)} scenes from {video_path} ({initial_size} bytes)")
        except Exception:
            return str(temp_dir), []
        protected = None
        try:
            import uuid
            protected = os.path.join(str(temp_dir), f"working_{source_video_id}_{uuid.uuid4().hex[:8]}.mp4")
            shutil.copy2(video_path, protected)
            if os.path.getsize(protected) != initial_size:
                print("Working copy size mismatch; using original")
                protected = None
            else:
                self._protected_files.append(protected)
        except Exception as e:  # noqa
            print(f"Working copy failed: {e}")
            protected = None
        working = protected or video_path
        prepared = []
        for idx, (s, e) in enumerate(scene_list):
            try:
                st = s.get_seconds(); et = e.get_seconds()
                if et - st < 0.5:
                    continue
                prepared.append((idx, st, et))
            except Exception:
                continue
        try:
            concurrency = max(1, min(int(os.getenv("SCENE_SPLIT_CONCURRENCY", "1")), 6))
        except ValueError:
            concurrency = 1
        if concurrency > 1 and len(prepared) > 2:
            print(f"⚙️  Parallel splitting (workers={concurrency})")
        else:
            concurrency = 1
        from concurrent.futures import ThreadPoolExecutor, as_completed
        def _do(idx, s, e):
            sc = idx + 1
            out = os.path.join(str(temp_dir), f"{source_video_id}-Scene-{sc:03d}.mp4")
            if os.path.exists(out) and os.path.getsize(out) > 1024:
                return sc, out, True, s, e
            ok = self.split_video_with_ffmpeg(working, s, e, out)
            return sc, out, ok, s, e
        results = []; failed = []
        if concurrency > 1:
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                fmap = {pool.submit(_do, i, s, e): (i, s, e) for i, s, e in prepared}
                for fut in as_completed(fmap):
                    i, s, e = fmap[fut]
                    try:
                        results.append(fut.result())
                    except Exception as ex:
                        failed.append((i + 1, f"Exception: {ex}"))
        else:
            for i, s, e in prepared:
                results.append(_do(i, s, e))
        results.sort(key=lambda r: r[0])
        valid = []
        for sc, out, ok, s, e in results:
            if not ok or not os.path.exists(out):
                failed.append((sc, f"Failed split {s:.1f}-{e:.1f}s")); continue
            try:
                size = os.path.getsize(out)
                print(f"✅ Scene {sc} created: {os.path.basename(out)} ({size} bytes)")
            except OSError as er:
                failed.append((sc, f"File access error: {er}")); continue
            time.sleep(0.02)
            info = self.get_video_info(out)
            if not (info and info.get('duration') and info['duration'] >= 3.0):
                continue
            valid.append((sc, out, info, s, e))
        clips = []
        for sc, out, info, s, e in valid:
            print(f"🔍 Detecting pillarboxes on scene {sc}...")
            cropped = self.crop_video_if_vertical_with_blur(out)
            if cropped != out:
                print(f"✅ Scene {sc} cropped: {os.path.basename(out)} -> {os.path.basename(cropped)}")
                out = cropped
            else:
                print(f"ℹ️  No pillarboxes detected on scene {sc}")
            clips.append({
                'path': out,
                'duration': info['duration'],
                'orientation': self.get_video_orientation(info),
                'scene_number': sc,
                'start_time': s,
                'end_time': e
            })
        print("📊 Scene splitting summary:")
        print(f"   Total scenes: {len(scene_list)}")
        print(f"   Successfully processed: {len(clips)}")
        print(f"   Failed: {len(failed)}")
        if failed:
            print("⚠️  Failures:")
            for sc, msg in failed:
                print(f"   Scene {sc}: {msg}")
        if protected and os.path.exists(protected):
            print(f"🕒 Deferred cleanup: protected working copy retained at {protected}")
        print(f"✅ Generated {len(clips)} valid clips from {source_video_id}")
        return str(temp_dir), clips

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------
    def is_compilation_video(self, video_path: str, method: str = 'scenedetect') -> bool:
        analysis = self.analyze_video_scenes(video_path, method=method)
        return analysis.get('is_compilation', False)

    def download_and_split(self, video_id: str, sensitivity: float = 30.0, method: str = 'scenedetect') -> List[Dict[str, Any]]:
        vid = self.download_video(video_id)
        if not vid or vid[0] is None:
            print(f"Download failed for {video_id}")
            return []
        video_path, title = vid
        try:
            analysis = self.analyze_video_scenes(video_path, threshold=sensitivity, method=method)
            scenes = analysis.get('scenes', [])
            if not scenes:
                info = self.get_video_info(video_path)
                dur = info.get('duration', 0) if info else 0
                return [{
                    'path': video_path,
                    'duration': dur,
                    'orientation': self.get_video_orientation(info),
                    'scene_number': 1,
                    'title': title,
                    'start_time': 0.0,
                    'end_time': dur
                }]
            _temp_dir, clips = self.split_video_from_scenes(video_path, video_id, scenes)
            if os.path.exists(video_path):
                print(f"🕒 Deferred cleanup: original video retained {video_path}")
            return clips
        except Exception as e:  # noqa
            print(f"Processing error {video_id}: {e}")
            info = self.get_video_info(video_path)
            dur = info.get('duration', 0) if info else 0
            return [{
                'path': video_path,
                'duration': dur,
                'orientation': self.get_video_orientation(info),
                'scene_number': 1,
                'title': title,
                'start_time': 0.0,
                'end_time': dur
            }]

    # ------------------------------------------------------------------
    # Manual cleanup API (safe explicit removal)
    # ------------------------------------------------------------------
    def manual_cleanup(self, include_scenes: bool = False) -> Dict[str, Any]:
        """Explicitly remove protected working copies (and optionally scene clips).

        Args:
            include_scenes: If True, also remove generated scene clip files.
        Returns:
            dict summary of removed counts.
        """
        removed = []
        # Remove protected working copies
        for f in list(self._protected_files):
            if os.path.exists(f):
                try:
                    os.remove(f)
                    removed.append(f)
                except OSError:
                    pass
            try:
                self._protected_files.remove(f)
            except ValueError:
                pass
        scene_removed = []
        if include_scenes:
            backend_dir = Path(__file__).resolve().parent.parent.parent.parent
            temp_dir = backend_dir / "temp_vertical"
            if temp_dir.exists():
                for p in temp_dir.glob("*-Scene-*.mp4"):
                    try:
                        sz = p.stat().st_size
                        os.remove(p)
                        scene_removed.append((str(p), sz))
                    except OSError:
                        pass
        return {
            'protected_removed': len(removed),
            'scene_files_removed': len(scene_removed),
            'scene_bytes_freed': sum(sz for _, sz in scene_removed)
        }

    def detect_blurred_pillarboxes(self, video_path, sample_frames=10, variance_threshold=50):
        """
        Detect blurred pillarboxes by analyzing texture variance and color consistency.
        Works better for blurred/gradual transitions than sharp black bars.
        
        Args:
            video_path: Path to the video file
            sample_frames: Number of frames to sample for detection
            variance_threshold: Texture variance threshold (lower = more uniform)
        
        Returns:
            tuple: (left_crop, right_crop) - pixels to crop from each side
        """
        print(f"[Blurred Detection] Starting with variance_threshold={variance_threshold}")
        
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        print(f"[Blurred Detection] Video: {width}x{height}, {total_frames} frames")
        
        frame_indices = np.linspace(0, total_frames - 1, sample_frames, dtype=int)
        
        left_boundaries = []
        right_boundaries = []
        
        for i, frame_idx in enumerate(frame_indices):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            
            if not ret:
                continue
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Calculate texture variance for each column
            variances = []
            for x in range(width):
                column = gray[:, x]
                # Use local variance to detect texture
                variance = np.var(column.astype(np.float64))
                variances.append(variance)
            
            variances = np.array(variances)
            
            # Smooth the variance curve to reduce noise
            try:
                from scipy.ndimage import gaussian_filter1d
                smoothed_variances = gaussian_filter1d(variances, sigma=8)  # More smoothing
            except ImportError:
                # Fallback: larger moving average if scipy not available
                smoothed_variances = np.convolve(variances, np.ones(15)/15, mode='same')
            
            # More sophisticated boundary detection
            # Find peaks in variance that indicate content boundaries
            max_var = np.max(smoothed_variances)
            mean_var = np.mean(smoothed_variances)
            
            # More conservative dynamic threshold
            dynamic_threshold = max(variance_threshold * 0.7, float(mean_var * 0.6))
            
            # Look for the main content region by finding the largest high-variance region
            # This helps avoid detecting noise as content boundaries
            
            # Find all regions above threshold
            high_var_regions = smoothed_variances > dynamic_threshold
            
            # Find start and end of the largest continuous region
            if np.any(high_var_regions):
                # Find all continuous regions
                diff = np.diff(np.concatenate(([False], high_var_regions, [False])).astype(int))
                starts = np.where(diff == 1)[0]
                ends = np.where(diff == -1)[0]
                
                if len(starts) > 0 and len(ends) > 0:
                    # Find the largest region
                    region_sizes = ends - starts
                    largest_region_idx = np.argmax(region_sizes)
                    
                    left_boundary = starts[largest_region_idx]
                    right_boundary = ends[largest_region_idx] - 1
                    
                    # Add some padding to avoid cutting into content
                    padding = max(5, width // 100)
                    left_boundary = max(0, left_boundary - padding)
                    right_boundary = min(width - 1, right_boundary + padding)
                else:
                    left_boundary = 0
                    right_boundary = width - 1
            else:
                left_boundary = 0
                right_boundary = width - 1
            
            left_boundaries.append(left_boundary)
            right_boundaries.append(width - right_boundary - 1)
            
            if i == 0:  # Debug info for first frame
                print(f"[Blurred Detection] Frame {frame_idx}: max_var={max_var:.2f}, mean_var={mean_var:.2f}, threshold={dynamic_threshold:.2f}")
                print(f"[Blurred Detection] Frame {frame_idx}: left_boundary={left_boundary}, right_boundary={right_boundary}")
        
        cap.release()
        
        # Filter outliers before taking median
        left_boundaries = np.array(left_boundaries)
        right_boundaries = np.array(right_boundaries)
        
        # Remove extreme outliers (beyond 2 standard deviations)
        if len(left_boundaries) > 3:  # Only filter if we have enough samples
            left_mean = np.mean(left_boundaries)
            left_std = np.std(left_boundaries)
            left_mask = np.abs(left_boundaries - left_mean) <= 2 * left_std
            left_boundaries = left_boundaries[left_mask]
            
            right_mean = np.mean(right_boundaries)
            right_std = np.std(right_boundaries)
            right_mask = np.abs(right_boundaries - right_mean) <= 2 * right_std
            right_boundaries = right_boundaries[right_mask]
        
        # Use median values for robustness
        left_crop = int(np.median(left_boundaries)) if len(left_boundaries) > 0 else 0
        right_crop = int(np.median(right_boundaries)) if len(right_boundaries) > 0 else 0
        
        # Additional validation: ensure we're not cropping too much
        if left_crop + right_crop > width * 0.7:
            print(f"[Blurred Detection] WARNING: Would crop {left_crop + right_crop}px of {width}px, reducing...")
            # Scale down proportionally
            scale_factor = (width * 0.6) / (left_crop + right_crop)
            left_crop = int(left_crop * scale_factor)
            right_crop = int(right_crop * scale_factor)
        
        print(f"[Blurred Detection] All boundaries: left={list(left_boundaries)}, right={list(right_boundaries)}")
        print(f"[Blurred Detection] Final result: left_crop={left_crop}, right_crop={right_crop}")
        
        return left_crop, right_crop