import { useState } from "react";
import { API_BASE_URL } from "./lib/api";
import { useTutorialSession } from "./hooks/useTutorialSession";
import { TaskComposer } from "./components/TaskComposer";
import { RunStatus } from "./components/RunStatus";
import { EventFeed } from "./components/EventFeed";
import { ArtifactList } from "./components/ArtifactList";
import { ReportPreview } from "./components/ReportPreview";
import type { FileInfo } from "./types";

function App() {
  const session = useTutorialSession(API_BASE_URL);
  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState<FileInfo | null>(null);

  const handleUpload = async (files: File[]) => {
    setUploading(true);
    try {
      await session.upload(files);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="workbench">
      <header className="workbench-header">
        <h1>Tutorial Workbench</h1>
        <p className="workbench-subtitle">
          Phase 2A — live task run with event stream and artifact review
        </p>
      </header>

      <div className="workbench-grid">
        <aside className="panel panel-composer">
          <RunStatus status={session.status} error={session.error} />
          <TaskComposer
            status={session.status}
            uploading={uploading}
            uploadedFiles={session.uploadedFiles}
            onRun={session.run}
            onCancel={() => void session.cancel()}
            onUpload={(files) => void handleUpload(files)}
          />
        </aside>

        <main className="panel panel-feed">
          <EventFeed events={session.events} />
        </main>

        <aside className="panel panel-artifacts">
          <ArtifactList
            threadId={session.threadId}
            artifacts={session.artifacts}
            previewing={preview?.path ?? null}
            onPreview={setPreview}
          />
          <ReportPreview
            threadId={session.threadId}
            artifact={preview}
            onClose={() => setPreview(null)}
          />
        </aside>
      </div>
    </div>
  );
}

export default App;
