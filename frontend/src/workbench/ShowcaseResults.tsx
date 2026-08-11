import { downloadUrl } from "./api";
import type {
  FileInfo,
  LiveCitationDocument,
  LiveCitationProgress,
  LiveDeliveryStatus,
  LiveEvidence,
  LiveSource,
  LiveSourceKind,
} from "./types";

const SOURCE_KINDS: readonly LiveSourceKind[] = [
  "web",
  "mysql",
  "knowledge",
  "uploaded-file",
];

const SOURCE_LABELS: Record<LiveSourceKind, string> = {
  web: "Web",
  mysql: "MySQL",
  knowledge: "Knowledge base",
  "uploaded-file": "Uploaded file",
};

export interface ShowcaseResultsProps {
  apiBaseUrl: string;
  threadId: string;
  document: LiveCitationDocument | null;
  loading: boolean;
  error: string | null;
  deliveryStatus: LiveDeliveryStatus;
  progress: LiveCitationProgress | null;
  files: FileInfo[];
  markdown: string | null;
  markdownError: string | null;
}

function reportFile(files: FileInfo[], name: string): FileInfo | undefined {
  return files.find((file) => file.name === name || file.path === name);
}

function SourceLink({ apiBaseUrl, source }: { apiBaseUrl: string; source: LiveSource }) {
  if (source.safe_display_link === undefined) return null;
  if (source.source_kind === "web") {
    return (
      <a
        className="source-link source-link-web"
        href={source.safe_display_link}
        target="_blank"
        rel="noreferrer noopener"
      >
        Open Web source
      </a>
    );
  }
  if (source.source_kind === "uploaded-file") {
    return (
      <a
        className="source-link source-link-upload"
        href={`${apiBaseUrl.replace(/\/+$/, "")}${source.safe_display_link}`}
      >
        Open uploaded source
      </a>
    );
  }
  return null;
}

function EvidenceView(props: {
  evidence: LiveEvidence;
  source: LiveSource;
}) {
  return (
    <li className={`live-evidence source-kind-${props.evidence.source_kind}`}>
      <blockquote>{props.evidence.quote}</blockquote>
      <p className="live-evidence-meta">
        {props.source.title} · {SOURCE_LABELS[props.evidence.source_kind]}
      </p>
      <p className="live-locator">
        Locator: {props.evidence.locator.kind}={props.evidence.locator.value}
      </p>
    </li>
  );
}

