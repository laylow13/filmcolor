/// <reference types="@testing-library/jest-dom" />

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi, afterEach } from "vitest";
import { App } from "./App";

const mockFetch = vi.fn(async (input: RequestInfo | URL) => {
  const url = String(input);
  if (url === "/api/engines") return jsonResponse({ filmcolor: { available: true }, negpy: { available: true, experimental: true, backend: "cpu", commit: "abc1234" } });
  if (url === "/api/rolls") return jsonResponse([]);
  return jsonResponse([]);
});

describe("App", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("shows import button", async () => {
    vi.stubGlobal("fetch", mockFetch);
    render(<App />);
    expect(await screen.findByText("+ Import Roll")).toBeInTheDocument();
  });

  it("shows collapsible engine section", async () => {
    vi.stubGlobal("fetch", mockFetch);
    render(<App />);
    expect(await screen.findByText("ENGINE")).toBeInTheDocument();
  });

  it("shows import form on click", async () => {
    vi.stubGlobal("fetch", mockFetch);
    render(<App />);
    fireEvent.click(await screen.findByText("+ Import Roll"));
    expect(screen.getByPlaceholderText(/Folder path/)).toBeInTheDocument();
  });
});

function jsonResponse(body: unknown) {
  return Promise.resolve({ ok: true, json: async () => body } as Response);
}
