"""
PodcastClips Debug UI

Interactive Gradio interface for visualizing and debugging PodcastClips video generation.
Allows step-by-step inspection, parameter tuning, and regeneration of processing steps.

Usage:
    python debug_ui.py <job_id>
    python debug_ui.py <job_id> <output_dir>
"""

import gradio as gr
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import pandas as pd
from loguru import logger as loguru_logger
import requests

# Setup logger
logger = loguru_logger.bind(name="PodcastClips.debug_ui")


def fetch_available_models(backend_url: str = "http://localhost:9000") -> List[str]:
    """
    Fetch available AI models from the backend API.

    Args:
        backend_url: Base URL of the backend API

    Returns:
        List of available model names
    """
    fallback_models = [
        "gemini-2.0-flash",
        "gemini-2.0-pro-exp",
        "gemini-2.0-pro",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        "gemini-2.0-flash-lite"
    ]

    try:
        response = requests.get(f"{backend_url}/api/AIvideos/models", timeout=5)
        if response.status_code == 200:
            data = response.json()
            models = data.get("models", fallback_models)
            logger.info(f"Fetched {len(models)} AI models from backend")
            return models
        else:
            logger.warning(f"Backend API returned {response.status_code}, using fallback models")
            return fallback_models
    except Exception as e:
        logger.warning(f"Failed to fetch models from backend: {e}, using fallback")
        return fallback_models


class DebugUIState:
    """Manages state for the debug UI"""

    def __init__(self, job_id: str, output_dir: str):
        self.job_id = job_id
        self.output_dir = Path(output_dir)
        self.artifacts_dir = self.output_dir / "artifacts"
        self.debug_dir = self.artifacts_dir / "debug"

        # Create debug directory if it doesn't exist
        self.debug_dir.mkdir(parents=True, exist_ok=True)

        # Cache for loaded artifacts
        self._artifact_cache: Dict[str, Any] = {}

    def clear_cache(self, artifact_path: Optional[str] = None):
        """Clear artifact cache.

        Args:
            artifact_path: Specific artifact to clear, or None to clear all
        """
        if artifact_path:
            self._artifact_cache.pop(artifact_path, None)
            logger.debug(f"Cleared cache for {artifact_path}")
        else:
            self._artifact_cache.clear()
            logger.debug("Cleared all artifact cache")

    def load_artifact(self, artifact_path: str, use_cache: bool = False) -> Optional[Dict[str, Any]]:
        """Load a JSON artifact from the artifacts directory

        Args:
            artifact_path: Path to artifact relative to artifacts directory
            use_cache: Whether to use cached version (default: False for fresh data)
        """
        # Check cache only if explicitly requested
        if use_cache and artifact_path in self._artifact_cache:
            return self._artifact_cache[artifact_path]

        full_path = self.artifacts_dir / artifact_path
        if not full_path.exists():
            logger.warning(f"Artifact not found: {full_path}")
            return None

        try:
            with open(full_path, 'r') as f:
                data = json.load(f)
            # Update cache for future use
            self._artifact_cache[artifact_path] = data
            return data
        except Exception as e:
            logger.error(f"Error loading artifact {artifact_path}: {e}")
            return None

    def get_video_path(self) -> Optional[str]:
        """Get the path to the downloaded video"""
        video_metadata = self.load_artifact("download/video_metadata.json")
        if video_metadata and 'video_path' in video_metadata:
            return video_metadata['video_path']

        # Fallback: look for video file in output directory
        for ext in ['.mp4', '.webm', '.mkv']:
            video_files = list(self.output_dir.glob(f"*{ext}"))
            if video_files:
                return str(video_files[0])

        return None

    def get_available_clips(self) -> List[str]:
        """Get list of generated clip files"""
        clips = []
        for clip_file in self.output_dir.glob("*.mp4"):
            if "original" not in clip_file.name.lower():
                clips.append(str(clip_file))
        return sorted(clips)


