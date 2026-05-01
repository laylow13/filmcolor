import type { FrameSidecar, OutputStyle, RollMetadata } from "./types";

export async function listRolls(): Promise<RollMetadata[]> {
  const response = await fetch("/api/rolls");
  return readJson(response);
}

export async function listFrames(rollId: string): Promise<FrameSidecar[]> {
  const response = await fetch(`/api/rolls/${rollId}/frames`);
  return readJson(response);
}

export async function setFrameStyle(
  rollId: string,
  frameId: string,
  style: OutputStyle
): Promise<FrameSidecar> {
  const response = await fetch(`/api/rolls/${rollId}/frames/${frameId}/pipeline`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tone: { style } })
  });
  return readJson(response);
}

export async function renderPreview(rollId: string, frameId: string): Promise<{ preview_url: string }> {
  const response = await fetch(`/api/rolls/${rollId}/frames/${frameId}/render-preview`, {
    method: "POST"
  });
  return readJson(response);
}

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}
