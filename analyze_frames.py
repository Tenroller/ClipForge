import json
import os

json_path = 'video-processor/vendors/PodcastClips/test_debug_data.json'

if not os.path.exists(json_path):
    print(f"Error: {json_path} not found")
    exit(1)

with open(json_path, 'r') as f:
    data = json.load(f)

frames = data.get('frames', {})
target_frames = [348, 2862, 3024, 6437, 7596]

print(f"Analyzing {len(target_frames)} frames...")

for frame_id in target_frames:
    fid = str(frame_id)
    if fid in frames:
        f = frames[fid]
        print(f"\n=== Frame {frame_id} (t={f.get('timestamp', 0):.2f}s) ===")
        print(f"  Faces detected: {len(f.get('faces', []))}")
        print(f"  Active speaker: {f.get('active_speaker_id')}")
        
        # Check content scores if available (might not be in this JSON structure depending on export)
        # But we can infer from behavior
        
        for face in f.get('faces', []):
            is_active = "*" if face.get('is_active_speaker') else " "
            print(f"  {is_active} ID:{face['face_id']} Conf:{face['confidence']:.2f} "
                  f"Speech:{face.get('speech_correlation', 0):.2f} "
                  f"Area:{face.get('width',0)*face.get('height',0)} "
                  f"Center:({face.get('x',0)+face.get('width',0)/2:.0f}, {face.get('y',0)+face.get('height',0)/2:.0f})")
    else:
        print(f"\n=== Frame {frame_id} NOT FOUND ===")
