/// <reference types="@testing-library/jest-dom" />

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

describe("App", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });
  it("renders sample tools and disabled NegPy engine when unavailable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url === "/api/engines") {
          return jsonResponse({
            filmcolor: { available: true },
            negpy: { available: false, experimental: true, backend: "cpu", reason: "missing" }
          });
        }
        if (url === "/api/rolls") return jsonResponse([]);
        return jsonResponse([]);
      })
    );

    render(<App />);

    expect(await screen.findByText("Film Base")).toBeInTheDocument();
    expect(screen.getByText("Gray")).toBeInTheDocument();
    expect(screen.getByText("White")).toBeInTheDocument();
  });

  it("shows sample tools when a frame is selected", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url === "/api/engines") {
          return jsonResponse({
            filmcolor: { available: true },
            negpy: { available: true, experimental: true, backend: "cpu", commit: "abc1234" }
          });
        }
        if (url === "/api/rolls") {
          return jsonResponse([{
            id: "roll-001", name: "Roll", source_dir: "D:/film",
            created_at: "2026-05-02T00:00:00Z",
            defaults: { film_profile: "generic_color_negative", output_style: "faithful", color_space: "sRGB" }
          }]);
        }
        if (url === "/api/rolls/roll-001/frames") {
          return jsonResponse([{
            frame_id: "IMG_0001", status: "unprocessed",
            source: { path: "D:/film/IMG_0001.png", sha256: "abc", camera: null, lens: null, captured_at: null },
            pipeline: {
              engine: "filmcolor",
              tone: { style: "faithful", exposure: 0, contrast: 0.12, black_point: 0.004, white_point: 0.985 },
              mask: { auto: { rgb_gain: [1, 1, 1], confidence: 0 }, samples: { film_base: [], gray: [], white: [] } }
            },
            engines: { negpy: { enabled: false, version: null, source_commit: null, backend: "cpu", params: { mode: "C41", preset: "default" }, diagnostics: {} } },
            exports: [], error: null
          }]);
        }
        return jsonResponse([]);
      })
    );

    render(<App />);
    expect(await screen.findByText("SAMPLES")).toBeInTheDocument();
    expect(screen.getByText("Film Base")).toBeInTheDocument();
  });
});

function jsonResponse(body: unknown) {
  return Promise.resolve({ ok: true, json: async () => body } as Response);
}
