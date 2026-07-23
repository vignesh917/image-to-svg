import type { ProcessingParams, ProcessingResult } from "../types";
import { ApiError } from "../types";

// In dev, Vite's proxy (see vite.config.ts) forwards "/api" to the FastAPI
// server, so relative paths work with zero configuration. In production,
// point VITE_API_BASE_URL at the deployed backend origin.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

async function parseErrorBody(response: Response): Promise<string> {
  try {
    const body = await response.json();
    return body?.detail || body?.error || response.statusText;
  } catch {
    return response.statusText || `HTTP ${response.status}`;
  }
}

/**
 * Upload an image and run the full pipeline. `params` may be a partial
 * object - anything omitted uses the backend's documented default, so
 * callers never need to send every field.
 */
export async function processImage(
  file: File,
  params: Partial<ProcessingParams>,
  signal?: AbortSignal,
): Promise<ProcessingResult> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("params", JSON.stringify(params));

  const response = await fetch(`${API_BASE_URL}/api/process`, {
    method: "POST",
    body: formData,
    signal,
  });

  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorBody(response));
  }

  return (await response.json()) as ProcessingResult;
}

export async function fetchHealth(): Promise<{ status: string; service: string }> {
  const response = await fetch(`${API_BASE_URL}/api/health`);
  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorBody(response));
  }
  return response.json();
}

export async function fetchSupportedFormats(): Promise<{
  extensions: string[];
  content_types: string[];
  max_upload_mb: number;
}> {
  const response = await fetch(`${API_BASE_URL}/api/formats`);
  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorBody(response));
  }
  return response.json();
}