function ShowcaseReports(props: ShowcaseResultsProps) {
  const markdownFile = reportFile(props.files, "showcase-report.md");
  const pdfFile = reportFile(props.files, "showcase-report.pdf");
  return (
    <section className="showcase-reports" aria-labelledby="showcase-reports-heading">
      <h3 id="showcase-reports-heading">Reports</h3>
      {markdownFile ? (
        <div className="showcase-preview">
          <h4>Markdown preview</h4>
          {props.markdown !== null ? (
            <pre>{props.markdown}</pre>
          ) : props.markdownError !== null ? (
            <p className="preview-unavailable">{props.markdownError}</p>
          ) : (
            <p className="preview-loading">Loading preview…</p>
          )}
        </div>
      ) : null}
      {!markdownFile && !pdfFile ? <p className="empty">No reports yet.</p> : null}
      <ul className="showcase-downloads">
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

export function ShowcaseResults(props: ShowcaseResultsProps) {
  if (
    props.document === null &&
    !props.loading &&
    props.error === null &&
    props.deliveryStatus === "idle"
  ) {
    return null;
  }

  const document = props.document;
  const sourceById = new Map(
    document?.sources.map((source) => [source.source_id, source]) ?? []
  );
  const evidenceById = new Map(
    document?.evidence.map((evidence) => [evidence.evidence_id, evidence]) ?? []
  );

  return (
    <section className="showcase-results" aria-labelledby="showcase-results-heading">
      <header className="showcase-results-header">
        <p className="eyebrow">Validated live research</p>
        <h2 id="showcase-results-heading">Research results</h2>
        {props.progress ? (
          <p className="live-progress">
            {props.progress.claimCount} claims · {props.progress.evidenceCount} evidence
            records
          </p>
        ) : null}
        {props.loading ? (
          <p className="preview-loading">Loading live citation results…</p>
        ) : null}
        {props.error ? <p className="live-error">{props.error}</p> : null}
      </header>

      {document ? (
        <div className="showcase-result-grid">
          <div className="showcase-main">
            <section className="showcase-answer" aria-labelledby="showcase-answer-heading">
              <h3 id="showcase-answer-heading">Research answer</h3>
              <p>{document.answer}</p>
            </section>
            <section className="showcase-claims" aria-labelledby="showcase-claims-heading">
              <h3 id="showcase-claims-heading">Claims and evidence</h3>
              {document.claims.length === 0 ? (
                <p className="empty">No claims were produced.</p>
              ) : (
                <ol>
                  {document.claims.map((claim, claimIndex) => {
                    const linked = claim.evidence_ids
                      .map((evidenceId) => evidenceById.get(evidenceId))
                      .filter((item): item is LiveEvidence => item !== undefined);
                    return (
                      <li key={claim.claim_id} className="showcase-claim">
                        <details open={claimIndex === 0}>
                          <summary>
                            <span>{claim.claim_id}</span>
                            {claim.statement}
                          </summary>
                          {linked.length === 0 ? (
                            <p className="empty">No evidence is linked to this claim.</p>
                          ) : (
                            <ul className="live-evidence-list">
                              {linked.map((item) => {
                                const source = sourceById.get(item.source_id);
                                return source ? (
                                  <EvidenceView
                                    key={item.evidence_id}
                                    evidence={item}
                                    source={source}
                                  />
                                ) : null;
                              })}
                            </ul>
                          )}
                        </details>
                      </li>
                    );
                  })}
                </ol>
              )}
            </section>
          </div>

          <aside className="showcase-inspection" aria-label="Source inspection">
            <section className="source-coverage" aria-labelledby="coverage-heading">
              <h3 id="coverage-heading">Source coverage</h3>
              <ul aria-label="Source coverage">
                {SOURCE_KINDS.map((kind) => {
                  const sourceCount = document.sources.filter(
                    (source) => source.source_kind === kind
                  ).length;
                  const evidenceCount = document.evidence.filter(
                    (item) => item.source_kind === kind
                  ).length;
                  const limited = document.limitations.some(
                    (item) => item.source_kind === kind
                  );
                  return (
                    <li key={kind} className={`coverage-row source-kind-${kind}`}>
                      <span>{SOURCE_LABELS[kind]}</span>
                      <span>
                        {sourceCount} sources · {evidenceCount} evidence
                        {limited ? " · limited" : ""}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </section>

            <section className="showcase-limitations" aria-labelledby="limitations-heading">
              <h3 id="limitations-heading">Limitations</h3>
              {document.limitations.length === 0 ? (
                <p className="empty">No limitations reported.</p>
              ) : (
                <ul>
                  {document.limitations.map((limitation, index) => (
                    <li key={`${limitation.code}:${index}`}>
                      <span>{limitation.code}</span>: {limitation.message}
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="showcase-sources" aria-labelledby="sources-heading">
              <h3 id="sources-heading">Sources</h3>
              {document.sources.length === 0 ? (
                <p className="empty">No valid sources were collected.</p>
              ) : (
                <ul>
                  {document.sources.map((source) => (
                    <li
                      key={source.source_id}
                      className={`showcase-source source-kind-${source.source_kind}`}
                    >
                      <h4>{source.title}</h4>
                      <p>{source.display_text}</p>
                      <p>Captured: {source.captured_at}</p>
                      <p>Version: {source.version}</p>
                      <p className="live-locator">
                        Locator: {source.locator.kind}={source.locator.value}
                      </p>
                      <SourceLink apiBaseUrl={props.apiBaseUrl} source={source} />
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <ShowcaseReports {...props} />
          </aside>
        </div>
      ) : null}
    </section>
  );
}