def build_transcription_tab(state: DebugUIState) -> gr.Tab:
    """Build the transcription & speaker timeline tab"""

    with gr.Tab("📝 Transcription & Speakers") as tab:
        gr.Markdown("## Transcription & Speaker Timeline")
        gr.Markdown("View word-level transcription and speaker diarization results")

        with gr.Row():
            with gr.Column(scale=2):
                transcript_display = gr.DataFrame(
                    label="Word-Level Transcription",
                    headers=["Time", "Speaker", "Word", "Confidence"],
                    interactive=False
                )

            with gr.Column(scale=1):
                stats_display = gr.JSON(label="Transcription Stats")

        with gr.Row():
            speaker_timeline = gr.Plot(label="Speaker Activity Timeline")

        with gr.Accordion("Raw Transcript Data", open=False):
            raw_transcript = gr.JSON(label="Raw JSON")

        gr.Markdown("### Regenerate Transcription")
        with gr.Row():
            whisper_model = gr.Dropdown(
                choices=["turbo", "base", "small", "medium", "large"],
                value="turbo",
                label="Whisper Model"
            )
            regenerate_btn = gr.Button("🔄 Regenerate Transcription", variant="primary")

        regenerate_output = gr.Textbox(label="Regeneration Status", interactive=False)

        # Load data function
        def load_transcription_data():
            transcript_data = state.load_artifact("transcription/transcript.json")
            speaker_data = state.load_artifact("speaker_diarization/segments.json")

            if not transcript_data:
                return (
                    pd.DataFrame(),
                    {"error": "No transcription data found"},
                    None,
                    {"error": "No data"}
                )

            # Build DataFrame for display
            word_timings = transcript_data.get('word_timings', [])
            rows = []
            for word_info in word_timings[:500]:  # Limit to first 500 words for display
                rows.append({
                    "Time": f"{word_info.get('start_time', 0):.2f}s",
                    "Speaker": word_info.get('speaker', 'N/A'),
                    "Word": word_info.get('word', ''),
                    "Confidence": f"{word_info.get('confidence', 0):.2%}"
                })

            df = pd.DataFrame(rows)

            # Calculate stats
            stats = {
                "total_words": transcript_data.get('word_count', len(word_timings)),
                "duration": f"{word_timings[-1].get('end_time', 0):.2f}s" if word_timings else "N/A",
                "avg_confidence": f"{sum(w.get('confidence', 0) for w in word_timings) / len(word_timings):.2%}" if word_timings else "N/A"
            }

            if speaker_data:
                speakers = set(seg.get('speaker', '') for seg in speaker_data.get('segments', []))
                stats['num_speakers'] = len(speakers)

            # Create speaker timeline plot
            timeline_plot = create_speaker_timeline(word_timings, speaker_data)

            return df, stats, timeline_plot, transcript_data

        # Regenerate function
        def regenerate_transcription(model_name):
            try:
                from .debug_rerun import StepRerunner

                rerunner = StepRerunner(state.job_id, str(state.output_dir))
                result = rerunner.rerun_transcription(whisper_model=model_name)

                if result['status'] == 'success':
                    # Reload the transcription data to show new results
                    new_data = load_transcription_data()
                    return f"✅ Success! Transcription regenerated with {model_name} model. Refresh the tab to see new results."
                else:
                    return f"❌ Error: {result['message']}"
            except Exception as e:
                return f"❌ Error: {str(e)}"

        regenerate_btn.click(
            fn=regenerate_transcription,
            inputs=[whisper_model],
            outputs=[regenerate_output]
        )

        # Load on tab open
        tab.select(
            fn=load_transcription_data,
            outputs=[transcript_display, stats_display, speaker_timeline, raw_transcript]
        )

    return tab


