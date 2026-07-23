import { useCallback, useEffect, useRef, useState } from "react";
import { processImage } from "../api/client";
import { ApiError, DEFAULT_PARAMS, type ProcessingParams, type ProcessingResult } from "../types";

const DEBOUNCE_MS = 400;

/**
 * Owns the whole "upload -> tune parameters -> re-process" workflow.
 * Re-processing is debounced and automatically cancels any in-flight
 * request, so rapidly dragging a slider doesn't pile up requests or let
 * a stale response overwrite a newer one.
 */
export function useImageProcessor() {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [params, setParams] = useState<ProcessingParams>(DEFAULT_PARAMS);
  const [result, setResult] = useState<ProcessingResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const runNow = useCallback(async (targetFile: File, targetParams: ProcessingParams) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);
    try {
      const res = await processImage(targetFile, targetParams, controller.signal);
      setResult(res);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Unexpected error while processing the image.");
      }
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const selectFile = useCallback((newFile: File) => {
    setFile(newFile);
    setResult(null);
    setError(null);
    setPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return URL.createObjectURL(newFile);
    });
  }, []);

  const updateParams = useCallback((patch: Partial<ProcessingParams>) => {
    setParams((prev) => ({ ...prev, ...patch }));
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setFile(null);
    setResult(null);
    setError(null);
    setPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return null;
    });
    setParams(DEFAULT_PARAMS);
  }, []);

  // Debounced auto-reprocessing whenever the file or params change.
  useEffect(() => {
    if (!file) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      void runNow(file, params);
    }, DEBOUNCE_MS);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [file, params, runNow]);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    file,
    previewUrl,
    params,
    result,
    loading,
    error,
    selectFile,
    updateParams,
    reset,
    reprocessNow: () => file && runNow(file, params),
  };
}
