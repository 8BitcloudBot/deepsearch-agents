import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import {
  getLiveCitations,
  parseLiveCitationDocument,
} from "./api";
import { ShowcaseResults } from "./ShowcaseResults";

const THREAD_ID = "aaaaaaaa-0000-4000-8000-000000000101";
const OTHER_THREAD_ID = "bbbbbbbb-0000-4000-8000-000000000102";
const UNAVAILABLE = "Live citation results are unavailable.";

function source(
  source_id: string,
  source_kind: "web" | "mysql" | "knowledge" | "uploaded-file",
  locator: { kind: "url" | "row" | "chunk" | "span"; value: string },
  safe_display_link?: unknown
) {
  return {
    type: "live_source_result",
    source_id,
    source_kind,
    title: `${source_kind} source`,
    captured_at: "2026-08-10T08:00:00Z",
    version: "1.0.0",
    display_text: `${source_kind} display text`,
    locator,
    execution_mode: "live",
    evidence_partition: "live",
    ...(safe_display_link === undefined ? {} : { safe_display_link }),
  };
}

function evidence(
  evidence_id: string,
  source_id: string,
  source_kind: "web" | "mysql" | "knowledge" | "uploaded-file",
  locator: { kind: "url" | "row" | "chunk" | "span"; value: string }
) {
  return {
    evidence_id,
    source_id,
    source_kind,
    locator,
    quote: `${source_kind} evidence`,
    content_sha256: "a".repeat(64),
    thread_id: source_kind === "uploaded-file" ? THREAD_ID : null,
  };
}

function liveDocument() {
  const webLocator = { kind: "url" as const, value: "https://example.com/a" };
  const mysqlLocator = { kind: "row" as const, value: "catalog/items#id=7" };
  const knowledgeLocator = { kind: "chunk" as const, value: "kb/doc/chunk-3" };
  const uploadLocator = {
    kind: "span" as const,
    value: "brief notes.md:1-3",
  };
  const limitations: Array<{
    code: string;
    source_kind: "web" | "mysql" | "knowledge" | "uploaded-file" | null;
    message: string;
  }> = [
    { code: "partial-source", source_kind: "mysql", message: "Partial rows." },
  ];
  return {
    schema_version: "2.0.0",
    thread_id: THREAD_ID,
    answer: "A deterministic answer.",
    claims: [
      {
        claim_id: "claim-1",
        statement: "First claim.",
        evidence_ids: ["ev-live-web", "ev-live-upload"],
      },
      {
        claim_id: "claim-2",
        statement: "Second claim.",
        evidence_ids: ["ev-live-mysql", "ev-live-knowledge"],
      },
    ],
    sources: [
      source("src-web", "web", webLocator, webLocator.value),
      source("src-mysql", "mysql", mysqlLocator),
      source("src-knowledge", "knowledge", knowledgeLocator),
      source(
        "src-upload",
        "uploaded-file",
        uploadLocator,
        `/api/threads/${THREAD_ID}/uploads/brief%20notes.md`
      ),
    ],
    evidence: [
      evidence("ev-live-web", "src-web", "web", webLocator),
      evidence("ev-live-mysql", "src-mysql", "mysql", mysqlLocator),
      evidence("ev-live-knowledge", "src-knowledge", "knowledge", knowledgeLocator),
      evidence("ev-live-upload", "src-upload", "uploaded-file", uploadLocator),
    ],
    limitations,
    artifacts: [
      "live-citations.json",
      "showcase-report.md",
      "showcase-report.pdf",
    ],
  };
}

