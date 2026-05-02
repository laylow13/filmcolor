export type OutputStyle = "faithful" | "neutral" | "share";
export type ProcessingEngine = "filmcolor" | "negpy";

export interface EngineStatus {
  filmcolor: { available: true };
  negpy: {
    available: boolean;
    experimental: true;
    backend: "cpu";
    commit?: string;
    reason?: string;
  };
}

export interface RollMetadata {
  id: string;
  name: string;
  source_dir: string;
  created_at: string;
  defaults: {
    film_profile: string;
    output_style: OutputStyle;
    color_space: string;
  };
}

export interface FrameSidecar {
  frame_id: string;
  status: string;
  source: {
    path: string;
    sha256: string;
    camera: string | null;
    lens: string | null;
    captured_at: string | null;
  };
  pipeline: {
    engine: ProcessingEngine;
    tone: {
      style: OutputStyle;
      exposure: number;
      contrast: number;
      black_point: number;
      white_point: number;
    };
    mask: {
      auto: {
        rgb_gain: number[];
        confidence: number;
      };
      samples: {
        film_base: number[][];
        gray: number[][];
        white: number[][];
      };
    };
  };
  engines: {
    negpy: {
      enabled: boolean;
      version: string | null;
      source_commit: string | null;
      backend: string;
      params: {
        mode: string;
        preset: string;
        density?: number | null;
        grade?: number | null;
        wb_cyan?: number | null;
        wb_magenta?: number | null;
        wb_yellow?: number | null;
      };
      diagnostics: Record<string, unknown>;
    };
  };
  exports: unknown[];
  error: string | null;
}
