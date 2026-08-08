import { useWorkbench } from "./workbench/useWorkbench";
import type { ConnectionState } from "./workbench/useWorkbench";
import {
  CITATION_PARTITIONS_FILENAME,
  CITATION_REPORT_FILENAME,
  downloadUrl,
} from "./workbench/api";
import type {
  CitationClaim,
  CitationCompletedData,
  CitationEvidence,
  CitationPartition,
  CitationReport,
  FileInfo,
  HealthInfo,
  RunStatus,
  TutorialEvent,
  UploadFileInfo,
} from "./workbench/types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const STATUS_LABELS: Record<RunStatus, string> = {
  idle: "Idle",
  uploading: "Uploading",
  ready: "Ready",
  running: "Running",
  success: "Success",
  failed: "Failed",
  cancelled: "Cancelled",
  "connection-error": "Connection error",
};

const CONNECTION_LABELS: Record<ConnectionState, string> = {
  connecting: "connecting",
  open: "open",
  closed: "closed",
  error: "error",
};

const REPORT_MARKDOWN_NAME = "tutorial-report.md";
const REPORT_PDF_NAME = "tutorial-report.pdf";

/** Only server-returned entries that are the expected report are linked. */
function isReportFile(file: FileInfo, reportName: string): boolean {
  return file.name === reportName || file.path === reportName;
}

function SessionHeader(props: {
  threadId: string;
  health: HealthInfo | null;
  healthError: string | null;
  onNewSession: () => void;
}) {
  return (
    <header className="session-header">
      <h1>Agent Engineering Research Copilot</h1>
      <p className="thread-label">
        Session: <code>{props.threadId}</code>
      </p>
      {props.health ? (
        <p className="health-modes">
          Runtime: {props.health.tutorial_runtime} · Web:{" "}
          {props.health.web_provider} · Catalog: {props.health.catalog_provider}{" "}
          · Knowledge: {props.health.knowledge_provider}
        </p>
      ) : props.healthError ? (
        <p className="health-error">Health unavailable: {props.healthError}</p>
      ) : (
        <p className="health-modes">Loading runtime and provider modes…</p>
      )}
      <button type="button" className="new-session" onClick={props.onNewSession}>
        New session
      </button>
    </header>
  );
}

function TaskComposer(props: {
  threadId: string;
  query: string;
  onQueryChange: (value: string) => void;
  selectedFile: File | null;
  onFileChange: (file: File | null) => void;
  uploadedFile: UploadFileInfo | null;
  onUpload: () => void;
  canUpload: boolean;
  canStart: boolean;
  canCancel: boolean;
  onStart: () => void;
  onCancel: () => void;
}) {
  return (
    <section className="task-composer" aria-labelledby="composer-heading">
      <h2 id="composer-heading">Research task</h2>
      <div className="field-row">
        <label htmlFor="constraint-file">Constraint file</label>
        <input
          id="constraint-file"
          type="file"
          key={props.threadId}
          onChange={(event) => props.onFileChange(event.target.files?.[0] ?? null)}
        />
        <button
          type="button"
          className="upload"
          onClick={props.onUpload}
          disabled={props.selectedFile === null || !props.canUpload}
        >
          Upload
        </button>
      </div>
      <p className="upload-status">
        {props.uploadedFile
          ? `Uploaded: ${props.uploadedFile.name} (${props.uploadedFile.size} bytes)`
          : "No file uploaded."}
      </p>
      <div className="field-row">
        <label htmlFor="research-query">Research query</label>
        <input
          id="research-query"
          type="text"
          value={props.query}
          onChange={(event) => props.onQueryChange(event.target.value)}
          placeholder="e.g. Compare renewable energy policies"
        />
      </div>
      <div className="actions">
        <button
          type="button"
          className="start"
          onClick={props.onStart}
          disabled={!props.canStart}
        >
          Start research
        </button>
        <button
          type="button"
          className="cancel"
          onClick={props.onCancel}
          disabled={!props.canCancel}
        >
          Cancel
        </button>
      </div>
    </section>
  );
}

function RunStatus(props: {
  status: RunStatus;
  connectionState: ConnectionState;
  error: string | null;
}) {
  return (
    <section className="run-status" aria-live="polite">
      <h2>Run status</h2>
      <p className={`status status-${props.status}`}>
        Status: {STATUS_LABELS[props.status]}
      </p>
      <p className="connection">Connection: {CONNECTION_LABELS[props.connectionState]}</p>
      {props.error ? <p className="error">{props.error}</p> : null}
    </section>
  );
}

