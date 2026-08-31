import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ConversationWorkspace, type ConversationWorkspaceState } from "./ConversationWorkspace";

function state(): ConversationWorkspaceState {
  return {
    user: { id: "u1", username: "user", role: "user" },
    conversations: [{
      id: "c1",
      owner_id: "u1",
      title: "LangGraph 入门",
      created_at: "2026-08-16T00:00:00Z",
      updated_at: "2026-08-16T00:00:00Z",
      attachments: [],
      turns: [{
        id: "t1",
        question: "LangGraph 是什么？",
        answer: "LangGraph 用状态图组织可恢复的 Agent 流程。[1]",
        use_web: true,
        status: "completed",
        attachment_ids: [],
        created_at: "2026-08-16T00:00:00Z",
        completed_at: "2026-08-16T00:00:01Z",
        result: {
          schema_version: "5.0.0",
          answer: "LangGraph 用状态图组织可恢复的 Agent 流程。[1]",
          claims: [{ claim_id: "claim-1", statement: "LangGraph 使用状态图。", evidence_ids: ["ev-1"] }],
          evidence: [{ evidence_id: "ev-1", source_kind: "knowledge", title: "LangGraph 文档", locator_kind: "chunk", locator_value: "guide#intro", quote: "LangGraph models workflows as graphs.", hostname: null, published_at: null }],
          limitations: [],
        },
      }],
    }],
    activeConversation: null,
    activeConversationId: "c1",
    question: "",
    useWeb: true,
    stage: null,
    streamingText: "",
    runningTurnId: null,
    planSubquestions: [],
    stageLog: [],
    cancelTurn: vi.fn(),
    error: null,
    adminUsers: [],
    setQuestion: vi.fn(),
    setUseWeb: vi.fn(),
    selectConversation: vi.fn(),
    createConversation: vi.fn(),
    deleteConversation: vi.fn(),
    renameConversation: vi.fn(),
    resetUserData: vi.fn(),
    submitTurn: vi.fn(),
    view: "research",
    setView: vi.fn(),
    libraryDocs: [],
    libraryBusy: false,
    uploadLibraryDocuments: vi.fn(),
    deleteLibraryDocument: vi.fn(),
    logout: vi.fn(),
    reportUrl: () => "http://test/api/conversations/c1/report",
  };
}

