import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { FileText } from "lucide-react";
import { downloadUrl, fetchText } from "../lib/api";
import type { FileInfo } from "../types";

interface ReportPreviewProps {
  threadId: string;
  artifact: FileInfo | null;
  onClose: () => void;
}

type PreviewState =
  | { phase: "loading" }
  | { phase: "ready"; markdown: string }
  | { phase: "failed"; error: string };

export function ReportPreview({
  threadId,
  artifact,
  onClose,
}: ReportPreviewProps) {
  const [state, setState] = useState<PreviewState | null>(null);

  useEffect(() => {
    if (!artifact) {
      setState(null);
      return;
    }
    let cancelled = false;
    setState({ phase: "loading" });
    fetchText(downloadUrl(threadId, artifact.path))
      .then((markdown) => {
        if (!cancelled) setState({ phase: "ready", markdown });
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setState({
            phase: "failed",
            error: err instanceof Error ? err.message : String(err),
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [artifact, threadId]);

  if (!artifact || !state) return null;

  return (
    <section aria-label="Report preview" className="preview">
      <div className="preview-header">
        <h2 className="panel-title">Preview</h2>
        <button
          type="button"
          className="btn btn-link"
          aria-label="Close preview"
          onClick={onClose}
        >
          Close
        </button>
      </div>
      <div className="preview-body">
        {state.phase === "loading" && (
          <p className="preview-hint">
            <FileText size={14} aria-hidden="true" /> Loading {artifact.name}…
          </p>
        )}
        {state.phase === "failed" && (
          <p className="preview-error">Error: {state.error}</p>
        )}
        {state.phase === "ready" && (
          <div className="markdown">
            <ReactMarkdown>{state.markdown}</ReactMarkdown>
          </div>
        )}
      </div>
    </section>
  );
}
