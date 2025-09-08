import os
import sys
from utils import *
from dotenv import load_dotenv  # type: ignore

"""
Note on environment variables:
- We load dotenv here, but we no longer hard-require MoneyPrinter env vars at import time.
- The MoneyPrinter generation endpoint will validate env vars on demand.
This allows the app to also serve the Brainrot generator endpoint without requiring
PEXELS/OPENAI/TIKTOK keys when not used.
"""
# Load environment variables
load_dotenv("../.env")

from gpt import *
from video import *
from search import *
from uuid import uuid4
from tiktokvoice import *
from flask_cors import CORS  # type: ignore
from termcolor import colored  # type: ignore
try:
    from googleapiclient.errors import HttpError  # type: ignore
except Exception:
    try:
        from apiclient.errors import HttpError  # type: ignore
    except Exception:
        HttpError = Exception  # type: ignore
from flask import Flask, request, jsonify  # type: ignore
from moviepy.config import change_settings  # type: ignore
from moviepy import (  # type: ignore
    AudioFileClip,
    VideoFileClip,
    CompositeAudioClip,
    concatenate_audioclips,
)

# Allow importing the brainrot generator without packaging by augmenting sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
BRAINROT_DIR = os.path.join(REPO_ROOT, "brainrot-generator")
if BRAINROT_DIR not in sys.path:
    sys.path.insert(0, BRAINROT_DIR)
try:
    # Import TikYouGenerator for brainrot endpoint (optional dependency)
    from tikyou_video_generator.generator import TikYouGenerator  # type: ignore
except Exception as _brainrot_import_err:
    TikYouGenerator = None  # type: ignore



# Set environment variables
SESSION_ID = os.getenv("TIKTOK_SESSION_ID")
openai_api_key = os.getenv('OPENAI_API_KEY')
change_settings({"IMAGEMAGICK_BINARY": os.getenv("IMAGEMAGICK_BINARY")})

# Initialize Flask
app = Flask(__name__)
CORS(app)

AMOUNT_OF_STOCK_VIDEOS = 5
GENERATING = False


# Health endpoint to verify server is running and capabilities
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "backend": "videohelper",
        "moneyprinter": True,
        "brainrot_available": TikYouGenerator is not None,
        "cwd": os.getcwd(),
        "root": REPO_ROOT,
    })