function clone<T>(value: T): T {
  return structuredClone(value);
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("live citation parser", () => {
  it("constructs an exact typed document with validated Web and upload links", () => {
    const parsed = parseLiveCitationDocument(liveDocument(), THREAD_ID);

    expect(parsed.thread_id).toBe(THREAD_ID);
    expect(parsed.claims.map((claim) => claim.claim_id)).toEqual([
      "claim-1",
      "claim-2",
    ]);
    expect(parsed.sources.map((item) => item.safe_display_link)).toEqual([
      "https://example.com/a",
      undefined,
      undefined,
      `/api/threads/${THREAD_ID}/uploads/brief%20notes.md`,
    ]);
    expect(parsed).not.toBe(liveDocument());
  });

  it.each([
    ["foreign thread", (value: ReturnType<typeof liveDocument>) => {
      value.thread_id = OTHER_THREAD_ID;
    }],
    ["wrong schema", (value: ReturnType<typeof liveDocument>) => {
      value.schema_version = "1.0.0";
    }],
    ["wrong artifacts", (value: ReturnType<typeof liveDocument>) => {
      value.artifacts.reverse();
    }],
    ["non-sequential claim", (value: ReturnType<typeof liveDocument>) => {
      value.claims[1].claim_id = "claim-3";
    }],
    ["unknown evidence", (value: ReturnType<typeof liveDocument>) => {
      value.claims[0].evidence_ids = ["ev-live-missing"];
    }],
    ["duplicate evidence reference", (value: ReturnType<typeof liveDocument>) => {
      value.claims[0].evidence_ids = ["ev-live-web", "ev-live-web"];
    }],
    ["duplicate source id", (value: ReturnType<typeof liveDocument>) => {
      value.sources[1].source_id = "src-web";
    }],
    ["duplicate evidence id", (value: ReturnType<typeof liveDocument>) => {
      value.evidence[1].evidence_id = "ev-live-web";
    }],
    ["invalid source locator pair", (value: ReturnType<typeof liveDocument>) => {
      value.sources[0].locator = { kind: "row", value: "row-1" };
    }],
    ["evidence source mismatch", (value: ReturnType<typeof liveDocument>) => {
      value.evidence[0].source_id = "src-mysql";
    }],
    ["evidence locator mismatch", (value: ReturnType<typeof liveDocument>) => {
      value.evidence[0].locator = {
        ...value.evidence[0].locator,
        value: "https://example.com/other",
      };
    }],
    ["foreign upload evidence", (value: ReturnType<typeof liveDocument>) => {
      value.evidence[3].thread_id = OTHER_THREAD_ID;
    }],
    ["thread on Web evidence", (value: ReturnType<typeof liveDocument>) => {
      value.evidence[0].thread_id = THREAD_ID;
    }],
    ["offline execution", (value: ReturnType<typeof liveDocument>) => {
      value.sources[0].execution_mode = "offline";
    }],
    ["offline partition", (value: ReturnType<typeof liveDocument>) => {
      value.sources[0].evidence_partition = "offline";
    }],
    ["malformed hash", (value: ReturnType<typeof liveDocument>) => {
      value.evidence[0].content_sha256 = "not-a-hash";
    }],
    ["unknown source field", (value: ReturnType<typeof liveDocument>) => {
      Object.assign(value.sources[0], { raw_response: "secret" });
    }],
  ])("rejects %s with one stable error", (_label, mutate) => {
    const value = clone(liveDocument());
    mutate(value);

    expect(() => parseLiveCitationDocument(value, THREAD_ID)).toThrow(UNAVAILABLE);
  });

  it.each([
    "javascript:alert(1)",
    "file:///Users/example/private.txt",
    "https://user:secret@example.com/a",
    "https://example.com/other",
  ])("omits an invalid Web display link without dropping its source", (link) => {
    const value = liveDocument();
    value.sources[0].safe_display_link = link;

    const parsed = parseLiveCitationDocument(value, THREAD_ID);

    expect(parsed.sources[0].source_id).toBe("src-web");
    expect(parsed.sources[0].safe_display_link).toBeUndefined();
  });

  it("omits a credentialed Web link even when it matches the locator", () => {
    const value = liveDocument();
    const credentialed = "https://user:pass@example.com/a";
    value.sources[0].locator.value = credentialed;
    value.sources[0].safe_display_link = credentialed;
    value.evidence[0].locator.value = credentialed;

    const parsed = parseLiveCitationDocument(value, THREAD_ID);

    expect(parsed.sources[0].safe_display_link).toBeUndefined();
  });

  it.each([
    `/api/threads/${OTHER_THREAD_ID}/uploads/brief%20notes.md`,
    `/api/threads/${THREAD_ID}/uploads/..%2Fbrief.md`,
    `/api/threads/${THREAD_ID}/uploads/folder%2Fbrief.md`,
    "/api/download?path=brief%20notes.md",
  ])("omits an invalid upload display link without dropping its source", (link) => {
    const value = liveDocument();
    value.sources[3].safe_display_link = link;

    const parsed = parseLiveCitationDocument(value, THREAD_ID);

    expect(parsed.sources[3].source_id).toBe("src-upload");
    expect(parsed.sources[3].safe_display_link).toBeUndefined();
  });

  it("omits links supplied for MySQL and Knowledge base sources", () => {
    const value = liveDocument();
    value.sources[1].safe_display_link = "https://example.com/mysql";
    value.sources[2].safe_display_link = "https://example.com/knowledge";

    const parsed = parseLiveCitationDocument(value, THREAD_ID);

    expect(parsed.sources[1].safe_display_link).toBeUndefined();
    expect(parsed.sources[2].safe_display_link).toBeUndefined();
  });

  it("requests the thread-scoped endpoint and validates both wrapper and document", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ thread_id: THREAD_ID, document: liveDocument() }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await getLiveCitations("http://127.0.0.1:8000/", THREAD_ID);

    expect(result.thread_id).toBe(THREAD_ID);
    expect(fetchMock).toHaveBeenCalledWith(
      `http://127.0.0.1:8000/api/live-citations?thread_id=${THREAD_ID}`,
      undefined
    );
  });

  it("rejects a foreign response wrapper without exposing its body", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            thread_id: OTHER_THREAD_ID,
            document: { secret: "/Users/example/private.txt" },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
    );

    await expect(
      getLiveCitations("http://127.0.0.1:8000", THREAD_ID)
    ).rejects.toThrow(UNAVAILABLE);
  });

  it("preserves safe paragraph breaks but rejects non-text controls", () => {
    const value = liveDocument();
    value.answer = "First paragraph.\n\nSecond paragraph.";
    value.claims[0].statement = "First line.\nSecond line.";
    value.evidence[0].quote = "Quoted line one.\nQuoted line two.";

    const parsed = parseLiveCitationDocument(value, THREAD_ID);

    expect(parsed.answer).toBe(value.answer);
    expect(parsed.claims[0].statement).toBe(value.claims[0].statement);
    expect(parsed.evidence[0].quote).toBe(value.evidence[0].quote);

    value.evidence[0].quote = "unsafe\u0000quote";
    expect(() => parseLiveCitationDocument(value, THREAD_ID)).toThrow(UNAVAILABLE);
  });
});

