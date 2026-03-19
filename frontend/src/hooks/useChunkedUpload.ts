'use client';

import { useState, useCallback } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:9000';
const CHUNK_SIZE = 80 * 1024 * 1024; // 80 MB

export interface UploadResult {
  file_id: string;
  file_path: string;
  [key: string]: unknown;
}

async function getCsrfToken(): Promise<string | undefined> {
  const csrfToken = document.cookie.match(/(?:^|; )csrf_token=([^;]*)/)?.[1];
  if (csrfToken) return decodeURIComponent(csrfToken);
  try {
    const res = await fetch(`${API_BASE}/api/auth/csrf-token`, { credentials: 'include' });
    if (res.ok) return (await res.json()).csrf_token;
  } catch { /* best-effort */ }
  return undefined;
}

export function useChunkedUpload() {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);

  const upload = useCallback(async (file: File): Promise<UploadResult> => {
    setUploading(true);
    setProgress(0);

    try {
      const csrfToken = await getCsrfToken();
      const headers: Record<string, string> = {};
      if (csrfToken) headers['X-CSRF-Token'] = csrfToken;

      let data: UploadResult;

      if (file.size <= CHUNK_SIZE) {
        // Small file: single upload
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${API_BASE}/api/upload-video`, {
          method: 'POST',
          body: formData,
          credentials: 'include',
          headers: csrfToken ? { 'X-CSRF-Token': csrfToken } : undefined,
        });

        if (!response.ok) {
          const errBody = await response.json().catch(() => null);
          throw new Error(errBody?.detail || `Upload failed: ${response.statusText}`);
        }

        setProgress(100);
        data = await response.json();
      } else {
        // Large file: chunked upload
        const totalChunks = Math.ceil(file.size / CHUNK_SIZE);

        // 1. Init
        const initRes = await fetch(`${API_BASE}/api/upload-video/init`, {
          method: 'POST',
          credentials: 'include',
          headers: { ...headers, 'Content-Type': 'application/json' },
          body: JSON.stringify({ filename: file.name, total_size: file.size }),
        });
        if (!initRes.ok) {
          const errBody = await initRes.json().catch(() => null);
          throw new Error(errBody?.detail || `Init failed: ${initRes.statusText}`);
        }
        const { upload_id } = await initRes.json();

        // 2. Upload chunks with retry
        for (let i = 0; i < totalChunks; i++) {
          const start = i * CHUNK_SIZE;
          const end = Math.min(start + CHUNK_SIZE, file.size);
          const blob = file.slice(start, end);

          let success = false;
          for (let attempt = 0; attempt < 3; attempt++) {
            try {
              const chunkForm = new FormData();
              chunkForm.append('upload_id', upload_id);
              chunkForm.append('chunk_index', String(i));
              chunkForm.append('chunk', blob, file.name);

              const chunkRes = await fetch(`${API_BASE}/api/upload-video/chunk`, {
                method: 'POST',
                body: chunkForm,
                credentials: 'include',
                headers: csrfToken ? { 'X-CSRF-Token': csrfToken } : undefined,
              });

              if (!chunkRes.ok) {
                const errBody = await chunkRes.json().catch(() => null);
                throw new Error(errBody?.detail || `Chunk ${i} failed: ${chunkRes.statusText}`);
              }

              success = true;
              break;
            } catch (err) {
              if (attempt === 2) throw err;
              await new Promise((r) => setTimeout(r, 1000 * (attempt + 1)));
            }
          }

          if (!success) throw new Error(`Failed to upload chunk ${i} after 3 attempts`);
          setProgress(Math.round(((i + 1) / totalChunks) * 95));
        }

        // 3. Finalize
        const finalRes = await fetch(`${API_BASE}/api/upload-video/finalize`, {
          method: 'POST',
          credentials: 'include',
          headers: { ...headers, 'Content-Type': 'application/json' },
          body: JSON.stringify({ upload_id }),
        });
        if (!finalRes.ok) {
          const errBody = await finalRes.json().catch(() => null);
          throw new Error(errBody?.detail || `Finalize failed: ${finalRes.statusText}`);
        }

        setProgress(100);
        data = await finalRes.json();
      }

      return data;
    } finally {
      setUploading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setUploading(false);
    setProgress(0);
  }, []);

  return { upload, uploading, progress, reset };
}
