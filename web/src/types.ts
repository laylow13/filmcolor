export type OutputStyle = "faithful" | "neutral" | "share";

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
  exports: unknown[];
  error: string | null;
}
