import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import App from "./App";

describe("App", () => {
  it("renders the project heading", () => {
    render(<App />);
    expect(
      screen.getByRole("heading", {
        name: /Agent Engineering Research Copilot/i,
      })
    ).toBeInTheDocument();
  });

  it("displays Phase 0 badge", () => {
    render(<App />);
    expect(
      screen.getByText((content, element) => {
        if (!element) return false;
        // Only match the <p> element directly, not ancestors
        if (element.tagName !== "P") return false;
        const text = element.textContent || "";
        return /Phase\s*0/i.test(text);
      })
    ).toBeInTheDocument();
  });

  it("shows backend URL from environment", () => {
    render(<App />);
    expect(
      screen.getByText(/http:\/\/127\.0\.0\.1:8000/i)
    ).toBeInTheDocument();
  });
});