# Generation Endpoint (MoneyPrinter)
@app.route("/api/generate", methods=["POST"])
def generate():
    try:
        # Set global variable
        global GENERATING
        GENERATING = True

        # Clean
        clean_dir("../../../temp/")
        clean_dir("./subtitles/")


        # Parse JSON
        data = request.get_json()
        # Validate required environment only for MoneyPrinter flow
        try:
            check_env_vars()
        except SystemExit:
            GENERATING = False
            return jsonify({
                "status": "error",
                "message": "Missing required MoneyPrinter environment variables. See EnvironmentVariables.md.",
                "data": []
            }), 400
        paragraph_number = int(data.get('paragraphNumber', 1))  # Default to 1 if not provided
        ai_model = data.get('aiModel')  # Get the AI model selected by the user
        n_threads = data.get('threads')  # Amount of threads to use for video generation
        subtitles_position = data.get('subtitlesPosition')  # Position of the subtitles in the video
        text_color = data.get('color') # Color of subtitle text

        # Get 'useMusic' from the request data and default to False if not provided
        use_music = data.get('useMusic', False)

        # Get 'useGPU' from the request data and default to True if not provided  
        use_gpu = data.get('useGPU', True)

        # Get the ZIP Url of the songs
        songs_zip_url = data.get('zipUrl')

        # Download songs
        if use_music:
            # Downloads a ZIP file containing popular TikTok Songs
            if songs_zip_url:
                fetch_songs(songs_zip_url)
            else:
                # Default to a ZIP file containing popular TikTok Songs
                fetch_songs("https://filebin.net/2avx134kdibc4c3q/drive-download-20240209T180019Z-001.zip")

        # Print little information about the video which is to be generated
        print(colored("[Video to be generated]", "blue"))
        print(colored("   Subject: " + data["videoSubject"], "blue"))
        print(colored("   AI Model: " + ai_model, "blue"))  # Print the AI model being used
        print(colored("   Custom Prompt: " + data["customPrompt"], "blue"))  # Print the AI model being used
        print(colored("   GPU Acceleration: " + str(use_gpu), "blue"))  # Print GPU usage setting



        if not GENERATING:
            return jsonify(
                {
                    "status": "error",
                    "message": "Video generation was cancelled.",
                    "data": [],
                }
            )
        
        voice = data["voice"]
        voice_prefix = voice[:2]


        if not voice:
            print(colored("[!] No voice was selected. Defaulting to \"en_us_001\"", "yellow"))
            voice = "en_us_001"
            voice_prefix = voice[:2]


        # Generate a script
        script = generate_script(data["videoSubject"], paragraph_number, ai_model, voice, data["customPrompt"]) or ""  # Ensure non-None for typing

        # Generate search terms
        search_terms = get_search_terms(
            data["videoSubject"], AMOUNT_OF_STOCK_VIDEOS, script or "", ai_model
        )

        # Search for a video of the given search term
        video_urls = []

        # Defines how many results it should query and search through
        it = 15

        # Defines the minimum duration of each clip
        min_dur = 10

        # Loop through all search terms,
        # and search for a video of the given search term
        for search_term in search_terms:
            if not GENERATING:
                return jsonify(
                    {
                        "status": "error",
                        "message": "Video generation was cancelled.",
                        "data": [],
                    }
                )
            pexels_api_key = os.getenv("PEXELS_API_KEY") or ""
            found_urls = search_for_stock_videos(
                search_term, pexels_api_key, it, min_dur
            )
            # Check for duplicates
            for url in found_urls:
                if url not in video_urls:
                    video_urls.append(url)
                    break

        # Check if video_urls is empty
        if not video_urls:
            print(colored("[-] No videos found to download.", "red"))
            return jsonify(
                {
                    "status": "error",
                    "message": "No videos found to download.",
                    "data": [],
                }
            )
            
        # Define video_paths
        video_paths = []

        # Let user know
        print(colored(f"[+] Downloading {len(video_urls)} videos...", "blue"))

        # Save the videos
        for video_url in video_urls:
            if not GENERATING:
                return jsonify(
                    {
                        "status": "error",
                        "message": "Video generation was cancelled.",
                        "data": [],
                    }
                )
            try:
                saved_video_path = save_video(video_url)
                video_paths.append(saved_video_path)
            except Exception:
                print(colored(f"[-] Could not download video: {video_url}", "red"))

        # Let user know
        print(colored("[+] Videos downloaded!", "green"))

        # Let user know
        print(colored("[+] Script generated!\n", "green"))

        if not GENERATING:
            return jsonify(
                {
                    "status": "error",
                    "message": "Video generation was cancelled.",
                    "data": [],
                }
            )

        # Split script into sentences
        sentences = script.split(". ")

        # Remove empty strings
        sentences = list(filter(lambda x: x != "", sentences))
        paths = []

        # Generate TTS for every sentence
        for sentence in sentences:
            if not GENERATING:
                return jsonify(
                    {
                        "status": "error",
                        "message": "Video generation was cancelled.",
                        "data": [],
                    }
                )
            current_tts_path = f"../../../temp/{uuid4()}.mp3"
            tts(sentence, voice, filename=current_tts_path)
            audio_clip = AudioFileClip(current_tts_path)
            paths.append(audio_clip)

        # Combine all TTS files using moviepy
        final_audio = concatenate_audioclips(paths)
        tts_path = f"../../../temp/{uuid4()}.mp3"
        final_audio.write_audiofile(tts_path)

        try:
            subtitles_path = generate_subtitles(audio_path=tts_path, sentences=sentences, audio_clips=paths, voice=voice_prefix)
        except Exception as e:
            print(colored(f"[-] Error generating subtitles: {e}", "red"))
            subtitles_path = None

        # Concatenate videos
        temp_audio = AudioFileClip(tts_path)
        combined_video_path = combine_videos(video_paths, temp_audio.duration, 5, n_threads or 2, use_gpu)

        # Put everything together
        try:
            final_video_path = generate_video(combined_video_path, tts_path, subtitles_path or "", n_threads or 2, subtitles_position, text_color or "#FFFF00", use_gpu)
        except Exception as e:
            print(colored(f"[-] Error generating final video: {e}", "red"))
            final_video_path = None

        # Define metadata for the video, we will display this to the user, and use it for the YouTube upload
        title, description, keywords = generate_metadata(data["videoSubject"], script or "", ai_model)

        print(colored("[-] Metadata for YouTube upload:", "blue"))
        print(colored("   Title: ", "blue"))
        print(colored(f"   {title}", "blue"))
        print(colored("   Description: ", "blue"))
        print(colored(f"   {description}", "blue"))
        print(colored("   Keywords: ", "blue"))
        print(colored(f"  {', '.join(keywords)}", "blue"))

        video_clip = VideoFileClip(f"../../../temp/{final_video_path}")
        
        # Get GPU-optimized codec settings for final export
        codec_settings = get_video_codec_settings(use_gpu)
        # Remove 'logger' from codec_settings to avoid parameter conflict
        write_settings = {k: v for k, v in codec_settings.items() if k != 'logger'}
        
        if use_music:
            # Select a random song
            song_path = choose_random_song()

            # Add song to video at 30% volume using moviepy
            original_duration = video_clip.duration
            original_audio = video_clip.audio
            song_clip = AudioFileClip(song_path).with_fps(44100)

            # Set the volume of the song to 10% of the original volume
            song_clip = song_clip.with_volume_scaled(0.1).with_fps(44100)

            # Add the song to the video
            comp_audio = CompositeAudioClip([original_audio, song_clip])
            video_clip = video_clip.with_audio(comp_audio)
            video_clip = video_clip.with_fps(30)
            video_clip = video_clip.with_duration(original_duration)
            video_clip.write_videofile(final_video_path, threads=n_threads or 1, logger=None, **write_settings)
        else:
            video_clip.write_videofile(final_video_path, threads=n_threads or 1, logger=None, **write_settings)


        # Let user know
        print(colored(f"[+] Video generated: {final_video_path}!", "green"))

        # Stop FFMPEG processes
        if os.name == "nt":
            # Windows
            os.system("taskkill /f /im ffmpeg.exe")
        else:
            # Other OS
            os.system("pkill -f ffmpeg")

        GENERATING = False

        # Return JSON
        return jsonify(
            {
                "status": "success",
                "message": "Video generated! See MoneyPrinter/output.mp4 for result.",
                "data": final_video_path,
            }
        )
    except Exception as err:
        print(colored(f"[-] Error: {str(err)}", "red"))
        return jsonify(
            {
                "status": "error",
                "message": f"Could not retrieve stock videos: {str(err)}",
                "data": [],
            }
        )


