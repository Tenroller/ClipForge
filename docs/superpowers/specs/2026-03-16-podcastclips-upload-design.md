# Podcast Clips — File Upload Support

**Date:** 2026-03-16
**Status:** Approved

## Summary

Add file upload support to the Podcast Clips page, mirroring the existing upload capability in the Compilations page. Files larger than 80 MB are split into chunks and uploaded sequentially with per-chunk retry. The backend `PodcastClipsRequest` model is extended to accept either a YouTube URL or an uploaded video path (mutually exclusive, exactly one required).

---

## Backend Changes

### `backend/models/requests.py`

- `youtubeUrl`: change from required `str` to `Optional[str] = Field(default=None, ...)`
- Add `uploadedVideoPath: Optional[str] = Field(default=None, ...)`
- Remove the existing `@field_validator('youtubeUrl')` that calls `validate_youtube_url`
- Add a `@model_validator(mode='after')` that enforces exactly one of `youtubeUrl` / `uploadedVideoPath` is provided (mirrors `BrainrotRequest.validate_input_source`)
- When `youtubeUrl` is provided, call `validate_youtube_url(self.youtubeUrl)` inside the model validator

### `backend/api/routes/video_generation.py` — `podcastclips_generate`

- Update progress tracker log line to handle both source types:
  - If `req.youtubeUrl`: log `"Source: {req.youtubeUrl}"`
  - If `req.uploadedVideoPath`: log `"Source: Uploaded video - {req.uploadedVideoPath}"`

No changes needed to the orchestrator or video processor — the full `request.model_dump()` dict is already forwarded.

---

## Frontend Changes

### New: `frontend/src/hooks/useFileUpload.ts`

Shared hook encapsulating all chunked upload logic extracted from `compilations/page.tsx`.

**State exposed:**
- `uploadedFile: File | null`
- `uploadedFileId: string | null`
- `uploadedFilePath: string | null`
- `isUploading: boolean`
- `uploadProgress: number` (0–100)

**Handler exposed:**
- `handleFileUpload(event: React.ChangeEvent<HTMLInputElement>): Promise<void>`

**Internals:**
- `CHUNK_SIZE = 80 * 1024 * 1024` (80 MB threshold)
- Small files (≤ 80 MB): single `POST /api/upload-video`
- Large files (> 80 MB): init → chunks (3 attempts each, exponential backoff 1s/2s) → finalize
- `getCsrfToken()` helper lives inside the hook
- On success: sets `uploadedFileId` and `uploadedFilePath`, fires a toast
- On error: resets all state, fires a destructive toast

The hook accepts a `toast` function and translation helper `t` as arguments so it remains decoupled from UI concerns.

### `frontend/src/app/(protected)/compilations/page.tsx`

- Replace the ~120 lines of inline upload state + `handleFileUpload` + `getCsrfToken` + `CHUNK_SIZE` with a single call to `useFileUpload({ toast, t })`
- Destructure `{ uploadedFile, uploadedFileId, uploadedFilePath, isUploading, uploadProgress, handleFileUpload }` from the hook
- No UI changes

### `frontend/src/app/(protected)/podcastclips/page.tsx`

- Add `inputMethod` state: `'youtube' | 'upload'` (default `'youtube'`)
- Consume `useFileUpload({ toast, t })`
- Replace ROW 1 (YouTube input bar) with a `<Tabs>` card:
  - Tab 1 `youtube`: existing YouTube `<Input>` + metadata preview (unchanged behaviour)
  - Tab 2 `upload`: dashed drop zone with file input, file name display, and progress bar — matching compilations UI exactly
- Move the metadata preview (ROW 2) so it only renders when `inputMethod === 'youtube'`
- Feature cards placeholder also only renders when `inputMethod === 'youtube'`
- Update `handleSubmit`:
  - Validate `youtubeUrl` only when `inputMethod === 'youtube'`
  - Validate `uploadedFilePath` only when `inputMethod === 'upload'`
  - Set `youtubeUrl` to `undefined` when using upload; set `uploadedVideoPath` to `uploadedFilePath` when using upload
- Disable submit button when `inputMethod === 'upload'` and no file uploaded

### `frontend/src/lib/api.ts`

No changes required — `generatePodcastClips` already accepts `unknown` as its params type.

---

## i18n Changes

Add the following keys to the `podcastClips` namespace in both `frontend/messages/en.json` and `frontend/messages/pt-BR.json`:

| Key | EN | PT-BR |
|-----|----|-------|
| `videoSource` | `"Video Source"` | `"Fonte do Vídeo"` |
| `uploadFile` | `"Upload File"` | `"Enviar Arquivo"` |
| `uploadVideo` | `"Upload Video"` | `"Enviar Vídeo"` |
| `uploadVideoDescription` | `"Click to select a video file"` | `"Clique para selecionar um arquivo de vídeo"` |
| `uploading` | `"Uploading..."` | `"Enviando..."` |
| `videoUploaded` | `"Video uploaded successfully"` | `"Vídeo enviado com sucesso"` |
| `uploadFailed` | `"Upload failed"` | `"Falha no envio"` |
| `uploadVideoFirst` | `"Please upload a video file first"` | `"Por favor, envie um arquivo de vídeo primeiro"` |

---

## Data Flow

```
User selects file (podcastclips page)
  → useFileUpload.handleFileUpload()
  → small: POST /api/upload-video → { file_id, file_path }
  → large: POST /api/upload-video/init
           → POST /api/upload-video/chunk (×N, with retry)
           → POST /api/upload-video/finalize → { file_id, file_path }
  → uploadedFilePath stored in hook state

User clicks "Generate Viral Clips"
  → handleSubmit builds payload:
      { uploadedVideoPath: uploadedFilePath, minDuration, maxDuration, ... }
  → POST /api/podcastclips/generate
  → PodcastClipsRequest model_validator: youtubeUrl=None, uploadedVideoPath set → valid
  → job created, submitted to orchestrator → { jobId }
```

---

## Constraints

- The upload endpoints (`/api/upload-video*`) are already implemented and shared — no new backend upload infrastructure needed.
- The `useFileUpload` hook must not break the compilations page — it is a pure extraction of existing code.
- No changes to the video processor or orchestrator submission path.