def create_speaker_timeline(word_timings: List[Dict], speaker_data: Optional[Dict]) -> Any:
    """Create a timeline plot showing speaker activity"""
    import plotly.graph_objects as go

    if not word_timings:
        return None

    # Group words by speaker and time
    speaker_segments = []
    current_speaker = None
    segment_start = None

    for word in word_timings:
        speaker = word.get('speaker', 'UNKNOWN')
        time = word.get('start_time', 0)

        if speaker != current_speaker:
            if current_speaker is not None:
                speaker_segments.append({
                    'speaker': current_speaker,
                    'start': segment_start,
                    'end': time
                })
            current_speaker = speaker
            segment_start = time

    # Add final segment
    if current_speaker and word_timings:
        speaker_segments.append({
            'speaker': current_speaker,
            'start': segment_start,
            'end': word_timings[-1].get('end_time', 0)
        })

    # Create plot
    fig = go.Figure()

    # Color map for speakers
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8']
    speaker_colors = {}

    for i, segment in enumerate(speaker_segments):
        speaker = segment['speaker']
        if speaker not in speaker_colors:
            speaker_colors[speaker] = colors[len(speaker_colors) % len(colors)]

        fig.add_trace(go.Bar(
            x=[segment['end'] - segment['start']],
            y=[speaker],
            orientation='h',
            base=segment['start'],
            name=speaker,
            marker=dict(color=speaker_colors[speaker]),
            showlegend=i == 0 or segment['speaker'] not in [s['speaker'] for s in speaker_segments[:i]],
            hovertemplate=f"<b>{speaker}</b><br>Time: {segment['start']:.1f}s - {segment['end']:.1f}s<br>Duration: {segment['end'] - segment['start']:.1f}s<extra></extra>"
        ))

    fig.update_layout(
        title="Speaker Activity Over Time",
        xaxis_title="Time (seconds)",
        yaxis_title="Speaker",
        barmode='overlay',
        height=300,
        showlegend=True
    )

    return fig


def build_face_tracking_tab(state: DebugUIState) -> gr.Tab:
    """Build the face tracking visualization tab"""

    with gr.Tab("👤 Face Tracking") as tab:
        gr.Markdown("## Face Tracking Visualization")
        gr.Markdown("View face detection and tracking with bounding box overlays")

        with gr.Row():
            with gr.Column(scale=2):
                video_player = gr.Video(label="Video with Face Tracking Overlay", autoplay=False)

            with gr.Column(scale=1):
                gr.Markdown("### Quality Metrics")
                quality_metrics = gr.JSON(label="Tracking Quality")

                gr.Markdown("### Tracked Faces")
                face_list = gr.DataFrame(
                    label="Face Statistics",
                    headers=["Face ID", "Avg Size", "Speech Corr", "Frames"],
                    interactive=False
                )

        with gr.Row():
            face_timeline = gr.Plot(label="Face Position Timeline")

        gr.Markdown("### Regenerate Face Tracking")
        with gr.Row():
            smoothing = gr.Slider(0, 100, value=70, label="Smoothing Strength")
            max_faces = gr.Slider(1, 5, value=2, step=1, label="Max Tracked Faces")
            generate_overlay_btn = gr.Button("🎥 Generate Overlay Video", variant="primary")

        overlay_status = gr.Textbox(label="Status", interactive=False)

        # Load data function
        def load_face_tracking_data():
            video_path = state.get_video_path()

            # Try to load debug face data
            face_data = state.load_artifact("debug/face_boxes_by_frame.json")
            metrics_data = state.load_artifact("debug/quality_metrics.json")

            if not face_data:
                return (
                    video_path,
                    {"info": "No face tracking debug data found. Generate overlay first."},
                    pd.DataFrame(),
                    None
                )

            # Build face statistics DataFrame
            face_tracks = face_data.get('face_tracks', [])
            rows = []
            for track in face_tracks:
                rows.append({
                    "Face ID": track.get('face_id', 'N/A'),
                    "Avg Size": f"{track.get('avg_area_ratio', 0):.1%}",
                    "Speech Corr": f"{track.get('speech_correlation', 0):.2f}",
                    "Frames": len(track.get('positions', {}))
                })

            face_df = pd.DataFrame(rows)

            # Create timeline plot
            timeline_plot = create_face_timeline(face_tracks)

            return video_path, metrics_data or {}, face_df, timeline_plot

        # Generate overlay function
        def generate_overlay(smoothing_val, max_faces_val):
            try:
                from .debug_rerun import StepRerunner

                rerunner = StepRerunner(state.job_id, str(state.output_dir))
                result = rerunner.generate_face_overlay(
                    smoothing_strength=int(smoothing_val),
                    max_tracked_faces=int(max_faces_val)
                )

                if result['status'] == 'success':
                    video_path = result.get('video_path', '')
                    return (
                        video_path,  # Update video player
                        f"✅ Success! Face tracking overlay generated.\n\nVideo player updated above."
                    )
                else:
                    return (
                        None,  # No video
                        f"❌ {result['message']}"
                    )
            except Exception as e:
                return (
                    None,
                    f"❌ Error: {str(e)}"
                )

        generate_overlay_btn.click(
            fn=generate_overlay,
            inputs=[smoothing, max_faces],
            outputs=[video_player, overlay_status]  # Update both video and status
        )

        # Load on tab open
        tab.select(
            fn=load_face_tracking_data,
            outputs=[video_player, quality_metrics, face_list, face_timeline]
        )

    return tab


