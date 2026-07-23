import { useMemo } from "react";
import UploadDropzone from "./components/UploadDropzone";
import ParameterControls from "./components/ParameterControls";
import StagePreviewTabs from "./components/StagePreviewTabs";
import SvgViewer from "./components/SvgViewer";
import PointsTable from "./components/PointsTable";
import DownloadBar from "./components/DownloadBar";
import { useImageProcessor } from "./hooks/useImageProcessor";

export default function App() {
  const { file, previewUrl, params, result, loading, error, selectFile, updateParams, reset } =
    useImageProcessor();

  const baseFileName = useMemo(() => {
    if (!file) return "extracted-outline";
    return file.name.replace(/\.[^.]+$/, "") + "-outline";
  }, [file]);

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div>
            <h1 className="text-lg font-semibold text-slate-900">Image → SVG Extraction Engine</h1>
            <p className="text-xs text-slate-500">
              Site boundaries, railway layouts, floor plans, building outlines, road layouts, polygons - generic,
              parameter-driven contour extraction. No manual tracing, no hardcoded coordinates.
            </p>
          </div>
          {file && (
            <button
              onClick={reset}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
            >
              Start over
            </button>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-6">
        {!file && (
          <div className="mx-auto max-w-xl pt-12">
            <UploadDropzone onFileSelected={selectFile} />
          </div>
        )}

        {file && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[280px_1fr]">
            <aside className="h-fit rounded-xl border border-slate-200 bg-white p-4">
              <ParameterControls params={params} onChange={updateParams} disabled={loading} />
            </aside>

            <section className="space-y-6">
              {error && (
                <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {error}
                </div>
              )}

              <div className="rounded-xl border border-slate-200 bg-white p-4">
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="text-sm font-semibold text-slate-800">Pipeline preview</h2>
                  {loading && <span className="text-xs text-slate-400">Processing…</span>}
                </div>
                {result ? (
                  <StagePreviewTabs stages={result.stages} />
                ) : (
                  <div className="flex h-64 items-center justify-center text-sm text-slate-400">
                    {loading ? "Running pipeline…" : "Waiting for first result…"}
                  </div>
                )}
              </div>

              <div className="rounded-xl border border-slate-200 bg-white p-4">
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="text-sm font-semibold text-slate-800">Extracted SVG</h2>
                  {result && <DownloadBar result={result} baseFileName={baseFileName} />}
                </div>
                {result ? (
                  <SvgViewer
                    svg={result.svg}
                    viewBox={result.view_box}
                    objects={result.objects}
                    originalImageUrl={previewUrl}
                  />
                ) : (
                  <div className="flex h-64 items-center justify-center text-sm text-slate-400">
                    The generated SVG will appear here.
                  </div>
                )}
              </div>

              {result && (
                <div className="rounded-xl border border-slate-200 bg-white p-4">
                  <h2 className="mb-3 text-sm font-semibold text-slate-800">Detected points</h2>
                  <PointsTable objects={result.objects} />
                </div>
              )}
            </section>
          </div>
        )}
      </main>
    </div>
  );
}
