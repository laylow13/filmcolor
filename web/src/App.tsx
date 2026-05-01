import { Aperture, Grid2X2, ImageIcon, Play, SlidersHorizontal } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { listFrames, listRolls, renderPreview, setFrameStyle } from "./api";
import type { FrameSidecar, OutputStyle, RollMetadata } from "./types";

const styles: OutputStyle[] = ["faithful", "neutral", "share"];

export function App() {
  const [rolls, setRolls] = useState<RollMetadata[]>([]);
  const [selectedRollId, setSelectedRollId] = useState<string>("");
  const [frames, setFrames] = useState<FrameSidecar[]>([]);
  const [selectedFrameId, setSelectedFrameId] = useState<string>("");
  const [previewUrl, setPreviewUrl] = useState<string>("");
  const [error, setError] = useState<string>("");

  useEffect(() => {
    listRolls()
      .then((items) => {
        setRolls(items);
        setSelectedRollId(items[0]?.id ?? "");
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!selectedRollId) {
      setFrames([]);
      return;
    }
    listFrames(selectedRollId)
      .then((items) => {
        setFrames(items);
        setSelectedFrameId(items[0]?.frame_id ?? "");
      })
      .catch((err: Error) => setError(err.message));
  }, [selectedRollId]);

  const selectedFrame = useMemo(
    () => frames.find((frame) => frame.frame_id === selectedFrameId) ?? null,
    [frames, selectedFrameId]
  );

  async function chooseStyle(style: OutputStyle) {
    if (!selectedRollId || !selectedFrame) return;
    const updated = await setFrameStyle(selectedRollId, selectedFrame.frame_id, style);
    setFrames((current) =>
      current.map((frame) => (frame.frame_id === updated.frame_id ? updated : frame))
    );
  }

  async function handleRenderPreview() {
    if (!selectedRollId || !selectedFrame) return;
    const result = await renderPreview(selectedRollId, selectedFrame.frame_id);
    setPreviewUrl(`${result.preview_url}?t=${Date.now()}`);
  }

  return (
    <main className="shell">
      <aside className="rolls" aria-label="Roll list">
        <div className="brand">
          <Aperture aria-hidden="true" size={22} />
          <h1>Filmcolor</h1>
        </div>
        <div className="sectionLabel">ROLL</div>
        {rolls.length === 0 ? (
          <div className="empty">No rolls imported</div>
        ) : (
          rolls.map((roll) => (
            <button
              className={roll.id === selectedRollId ? "roll active" : "roll"}
              key={roll.id}
              onClick={() => setSelectedRollId(roll.id)}
            >
              <span>{roll.name}</span>
              <small>{roll.id}</small>
            </button>
          ))
        )}
      </aside>

      <section className="table">
        <header className="toolbar">
          <div>
            <div className="sectionLabel">FRAME</div>
            <strong>{selectedFrame?.frame_id ?? "No frame selected"}</strong>
          </div>
          <button className="iconButton" onClick={handleRenderPreview} aria-label="Render preview">
            <Play size={18} />
          </button>
        </header>

        <div className="preview">
          {previewUrl ? (
            <img src={previewUrl} alt="Rendered film preview" />
          ) : (
            <div className="previewEmpty">
              <ImageIcon size={34} />
              <span>Render a preview</span>
            </div>
          )}
        </div>

        <div className="gridHeader">
          <Grid2X2 size={16} />
          <span>Contact Sheet</span>
        </div>
        <div className="frames">
          {frames.map((frame) => (
            <button
              key={frame.frame_id}
              className={frame.frame_id === selectedFrameId ? "frame active" : "frame"}
              onClick={() => {
                setSelectedFrameId(frame.frame_id);
                setPreviewUrl("");
              }}
            >
              <span>{frame.frame_id}</span>
              <small>{frame.status}</small>
            </button>
          ))}
        </div>
      </section>

      <aside className="panel">
        <div className="panelTitle">
          <SlidersHorizontal size={18} />
          <span>Pipeline</span>
        </div>
        <div className="sectionLabel">STYLE</div>
        <div className="segmented">
          {styles.map((style) => (
            <button
              key={style}
              className={selectedFrame?.pipeline.tone.style === style ? "selected" : ""}
              onClick={() => chooseStyle(style)}
            >
              {style}
            </button>
          ))}
        </div>
        <dl className="readout">
          <div>
            <dt>Mask confidence</dt>
            <dd>{selectedFrame?.pipeline.mask.auto.confidence.toFixed(2) ?? "0.00"}</dd>
          </div>
          <div>
            <dt>Exposure</dt>
            <dd>{selectedFrame?.pipeline.tone.exposure.toFixed(2) ?? "0.00"}</dd>
          </div>
          <div>
            <dt>Contrast</dt>
            <dd>{selectedFrame?.pipeline.tone.contrast.toFixed(2) ?? "0.00"}</dd>
          </div>
        </dl>
        {error ? <p className="error">{error}</p> : null}
      </aside>
    </main>
  );
}
