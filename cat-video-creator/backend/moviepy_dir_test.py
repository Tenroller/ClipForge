from moviepy import VideoFileClip, AudioFileClip, vfx, afx


def main() -> None:
    print("moviepy dir() quick check (v2 API)")
    print("VideoFileClip has subclip:", hasattr(VideoFileClip, "subclip"))
    print("VideoFileClip has subclipped:", hasattr(VideoFileClip, "subclipped"))
    print("AudioFileClip has subclipped:", hasattr(AudioFileClip, "subclipped"))
    print("afx has AudioFadeOut:", hasattr(afx, "AudioFadeOut"))
    print("vfx has Crop class:", hasattr(vfx, "Crop"))
    # show a few relevant methods
    vf_methods = [m for m in dir(VideoFileClip) if any(k in m for k in ("sub", "with_", "resiz", "crop"))]
    print("VideoFileClip relevant methods:", sorted(vf_methods)[:25])


if __name__ == "__main__":
    main()