def create_face_timeline(face_tracks: List[Dict]) -> Any:
    """Create a timeline plot showing face positions"""
    import plotly.graph_objects as go

    if not face_tracks:
        return None

    fig = go.Figure()

    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8']

    for i, track in enumerate(face_tracks):
        face_id = track.get('face_id', i)
        positions = track.get('positions', {})

        if not positions:
            continue

        # Convert positions dict to sorted lists
        times = sorted([float(t) for t in positions.keys()])
        y_positions = [positions[str(t)].get('y', 0) for t in times]

        fig.add_trace(go.Scatter(
            x=times,
            y=y_positions,
            mode='lines',
            name=f'Face {face_id}',
            line=dict(color=colors[i % len(colors)], width=2),
            hovertemplate=f"<b>Face {face_id}</b><br>Time: %{{x:.2f}}s<br>Y Position: %{{y}}<extra></extra>"
        ))

    fig.update_layout(
        title="Face Vertical Position Over Time",
        xaxis_title="Time (seconds)",
        yaxis_title="Y Position (pixels)",
        height=300,
        showlegend=True
    )

    return fig


def build_ai_analysis_tab(state: DebugUIState) -> gr.Tab:
    """Build the AI analysis & viral moments tab"""

    # Fetch available models from backend API
    available_models = fetch_available_models()

    with gr.Tab("🎯 AI Analysis") as tab:
        gr.Markdown("## AI Viral Moment Analysis")
        gr.Markdown("View and regenerate AI-selected viral moments")

        moments_display = gr.HTML(label="Viral Moments")

        with gr.Accordion("Raw AI Analysis Data", open=False):
            raw_ai_data = gr.JSON(label="Raw JSON")

        gr.Markdown("### Regenerate AI Analysis")
        with gr.Row():
            ai_model = gr.Dropdown(
                choices=available_models,
                value=available_models[0] if available_models else "gemini-2.0-flash",
                label="AI Model"
            )
            keywords = gr.Textbox(label="Viral Focus Keywords", placeholder="e.g., motivation, success, business")

        regenerate_ai_btn = gr.Button("🔄 Regenerate AI Analysis", variant="primary")
        ai_output = gr.Textbox(label="Regeneration Status", interactive=False)

        # Load data function
        def load_ai_analysis():
            viral_moments = state.load_artifact("ai_analysis/viral_moments.json")

            if not viral_moments:
                return "<p>No AI analysis data found.</p>", {"error": "No data"}

            # Build HTML cards for each moment
            moments_list = viral_moments.get('moments', []) if isinstance(viral_moments, dict) else viral_moments

            html = "<div style='display: flex; flex-direction: column; gap: 20px;'>"

            for i, moment in enumerate(moments_list[:10], 1):  # Limit to top 10
                viral_score = moment.get('viral_score', 0)
                title = moment.get('title', f'Moment {i}')
                hook = moment.get('hook', 'N/A')
                reason = moment.get('reason', 'N/A')
                start_time = moment.get('start_time', 0)
                end_time = moment.get('end_time', 0)
                duration = end_time - start_time

                # Check for optimized timings
                opt_start = moment.get('optimized_start')
                opt_end = moment.get('optimized_end')
                has_optimization = opt_start is not None and opt_end is not None

                # Score color
                if viral_score >= 80:
                    score_color = '#4CAF50'
                elif viral_score >= 60:
                    score_color = '#FF9800'
                else:
                    score_color = '#F44336'

                # Build timing display
                timing_html = f"{start_time:.1f}s - {end_time:.1f}s ({duration:.1f}s)"
                if has_optimization:
                    opt_duration = opt_end - opt_start
                    adjustment = opt_start - start_time
                    timing_html += f"<br><span style='color: #2563eb; font-size: 0.9em;'>✓ Optimized: {opt_start:.1f}s - {opt_end:.1f}s ({opt_duration:.1f}s, Δ{adjustment:+.1f}s)</span>"

                html += f"""
                <div style='border: 2px solid #ddd; border-radius: 8px; padding: 15px; background: #f9f9f9; color: #1a1a1a;'>
                    <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;'>
                        <h3 style='margin: 0; color: #1a1a1a;'>#{i}: {title}</h3>
                        <span style='background: {score_color}; color: white; padding: 5px 15px; border-radius: 20px; font-weight: bold;'>
                            {viral_score:.0f}/100
                        </span>
                    </div>
                    <p style='margin: 8px 0; color: #333;'><strong style='color: #1a1a1a;'>⏱️ Timing:</strong> {timing_html}</p>
                    <p style='margin: 8px 0; color: #333;'><strong style='color: #1a1a1a;'>🎣 Hook:</strong> {hook}</p>
                    <p style='margin: 8px 0; color: #333;'><strong style='color: #1a1a1a;'>💡 Reason:</strong> {reason}</p>
                    <p style='margin: 8px 0; color: #333;'><strong style='color: #1a1a1a;'>🏷️ Tags:</strong> {', '.join(moment.get('tags', []))}</p>
                </div>
                """

            html += "</div>"

            return html, viral_moments

        # Regenerate function
        def regenerate_ai(model, kw):
            try:
                from .debug_rerun import StepRerunner

                rerunner = StepRerunner(state.job_id, str(state.output_dir))
                result = rerunner.rerun_ai_analysis(ai_model=model, keywords=kw)

                if result['status'] == 'success':
                    moments_count = result.get('moments_count', 0)
                    return f"✅ Success! AI analysis regenerated with {model}. Found {moments_count} viral moments. Refresh the tab to see new results."
                else:
                    return f"❌ Error: {result['message']}"
            except Exception as e:
                return f"❌ Error: {str(e)}"

        regenerate_ai_btn.click(
            fn=regenerate_ai,
            inputs=[ai_model, keywords],
            outputs=[ai_output]
        )

        # Load on tab open
        tab.select(
            fn=load_ai_analysis,
            outputs=[moments_display, raw_ai_data]
        )

    return tab


