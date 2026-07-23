import { useCallback, useRef, useState } from "react";
import type { DragEvent } from "react";

interface Props {
  onFileSelected: (file: File) => void;
  acceptedExtensions?: string[];
}

const DEFAULT_ACCEPTED = [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"];

export default function UploadDropzone({ onFileSelected, acceptedExtensions = DEFAULT_ACCEPTED }: Props) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const validateAndEmit = useCallback(
    (file: File | undefined) => {
      if (!file) return;
      const lowerName = file.name.toLowerCase();
      const isAccepted = acceptedExtensions.some((ext) => lowerName.endsWith(ext));
      if (!isAccepted) {
        setValidationError(`Unsupported file type. Accepted: ${acceptedExtensions.join(", ")}`);
        return;
      }
      setValidationError(null);
      onFileSelected(file);
    },
    [acceptedExtensions, onFileSelected],
  );

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
        onDragOver={(e: DragEvent) => {
          e.preventDefault();
          setIsDragOver(true);
        }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={(e: DragEvent) => {
          e.preventDefault();
          setIsDragOver(false);
          validateAndEmit(e.dataTransfer.files?.[0]);
        }}
        className={[
          "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-10 text-center transition-colors",
          isDragOver ? "border-brand-500 bg-brand-50" : "border-slate-300 bg-white hover:border-brand-400",
        ].join(" ")}
      >
        <svg
          className="h-10 w-10 text-slate-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 8.25L12 3.75m0 0L7.5 8.25M12 3.75v13.5"
          />
        </svg>
        <p className="text-sm font-medium text-slate-700">
          Drag &amp; drop an image, or <span className="text-brand-600">browse</span>
        </p>
        <p className="text-xs text-slate-400">
          Site boundaries, railway layouts, floor plans, building outlines, road layouts, polygons - {acceptedExtensions.join(", ")}
        </p>
        <input
          ref={inputRef}
          type="file"
          accept={acceptedExtensions.join(",")}
          className="hidden"
          onChange={(e) => validateAndEmit(e.target.files?.[0])}
        />
      </div>
      {validationError && <p className="mt-2 text-sm text-red-600">{validationError}</p>}
    </div>
  );
}
