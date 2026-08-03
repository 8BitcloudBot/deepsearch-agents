import { Download, Eye, FileText } from "lucide-react";
import { downloadUrl } from "../lib/api";
import type { FileInfo } from "../types";

interface ArtifactListProps {
  threadId: string;
  artifacts: FileInfo[];
  previewing: string | null;
  onPreview: (artifact: FileInfo) => void;
}

function isMarkdown(file: FileInfo): boolean {
  return (
    file.media_type === "text/markdown" ||
    file.name.toLowerCase().endsWith(".md")
  );
}

export function ArtifactList({
  threadId,
  artifacts,
  previewing,
  onPreview,
}: ArtifactListProps) {
  return (
    <section aria-label="Artifacts" className="artifacts">
      <h2 className="panel-title">Artifacts</h2>
      {artifacts.length === 0 ? (
        <p className="artifacts-empty">No artifacts yet.</p>
      ) : (
        <ul className="artifact-list">
          {artifacts.map((file) => (
            <li key={file.path} className="artifact-item">
              <span className="artifact-name">
                <FileText size={14} aria-hidden="true" />
                {file.name}
              </span>
              <span className="artifact-actions">
                <a
                  className="btn btn-link"
                  aria-label={`Download ${file.name}`}
                  href={downloadUrl(threadId, file.path)}
                >
                  <Download size={14} aria-hidden="true" />
                  Download
                </a>
                {isMarkdown(file) && (
                  <button
                    type="button"
                    className="btn btn-link"
                    aria-label={`Preview ${file.name}`}
                    onClick={() => onPreview(file)}
                    disabled={previewing === file.path}
                  >
                    <Eye size={14} aria-hidden="true" />
                    Preview
                  </button>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
