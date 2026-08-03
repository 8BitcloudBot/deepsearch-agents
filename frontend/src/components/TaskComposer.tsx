import { useRef, useState } from "react";
import { FolderUp, Play, Square, Upload } from "lucide-react";
import type { SessionStatus, UploadFileInfo } from "../types";

interface TaskComposerProps {
  status: SessionStatus;
  uploading: boolean;
  uploadedFiles: UploadFileInfo[];
  onRun: (query: string) => void;
  onCancel: () => void;
  onUpload: (files: File[]) => void;
}

export function TaskComposer({
  status,
  uploading,
  uploadedFiles,
  onRun,
  onCancel,
  onUpload,
}: TaskComposerProps) {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const busy = status === "connecting" || status === "running";
  const canCancel = status === "connecting" || status === "running";

  return (
    <section aria-label="Task composer" className="composer">
      <label className="field-label" htmlFor="task-query">
        Task query
      </label>
      <textarea
        id="task-query"
        aria-label="Task query"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="e.g. research aspirin side effects and write a report"
        rows={5}
      />

      <div className="field-block">
        <label className="field-label" htmlFor="constraint-files">
          Constraint files
        </label>
        <div className="file-row">
          <input
            id="constraint-files"
            aria-label="Constraint files"
            type="file"
            multiple
            ref={fileInputRef}
            onChange={(e) => setSelected(Array.from(e.target.files ?? []))}
          />
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => {
              if (selected.length > 0) {
                onUpload(selected);
                setSelected([]);
                if (fileInputRef.current) fileInputRef.current.value = "";
              }
            }}
            disabled={selected.length === 0 || uploading}
          >
            <Upload size={14} aria-hidden="true" />
            Upload
          </button>
        </div>
        {selected.length > 0 && (
          <ul className="file-list" aria-label="Files to upload">
            {selected.map((f) => (
              <li key={f.name}>
                <FolderUp size={13} aria-hidden="true" />
                {f.name}
              </li>
            ))}
          </ul>
        )}
        {uploadedFiles.length > 0 && (
          <ul className="file-list uploaded" aria-label="Uploaded files">
            {uploadedFiles.map((f) => (
              <li key={f.name}>
                <FolderUp size={13} aria-hidden="true" />
                {f.name}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="actions">
        {canCancel ? (
          <button
            type="button"
            className="btn btn-cancel"
            onClick={onCancel}
          >
            <Square size={14} aria-hidden="true" />
            Cancel Task
          </button>
        ) : (
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => onRun(query)}
            disabled={!query.trim() || busy}
          >
            <Play size={14} aria-hidden="true" />
            Run Task
          </button>
        )}
      </div>
    </section>
  );
}