def build_parameter_tuning_tab(state: DebugUIState) -> gr.Tab:
    """Build the parameter tuning tab"""

    with gr.Tab("⚙️ Parameter Tuning") as tab:
        gr.Markdown("## Step-by-Step Parameter Tuning")
        gr.Markdown("Rerun individual processing steps with different parameters")

        step_selector = gr.Dropdown(
            choices=[
                "transcription",
                "speaker_diarization",
                "ai_analysis",
                "face_tracking",
                "clip_generation"
            ],
            value="transcription",
            label="Select Step to Rerun"
        )

        # Dynamic parameter form area
        params_area = gr.Column()

        with params_area:
            params_display = gr.Markdown("Select a step to see parameters")

        rerun_btn = gr.Button("▶️ Rerun Step", variant="primary", size="lg")
        rerun_status = gr.Textbox(label="Execution Status", interactive=False)

        with gr.Row():
            with gr.Column():
                gr.Markdown("### Original Results")
                original_results = gr.JSON(label="Original")

            with gr.Column():
                gr.Markdown("### New Results")
                new_results = gr.JSON(label="After Rerun")

        # Step selection handler
        def on_step_select(step):
            param_forms = {
                "transcription": "**Whisper Model:** turbo | base | small | medium | large",
                "speaker_diarization": "**Min Speakers:** 2\n**Max Speakers:** 5",
                "ai_analysis": "**AI Model:** gemini-2.0-flash-exp\n**Keywords:** (custom)",
                "face_tracking": "**Smoothing Strength:** 70\n**Max Tracked Faces:** 2",
                "clip_generation": "**Subtitle Font Size:** 60\n**Crop Style:** auto"
            }
            return param_forms.get(step, "No parameters available")

        step_selector.change(
            fn=on_step_select,
            inputs=[step_selector],
            outputs=[params_display]
        )

        # Rerun handler
        def rerun_step(step):
            try:
                from .debug_rerun import StepRerunner

                rerunner = StepRerunner(state.job_id, str(state.output_dir))

                if step == "transcription":
                    result = rerunner.rerun_transcription(whisper_model="base")
                    if result['status'] == 'success':
                        return f"✅ Transcription rerun complete! Check 'Transcription & Speakers' tab.\nSaved to: {result.get('saved_to', 'N/A')}"
                    else:
                        return f"❌ Error: {result['message']}"

                elif step == "speaker_diarization":
                    result = rerunner.rerun_speaker_diarization(min_speakers=2, max_speakers=5)
                    if result['status'] == 'success':
                        return f"✅ Speaker diarization rerun complete!\nSaved to: {result.get('saved_to', 'N/A')}"
                    else:
                        return f"❌ Error: {result['message']}"

                elif step == "ai_analysis":
                    result = rerunner.rerun_ai_analysis(ai_model="gemini-2.0-flash", keywords="")
                    if result['status'] == 'success':
                        moments_count = result.get('moments_count', 0)
                        return f"✅ AI analysis rerun complete! Found {moments_count} moments.\nSaved to: {result.get('saved_to', 'N/A')}"
                    else:
                        return f"❌ Error: {result['message']}"

                elif step == "face_tracking":
                    result = rerunner.rerun_face_tracking(smoothing_strength=70, max_tracked_faces=2)
                    if result['status'] == 'success':
                        return f"✅ Face tracking rerun complete (30s test)!\nSaved to: {result.get('saved_to', 'N/A')}"
                    else:
                        return f"❌ Error: {result['message']}"

                elif step == "clip_generation":
                    return "⚠️ Clip generation rerun requires full pipeline. Use main form to regenerate."

                else:
                    return f"❌ Unknown step: {step}"

            except Exception as e:
                return f"❌ Error: {str(e)}"

        rerun_btn.click(
            fn=rerun_step,
            inputs=[step_selector],
            outputs=[rerun_status]
        )

    return tab


