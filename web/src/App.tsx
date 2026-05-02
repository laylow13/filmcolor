import { Aperture, Grid2X2, ImageIcon, Play, SlidersHorizontal } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { getEngines, listFrames, listRolls, renderPreview, setFrameEngine, setFrameStyle } from "./api";
import type { EngineStatus, FrameSidecar, OutputStyle, ProcessingEngine, RollMetadata } from "./types";

const styles: OutputStyle[] = ["faithful", "neutral", "share"];

export function App() {
  const [rolls, setRolls] = useState<RollMetadata[]>([]);
  const [selectedRollId, setSelectedRollId] = useState<string>("");
  const [frames, setFrames] = useState<FrameSidecar[]>([]);
  const [selectedFrameId, setSelectedFrameId] = useState<string>("");
  const [previewUrl, setPreviewUrl] = useState<string>("");
  const [isRendering, setIsRendering] = useState(false);
  const [engines, setEngines] = useState<EngineStatus | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    getEngines()
      .then(setEngines)
      .catch((err: Error) => setError(err.message));
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

  async function chooseEngine(engine: ProcessingEngine) {
    if (!selectedRollId || !selectedFrame) return;
    const updated = await setFrameEngine(selectedRollId, selectedFrame.frame_id, engine);
    setFrames((current) =>
      current.map((frame) => (frame.frame_id === updated.frame_id ? updated : frame))
    );
    setPreviewUrl("");
  }

  async function chooseStyle(style: OutputStyle) {
    if (!selectedRollId || !selectedFrame) return;
    const updated = await setFrameStyle(selectedRollId, selectedFrame.frame_id, style);
    setFrames((current) =>
      current.map((frame) => (frame.frame_id === updated.frame_id ? updated : frame))
    );
  }

  async function handleRenderPreview() {
    if (!selectedRollId || !selectedFrame) return;
    setIsRendering(true);
    try {
      const result = await renderPreview(selectedRollId, selectedFrame.frame_id);
      setPreviewUrl(`${result.preview_url}?t=${Date.now()}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Render failed");
    } finally {
      setIsRendering(false);
    }
  }

  return (
    <main className="shell">
      {engines === null && rolls.length === 0 && !error ? (
        <div className="loadingBar" style={{ width: "100%" }} />
      ) : null}
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
          {isRendering ? (
            <div className="previewLoading">
              <ImageIcon size={34} />
              <span>Rendering...</span>
            </div>
          ) : previewUrl ? (
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
        <div className="sectionLabel">ENGINE</div>
        <div className="segmented engineSegment">
          <button
            className={(selectedFrame?.pipeline.engine ?? "filmcolor") === "filmcolor" ? "selected" : ""}
            onClick={() => chooseEngine("filmcolor")}
          >
            Filmcolor
          </button>
          <button
            className={selectedFrame?.pipeline.engine === "negpy" ? "selected" : ""}
            disabled={!engines?.negpy.available}
            onClick={() => chooseEngine("negpy")}
          >
            NegPy Experimental
          </button>
        </div>
        {engines?.negpy.available ? (
          <p className="engineNote">NegPy Experimental · CPU backend · {engines.negpy.commit ?? "unknown commit"}</p>
        ) : (
          <p className="engineNote">NegPy Experimental · CPU backend · {engines?.negpy.reason ?? "Checking NegPy availability..."}</p>
        )}
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
        {selectedFrame?.pipeline.engine === "negpy" ? (
          <div className="negpyInfo">
            <dl>
              <div>
                <dt>Backend</dt>
                <dd>{selectedFrame.engines.negpy.backend}</dd>
              </div>
              <div>
                <dt>Commit</dt>
                <dd>{selectedFrame.engines.negpy.source_commit?.slice(0, 7) ?? "unknown"}</dd>
              </div>
              <div>
                <dt>Adapter</dt>
                <dd>{String(selectedFrame.engines.negpy.diagnostics?.adapter ?? "in_process")}</dd>
              </div>
            </dl>
          </div>
        ) : (
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
        )}
        {error ? (
          <div className="errorBanner">
            <span>{error}</span>
            <button onClick={() => setError("")} aria-label="Dismiss error">
              Dismiss
            </button>
          </div>
        ) : null}
      </aside>
    </main>
  );
}