describe("ShowcaseResults", () => {
  function renderResults(overrides: Record<string, unknown> = {}) {
    const document = parseLiveCitationDocument(liveDocument(), THREAD_ID);
    return render(
      <ShowcaseResults
        apiBaseUrl="http://127.0.0.1:8000"
        threadId={THREAD_ID}
        document={document}
        loading={false}
        error={null}
        deliveryStatus="completed"
        progress={{ claimCount: 2, evidenceCount: 4 }}
        files={[
          {
            name: "showcase-report.md",
            path: "showcase-report.md",
            size: 120,
            media_type: "text/markdown",
          },
          {
            name: "showcase-report.pdf",
            path: "showcase-report.pdf",
            size: 240,
            media_type: "application/pdf",
          },
        ]}
        markdown="# Showcase report"
        markdownError={null}
        {...overrides}
      />
    );
  }

  it("renders claims first with only the first disclosure open and every linked evidence", () => {
    renderResults();
    const region = screen.getByRole("region", { name: /research results/i });
    const disclosures = region.querySelectorAll("details");

    expect(disclosures).toHaveLength(2);
    expect(disclosures[0]).toHaveAttribute("open");
    expect(disclosures[1]).not.toHaveAttribute("open");
    expect(screen.getByText("web evidence")).toBeInTheDocument();
    expect(screen.getByText("uploaded-file evidence")).toBeInTheDocument();
    expect(screen.getByText("mysql evidence")).toBeInTheDocument();
    expect(screen.getByText("knowledge evidence")).toBeInTheDocument();
    expect(region.querySelector(".showcase-claims")).not.toBeNull();
    expect(region.querySelector(".showcase-inspection")).not.toBeNull();
  });

  it("shows four stable coverage rows, source metadata, and limitations", () => {
    renderResults();
    const coverage = screen.getByRole("list", { name: /source coverage/i });

    for (const label of ["Web", "MySQL", "Knowledge base", "Uploaded file"]) {
      expect(within(coverage).getByText(label)).toBeInTheDocument();
    }
    expect(screen.getAllByText(/Captured:/i)).toHaveLength(4);
    expect(screen.getAllByText(/Version: 1\.0\.0/i)).toHaveLength(4);
    expect(screen.getByText(/Partial rows\./)).toBeInTheDocument();
    expect(document.querySelector(".source-kind-web")).not.toBeNull();
    expect(document.querySelector(".source-kind-uploaded-file")).not.toBeNull();
  });

  it("links only validated Web and uploaded sources with safe attributes", () => {
    renderResults();
    const web = screen.getByRole("link", { name: /open web source/i });
    const upload = screen.getByRole("link", { name: /open uploaded source/i });

    expect(web).toHaveAttribute("href", "https://example.com/a");
    expect(web).toHaveAttribute("target", "_blank");
    expect(web).toHaveAttribute("rel", "noreferrer noopener");
    expect(upload).toHaveAttribute(
      "href",
      `http://127.0.0.1:8000/api/threads/${THREAD_ID}/uploads/brief%20notes.md`
    );
    expect(upload).not.toHaveAttribute("target");
    expect(screen.queryByRole("link", { name: /mysql/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /knowledge/i })).not.toBeInTheDocument();
  });

  it("renders showcase report preview and current-thread download controls", () => {
    renderResults();

    expect(screen.getByText("# Showcase report")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /download markdown/i })).toHaveAttribute(
      "href",
      `http://127.0.0.1:8000/api/download?thread_id=${THREAD_ID}&path=showcase-report.md`
    );
    expect(screen.getByRole("link", { name: /download pdf/i })).toHaveAttribute(
      "href",
      `http://127.0.0.1:8000/api/download?thread_id=${THREAD_ID}&path=showcase-report.pdf`
    );
  });

  it("renders loading progress and degraded delivery as stable text", () => {
    const { rerender } = render(
      <ShowcaseResults
        apiBaseUrl="http://127.0.0.1:8000"
        threadId={THREAD_ID}
        document={null}
        loading
        error={null}
        deliveryStatus="loading"
        progress={{ claimCount: 2, evidenceCount: 4 }}
        files={[]}
        markdown={null}
        markdownError={null}
      />
    );
    expect(screen.getByText(/Loading live citation results/i)).toBeInTheDocument();
    expect(screen.getByText(/2 claims · 4 evidence records/i)).toBeInTheDocument();

    rerender(
      <ShowcaseResults
        apiBaseUrl="http://127.0.0.1:8000"
        threadId={THREAD_ID}
        document={null}
        loading={false}
        error="Live citation delivery did not complete."
        deliveryStatus="degraded"
        progress={null}
        files={[]}
        markdown={null}
        markdownError={null}
      />
    );
    expect(
      screen.getByText("Live citation delivery did not complete.")
    ).toBeInTheDocument();
  });

  it("keeps untrusted answer text as text and renders zero evidence honestly", () => {
    const value = liveDocument();
    value.answer = "<script>window.pwned = true</script>";
    value.claims = [
      { claim_id: "claim-1", statement: "No evidence claim.", evidence_ids: [] },
    ];
    value.sources = [];
    value.evidence = [];
    value.limitations = [
      { code: "no-evidence", source_kind: null, message: "No evidence." },
    ];
    renderResults({ document: parseLiveCitationDocument(value, THREAD_ID) });

    expect(
      screen.getByText("<script>window.pwned = true</script>")
    ).toBeInTheDocument();
    expect(document.querySelector("script")).toBeNull();
    expect(screen.getByText("No evidence is linked to this claim.")).toBeInTheDocument();
    expect(screen.getByText(/No evidence\./)).toBeInTheDocument();
  });
});