describe("ConversationWorkspace", () => {
  it("renders a conversation-first interface without structured data controls", () => {
    render(<ConversationWorkspace state={state()} />);
    expect(screen.getByRole("heading", { name: "LangGraph 入门" })).toBeInTheDocument();
    expect(screen.getByText("LangGraph 是什么？")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "使用实时网络" })).toBeChecked();
    expect(screen.queryByText(/MySQL|结构化数据/)).not.toBeInTheDocument();
  });

  it("organizes claims and renders each cited evidence card once", () => {
    const value = state();
    value.conversations[0].turns[0].result!.claims.push({
      claim_id: "claim-2",
      statement: "状态可以持久化。",
      evidence_ids: ["ev-1"],
    });
    render(<ConversationWorkspace state={value} />);
    expect(screen.getByRole("heading", { name: "本轮依据" })).toBeInTheDocument();
    expect(screen.getByText("LangGraph 使用状态图。")).toBeInTheDocument();
    expect(screen.getByText("状态可以持久化。")).toBeInTheDocument();
    expect(screen.getAllByText("LangGraph models workflows as graphs.")).toHaveLength(1);
    expect(screen.getByText("本地知识库")).toBeInTheDocument();
  });

  it("submits the current question with the web setting", () => {
    const value = state();
    value.question = "如何开始？";
    render(<ConversationWorkspace state={value} />);
    fireEvent.click(screen.getByRole("button", { name: "发送" }));
    expect(value.submitTurn).toHaveBeenCalledTimes(1);
  });

  it("offers only the cumulative Markdown report", () => {
    render(<ConversationWorkspace state={state()} />);
    expect(screen.getByRole("link", { name: "下载研究报告" })).toHaveAttribute(
      "href", "http://test/api/conversations/c1/report",
    );
    expect(screen.queryByText(/PDF|JSON/)).not.toBeInTheDocument();
  });

  it("omits unreferenced evidence and puts compact limitations first", () => {
    const value = state();
    const turn = value.conversations[0].turns[0];
    turn.result!.limitations = ["未覆盖部署规模问题。"];
    turn.result!.evidence.push({
      evidence_id: "ev-supplement",
      source_kind: "web",
      title: "补充页面",
      locator_kind: "url",
      locator_value: "https://example.com/supplement",
      quote: "补充证据",
      hostname: "example.com",
      published_at: null,
    });
    render(<ConversationWorkspace state={value} />);
    expect(screen.queryByText("补充检索来源（未被声明引用）")).not.toBeInTheDocument();
    expect(screen.queryByText("补充页面")).not.toBeInTheDocument();
    const answer = screen.getByText((_, element) =>
      element?.tagName === "P" &&
      element.textContent === "LangGraph 用状态图组织可恢复的 Agent 流程。[1]",
    );
    // 展示审阅：限制说明折叠面板位于回答之后（默认收起，不压在回答上方）
    const notes = screen.getByText("本轮限制与说明（1）");
    // answer 在 notes 之前（notes.compareDocumentPosition(answer) 返回 PRECEDING）
    expect(notes.compareDocumentPosition(answer) & Node.DOCUMENT_POSITION_PRECEDING).toBeTruthy();
  });

  it("expands and collapses a clamped evidence quote", () => {
    render(<ConversationWorkspace state={state()} />);

    const quote = screen.getByText("LangGraph models workflows as graphs.");
    expect(quote).toHaveClass("evidence-quote-clamped");
    fireEvent.click(screen.getByRole("button", { name: "展开证据原文" }));
    expect(quote).not.toHaveClass("evidence-quote-clamped");
    fireEvent.click(screen.getByRole("button", { name: "收起证据原文" }));
    expect(quote).toHaveClass("evidence-quote-clamped");
  });

  it("makes answer citation markers navigate to the supporting claim", () => {
    render(<ConversationWorkspace state={state()} />);
    expect(screen.getByRole("link", { name: "查看依据 1" })).toHaveAttribute(
      "href",
      "#turn-t1-evidence-ev-1",
    );
  });

  it("shows the stop control only while a turn is running", () => {
    const running = render(<ConversationWorkspace state={{
      ...state(),
      stage: "正在检索证据",
      runningTurnId: "t1",
    }} />);
    expect(screen.getByRole("button", { name: "停止本轮研究" })).toBeInTheDocument();
    running.unmount();

    render(<ConversationWorkspace state={state()} />);
    expect(screen.queryByRole("button", { name: "停止本轮研究" })).not.toBeInTheDocument();
  });

  it("supports manual conversation renaming", () => {
    const value = state();
    render(<ConversationWorkspace state={value} />);
    fireEvent.click(screen.getByRole("button", { name: "重命名会话" }));
    fireEvent.change(screen.getByRole("textbox", { name: "会话标题" }), {
      target: { value: "新的研究标题" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存标题" }));
    expect(value.renameConversation).toHaveBeenCalledWith("c1", "新的研究标题");
  });

  it("shows a compact admin data view and confirms reset", () => {
    const value = state();
    value.user = { id: "admin", username: "admin", role: "admin" };
    value.adminUsers = [
      { id: "u1", username: "user", role: "user", conversation_count: 3 },
    ];
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<ConversationWorkspace state={value} />);
    expect(screen.getByRole("heading", { name: "数据管理" })).toBeInTheDocument();
    expect(screen.getByText("3 个会话")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "清理 user 的数据" }));
    expect(value.resetUserData).toHaveBeenCalledWith("u1");
  });
});


it("renders streaming prose while a turn is running and clears after completion", () => {
  const running = state();
  running.runningTurnId = "turn-running";
  running.streamingText = "LangGraph 的图状态是";
  const view = render(<ConversationWorkspace state={running} />);

  const bubble = screen.getByLabelText("回答生成中");
  expect(bubble.textContent).toContain("LangGraph 的图状态是");

  // 完成态：runningTurnId 清空后由正式 answer 覆盖，不再显示流式气泡
  const done = state();
  view.rerender(<ConversationWorkspace state={done} />);
  expect(screen.queryByLabelText("回答生成中")).not.toBeInTheDocument();
});