def create_debug_interface(job_id: str, output_dir: str) -> gr.Blocks:
    """Create the main Gradio debug interface"""

    state = DebugUIState(job_id, output_dir)

    with gr.Blocks(title=f"PodcastClips Debug - {job_id}", theme=gr.themes.Soft()) as demo:
        gr.Markdown(f"# 🎬 PodcastClips Debug Mode")
        gr.Markdown(f"**Job ID:** `{job_id}`")
        gr.Markdown(f"**Output Directory:** `{output_dir}`")

        with gr.Tabs():
            build_transcription_tab(state)
            build_face_tracking_tab(state)
            build_ai_analysis_tab(state)
            build_parameter_tuning_tab(state)

        # Footer
        gr.Markdown("---")
        gr.Markdown("💡 **Tip:** Click on each tab to load its data. Use the regenerate buttons to rerun steps with different parameters.")

    return demo


def launch_debug_ui(job_id: str, output_dir: str, share: bool = False, server_port: int = 7860):
    """Launch the debug UI"""
    logger.info(f"Launching debug UI for job {job_id}")
    logger.info(f"Output directory: {output_dir}")

    demo = create_debug_interface(job_id, output_dir)

    demo.launch(
        server_name="0.0.0.0",
        server_port=server_port,
        share=share,
        show_error=True,
        quiet=False
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_ui.py <job_id> [output_dir]")
        print("Example: python debug_ui.py abc123 /path/to/output/abc123")
        sys.exit(1)

    job_id = sys.argv[1]

    if len(sys.argv) >= 3:
        output_dir = sys.argv[2]
    else:
        # Try to find output directory
        possible_dirs = [
            f"output/{job_id}",
            f"../../output/{job_id}",
            f"../../../output/{job_id}"
        ]

        output_dir = None
        for dir_path in possible_dirs:
            if os.path.exists(dir_path):
                output_dir = dir_path
                break

        if not output_dir:
            print(f"Error: Could not find output directory for job {job_id}")
            print("Please specify the output directory as the second argument")
            sys.exit(1)

    launch_debug_ui(job_id, output_dir)
