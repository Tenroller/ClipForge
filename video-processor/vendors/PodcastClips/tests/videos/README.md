# Test Videos for Face Detection

Add 5-10 second video clips to test face tracking and content mode detection.

## Naming Convention

| Filename | Expected Mode | Description |
|----------|--------------- |-------------|
| `interview_2_people.mp4` | SPLIT_SCREEN | Interview with 2 people in frame |
| `single_speaker.mp4` | FACE | Single person speaking to camera |
| `audience_wide.mp4` | HORIZONTAL | Wide audience shot, multiple people |
| `audience_front_speakers.mp4` | SPLIT_SCREEN | 2 speakers in front + audience behind |

## How to Add Videos

1. Record or clip 5-10 second segments from source footage
2. Name files according to the convention above
3. Run `python ../run_all_tests.py` from the tests folder

## Expected Results by Mode

- **FACE**: Single speaker close-up → zoomed vertical crop following the face
- **SPLIT_SCREEN**: 2 clear speakers → top/bottom split layout
- **HORIZONTAL**: Wide shots, audience, content → full 16:9 preservation