@app.route("/api/cancel", methods=["POST"])
def cancel():
    print(colored("[!] Received cancellation request...", "yellow"))

    global GENERATING
    GENERATING = False

    return jsonify({"status": "success", "message": "Cancelled video generation."})


# ------------------------------
# Brainrot generator endpoints
# ------------------------------

@app.route("/api/brainrot/generate", methods=["POST"])
def brainrot_generate():
    """
    Generate TikTok-style compilations using the brainrot generator in a unified API.

    Expected JSON body:
    {
      "youtubeUrl": "https://youtu.be/...",   # required
      "numCompilations": 1,                    # optional (default 1)
      "minDuration": 60,                       # optional (default 60)
      "maxDuration": 110,                      # optional (default 110)
      "maxReuse": 3                            # optional (default 3)
    }
    """
    try:
        if TikYouGenerator is None:
            return jsonify({
                "status": "error",
                "message": "Brainrot generator is unavailable (import failed).",
                "data": []
            }), 500

        payload = request.get_json(force=True) or {}
        youtube_url = payload.get("youtubeUrl")
        if not youtube_url or not isinstance(youtube_url, str):
            return jsonify({
                "status": "error",
                "message": "Missing or invalid 'youtubeUrl' in request body.",
                "data": []
            }), 400

        num_compilations = int(payload.get("numCompilations", 1))
        min_duration = int(payload.get("minDuration", 60))
        max_duration = int(payload.get("maxDuration", 110))
        max_reuse = int(payload.get("maxReuse", 3))

        # Use a dedicated output directory under MoneyPrinter for clarity
        brainrot_output_dir = os.path.abspath(os.path.join(CURRENT_DIR, "..", "brainrot_output"))
        os.makedirs(brainrot_output_dir, exist_ok=True)

        generator = TikYouGenerator(output_dir=brainrot_output_dir)

        # Phase 1: Process the source video into clips
        video_clips = generator.process_single_video(youtube_url)
        if not video_clips:
            return jsonify({
                "status": "error",
                "message": "No clips could be processed from the provided YouTube URL.",
                "data": []
            }), 400

        categorized = generator.categorize_clips(video_clips)
        all_clips = [c for group in categorized.values() for c in group if c.get('duration', 0) >= 1.0]
        if not all_clips:
            return jsonify({
                "status": "error",
                "message": "No usable clips long enough for compilation.",
                "data": []
            }), 400

        # Extract video_id for naming
        try:
            video_id = generator.extract_video_id(youtube_url)
        except Exception:
            video_id = "video"

        # Phase 2: Create compilations
        clip_usage = {clip['path']: 0 for clip in all_clips}
        created_sets = []

        for i in range(num_compilations):
            selected = generator._select_clips_with_constraints(  # noqa: SLF001 (private access acceptable in same repo)
                all_clips, clip_usage, max_reuse, min_duration, max_duration
            )
            if not selected:
                break

            # Update usage counts
            for clip in selected:
                clip_usage[clip['path']] += 1

            base_output_path = os.path.join(brainrot_output_dir, f"{video_id}_compilation_{i+1}")
            results = generator.create_all_compilation_variations(selected, base_output_path, video_id, i+1)

            created_sets.append({
                "index": i + 1,
                "normal": results.get("normal"),
                "tts": results.get("tts"),
            })

        if not created_sets:
            return jsonify({
                "status": "error",
                "message": "Unable to create any compilations with provided constraints.",
                "data": []
            }), 400

        return jsonify({
            "status": "success",
            "message": f"Created {len(created_sets)} brainrot compilation set(s).",
            "data": created_sets
        })
    except Exception as e:
        print(colored(f"[-] Brainrot error: {str(e)}", "red"))
        return jsonify({
            "status": "error",
            "message": f"Brainrot generation failed: {str(e)}",
            "data": []
        }), 500