function EventTimeline(props: { events: TutorialEvent[] }) {
  return (
    <section className="event-timeline" aria-labelledby="timeline-heading">
      <h2 id="timeline-heading">Event timeline</h2>
      {props.events.length === 0 ? (
        <p className="empty">No events yet.</p>
      ) : (
        <ul className="timeline">
          {props.events.map((event) => (
            <li
              key={`${event.thread_id}:${event.sequence}`}
              className="timeline-event"
            >
              <p className="event-meta">
                <span className="event-sequence">#{event.sequence}</span>
                <span className="event-time">
                  {new Date(event.timestamp).toLocaleTimeString()}
                </span>
                <span className="event-type">{event.type}</span>
              </p>
              <p className="event-message">{event.message}</p>
              {/* data is JSON text only — never markup. */}
              <pre className="event-data">
                {JSON.stringify(event.data, null, 2)}
              </pre>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function ArtifactPanel(props: {
  apiBaseUrl: string;
  threadId: string;
  files: FileInfo[];
  markdown: string | null;
  markdownError: string | null;
}) {
  const markdownFile = props.files.find((file) =>
    isReportFile(file, REPORT_MARKDOWN_NAME)
  );
  const pdfFile = props.files.find((file) => isReportFile(file, REPORT_PDF_NAME));
  return (
    <section className="artifact-panel" aria-labelledby="artifacts-heading">
      <h2 id="artifacts-heading">Artifacts</h2>
      {props.files.length === 0 ? <p className="empty">No artifacts yet.</p> : null}
      {props.files.length > 0 ? (
        <ul className="artifact-files">
          {props.files.map((file) => (
            <li key={file.path} className="artifact-file">
              {file.name} ({file.size} bytes)
            </li>
          ))}
        </ul>
      ) : null}
      {markdownFile ? (
        <div className="artifact-markdown">
          <h3>Markdown preview</h3>
          {props.markdown !== null ? (
            /* Report content is text nodes only — never markup. */
            <pre className="markdown-preview">{props.markdown}</pre>
          ) : props.markdownError !== null ? (
            <p className="preview-unavailable">{props.markdownError}</p>
          ) : (
            <p className="preview-loading">Loading preview…</p>
          )}
        </div>
      ) : props.files.length > 0 ? (
        <p className="empty">No Markdown report available.</p>
      ) : null}
      {props.markdownError !== null && props.files.length === 0 ? (
        <p className="preview-unavailable">{props.markdownError}</p>
      ) : null}
      <ul className="artifact-downloads">
        {markdownFile ? (
          <li>
            <a
              className="download download-markdown"
              href={downloadUrl(props.apiBaseUrl, props.threadId, markdownFile.path)}
              download={markdownFile.name}
            >
              Download Markdown
            </a>
          </li>
        ) : null}
        {pdfFile ? (
          <li>
            <a
              className="download download-pdf"
              href={downloadUrl(props.apiBaseUrl, props.threadId, pdfFile.path)}
              download={pdfFile.name}
            >
              Download PDF
            </a>
          </li>
        ) : null}
      </ul>
    </section>
  );
}

function ClaimView(props: { claim: CitationClaim }) {
  return (
    <li className="citation-claim">
      <p className="claim-text">{props.claim.claim}</p>
      {props.claim.support !== "" ? (
        /* Support states render as raw text so supported / unsupported /
           unknown / skipped stay distinct. */
        <p className="claim-support">Support: {props.claim.support}</p>
      ) : null}
      {props.claim.evidence.length > 0 ? (
        <ul className="evidence">
          {props.claim.evidence.map((evidence: CitationEvidence, index) => (
            <li key={index} className="evidence-item">
              <p className="evidence-snippet">{evidence.snippet}</p>
              <p className="evidence-source">Source: {evidence.source}</p>
            </li>
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function PartitionView(props: { partition: CitationPartition }) {
  const partition = props.partition;
  return (
    <li className="citation-partition">
      <h4>{partition.partition_id}</h4>
      {partition.support !== "" ? (
        <p className="partition-support">Support: {partition.support}</p>
      ) : null}
      {partition.metrics === null ? (
        <p className="metrics-empty">No metrics.</p>
      ) : (
        <ul className="metrics">
          {Object.entries(partition.metrics).map(([key, value]) => (
            <li key={key} className="metric">
              <span className="metric-key">{key}</span>: {String(value)}
            </li>
          ))}
        </ul>
      )}
      {partition.claims.length === 0 ? (
        <p className="empty">No claims.</p>
      ) : (
        <ul className="claims">
          {partition.claims.map((claim, index) => (
            <ClaimView
              key={`${partition.partition_id}:${index}`}
              claim={claim}
            />
          ))}
        </ul>
      )}
      {partition.limitations.length > 0 ? (
        <ul className="partition-limitations">
          {partition.limitations.map((limitation, index) => (
            <li key={index}>{limitation}</li>
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function CitationReportView(props: { citations: CitationReport }) {
  const citations = props.citations;
  return (
    <div className="citation-report">
      <p className="report-meta">
        Schema {citations.schema_version} · Dataset{" "}
        {citations.provenance.dataset_id} · Corpus {citations.provenance.corpus_id}
      </p>
      {citations.partitions.length === 0 ? (
        <p className="empty">No partitions in the report.</p>
      ) : (
        <ul className="citation-partitions">
          {citations.partitions.map((partition) => (
            <PartitionView key={partition.partition_id} partition={partition} />
          ))}
        </ul>
      )}
    </div>
  );
}

/**
 * Additive P4-5 citation panel: server-validated claims, evidence snippets,
 * support states, metrics, limitations and citation artifact download links.
 * Everything renders as text nodes — never markup.
 */
function CitationPanel(props: {
  apiBaseUrl: string;
  threadId: string;
  files: FileInfo[];
  summary: CitationCompletedData | null;
  citations: CitationReport | null;
  citationsLoading: boolean;
  citationsError: string | null;
}) {
  const citationReportFile = props.files.find(
    (file) =>
      file.name === CITATION_REPORT_FILENAME ||
      file.path === CITATION_REPORT_FILENAME
  );
  const citationPartitionsFile = props.files.find(
    (file) =>
      file.name === CITATION_PARTITIONS_FILENAME ||
      file.path === CITATION_PARTITIONS_FILENAME
  );
  const hasData = props.summary !== null || props.citations !== null;
  return (
    <section className="citation-panel" aria-labelledby="citations-heading">
      <h2 id="citations-heading">Citations</h2>
      {!hasData && !props.citationsLoading && props.citationsError === null ? (
        <p className="empty">No citation results yet.</p>
      ) : null}
      {props.citationsLoading ? (
        <p className="preview-loading">Loading citation results…</p>
      ) : null}
      {props.summary !== null ? (
        <div className="citation-summary">
          <p className="citation-status">Evaluation: {props.summary.status}</p>
          <p className="citation-partitions-count">
            Partitions evaluated: {props.summary.partition_count}
          </p>
          <p className="citation-fingerprint">
            Report fingerprint: {props.summary.report_fingerprint}
          </p>
        </div>
      ) : null}
      {props.summary !== null && props.summary.limitations.length > 0 ? (
        <div className="citation-limitations">
          <h3>Limitations</h3>
          <ul className="limitations-list">
            {props.summary.limitations.map((limitation, index) => (
              <li key={index}>{limitation}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {props.citations !== null ? (
        <CitationReportView citations={props.citations} />
      ) : null}
      {props.citationsError !== null ? (
        <p className="preview-unavailable">{props.citationsError}</p>
      ) : null}
      <ul className="citation-downloads">
        {citationReportFile !== undefined ? (
          <li>
            <a
              className="download download-citation-report"
              href={downloadUrl(
                props.apiBaseUrl,
                props.threadId,
                citationReportFile.path
              )}
              download={citationReportFile.name}
            >
              Download citation report
            </a>
          </li>
        ) : null}
        {citationPartitionsFile !== undefined ? (
          <li>
            <a
              className="download download-citation-partitions"
              href={downloadUrl(
                props.apiBaseUrl,
                props.threadId,
                citationPartitionsFile.path
              )}
              download={citationPartitionsFile.name}
            >
              Download citation partitions
            </a>
          </li>
        ) : null}
      </ul>
    </section>
  );
}

function App() {
  const workbench = useWorkbench(API_BASE_URL);
  const taskActive =
    workbench.status === "uploading" || workbench.status === "running";
  const canUpload = !taskActive && !workbench.taskStartPending;
  const canStart =
    workbench.uploadedFile !== null &&
    workbench.query.trim() !== "" &&
    !taskActive &&
    !workbench.taskStartPending &&
    workbench.connectionState === "open";
  const canCancel = workbench.status === "running";

  return (
    <main className="workbench">
      <SessionHeader
        threadId={workbench.threadId}
        health={workbench.health}
        healthError={workbench.healthError}
        onNewSession={workbench.newSession}
      />
      <TaskComposer
        threadId={workbench.threadId}
        query={workbench.query}
        onQueryChange={workbench.setQuery}
        selectedFile={workbench.selectedFile}
        onFileChange={workbench.selectFile}
        uploadedFile={workbench.uploadedFile}
        onUpload={workbench.upload}
        canUpload={canUpload}
        canStart={canStart}
        canCancel={canCancel}
        onStart={workbench.submit}
        onCancel={workbench.cancel}
      />
      <RunStatus
        status={workbench.status}
        connectionState={workbench.connectionState}
        error={workbench.error}
      />
      <EventTimeline events={workbench.events} />
      <ArtifactPanel
        apiBaseUrl={API_BASE_URL}
        threadId={workbench.threadId}
        files={workbench.files}
        markdown={workbench.markdown}
        markdownError={workbench.markdownError}
      />
      <CitationPanel
        apiBaseUrl={API_BASE_URL}
        threadId={workbench.threadId}
        files={workbench.files}
        summary={workbench.citationSummary}
        citations={workbench.citations}
        citationsLoading={workbench.citationsLoading}
        citationsError={workbench.citationsError}
      />
    </main>
  );
}

export default App;
