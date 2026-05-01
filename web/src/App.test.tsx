/// <reference types="@testing-library/jest-dom" />

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";

describe("App", () => {
  it("renders the filmcolor workbench shell", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => []
      }))
    );

    render(<App />);

    expect(await screen.findByText("Filmcolor")).toBeInTheDocument();
    expect(screen.getByText("ROLL")).toBeInTheDocument();
    expect(screen.getByText("FRAME")).toBeInTheDocument();
    expect(screen.getByText("faithful")).toBeInTheDocument();
  });
});
