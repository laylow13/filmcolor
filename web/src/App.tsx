import { Aperture, Grid2X2, ImageIcon, Play, SlidersHorizontal } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { getEngines, listFrames, listRolls, renderPreview, setFrameEngine, setFrameStyle, syncFrames } from "./api";
import type { EngineStatus, FrameSidecar, OutputStyle, ProcessingEngine, RollMetadata, SampleType, SyncRequest } from "./types";

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
  const [activeSampleType, setActiveSampleType] = useState<SampleType>("film_base");
  const [selectedFrameIds, setSelectedFrameIds] = useState<Set<string>>(new Set());
  const [previewNaturalSize, setPreviewNaturalSize] = useState<{ w: number; h: number } | null>(null);
  const previewImgRef = useRef<HTMLImageElement>(null);
  const prevSamplesRef = useRef<string>("");

  useEffect(() => {
    let ignore = false;
    getEngines()
      .then((result) => { if (!ignore) setEngines(result); })
      .catch((err: unknown) => { if (!ignore) setError(err instanceof Error ? err.message : "Failed to load engines"); });
    listRolls()
      .then((items) => {
        if (!ignore) {
          setRolls(items);
          setSelectedRollId(items[0]?.id ?? "");
        }
      })
      .catch((err: unknown) => { if (!ignore) setError(err instanceof Error ? err.message : "Failed to load rolls"); });
    return () => { ignore = true; };
  }, []);

  useEffect(() => {
    if (!selectedRollId) {
      setFrames([]);
      return;
    }
    let ignore = false;
    listFrames(selectedRollId)
      .then((items) => {
        if (!ignore) {
          setFrames(items);
          setSelectedFrameId(items[0]?.frame_id ?? "");
        }
      })
      .catch((err: unknown) => { if (!ignore) setError(err instanceof Error ? err.message : "Failed to load frames"); });
    return () => { ignore = true; };
  }, [selectedRollId]);

  const selectedFrame = useMemo(
    () => frames.find((frame) => frame.frame_id === selectedFrameId) ?? null,
    [frames, selectedFrameId]
  );

  useEffect(() => {
    if (!selectedFrame || !selectedRollId) return;
    const currentSamples = JSON.stringify(selectedFrame.pipeline.mask.samples);
    if (prevSamplesRef.current && prevSamplesRef.current !== currentSamples && previewUrl) {
      const timer = setTimeout(() => {
        handleRenderPreview();
      }, 500);
      return () => clearTimeout(timer);
    }
    prevSamplesRef.current = currentSamples;
  }, [selectedFrame?.pipeline.mask.samples]);

  async function chooseEngine(engine: ProcessingEngine) {
    if (!selectedRollId || !selectedFrame) return;
    try {
      const updated = await setFrameEngine(selectedRollId, selectedFrame.frame_id, engine);
      setFrames((current) =>
        current.map((frame) => (frame.frame_id === updated.frame_id ? updated : frame))
      );
      setPreviewUrl("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to switch engine");
    }
  }

  async function chooseStyle(style: OutputStyle) {
    if (!selectedRollId || !selectedFrame) return;
    try {
      const updated = await setFrameStyle(selectedRollId, selectedFrame.frame_id, style);
      setFrames((current) =>
        current.map((frame) => (frame.frame_id === updated.frame_id ? updated : frame))
      );
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to update style");
    }
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

  async function sendSamples(frame: FrameSidecar) {
    if (!selectedRollId) return;
    const resp = await fetch(`/api/rolls/${selectedRollId}/frames/${frame.frame_id}/pipeline`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mask: { samples: frame.pipeline.mask.samples } })
    });
    if (!resp.ok) throw new Error(await resp.text());
    const updated = await resp.json() as FrameSidecar;
    setFrames((current) =>
      current.map((f) => (f.frame_id === updated.frame_id ? updated : f))
    );
  }

  function handlePreviewClick(e: React.MouseEvent<HTMLDivElement>) {
    if (!selectedFrame || !previewNaturalSize || !previewImgRef.current) return;
    const imgEl = previewImgRef.current;
    const displayW = imgEl.clientWidth;
    const displayH = imgEl.clientHeight;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = Math.round(((e.clientX - rect.left) / displayW) * previewNaturalSize.w);
    const y = Math.round(((e.clientY - rect.top) / displayH) * previewNaturalSize.h);

    const oldSamples = selectedFrame.pipeline.mask.samples;
    const samples = {
      film_base: [...oldSamples.film_base],
      gray: [...oldSamples.gray],
      white: [...oldSamples.white],
    };
    samples[activeSampleType] = [...samples[activeSampleType], [x, y]];
    const updated = {
      ...selectedFrame,
      pipeline: { ...selectedFrame.pipeline, mask: { ...selectedFrame.pipeline.mask, samples } }
    };
    setFrames((current) => current.map((f) => (f.frame_id === updated.frame_id ? updated : f)));
    sendSamples(updated);
  }

  async function handleSync() {
    if (!selectedRollId || !selectedFrame || selectedFrameIds.size === 0) return;
    try {
      const req: SyncRequest = {
        source_frame_id: selectedFrame.frame_id,
        target_frame_ids: [...selectedFrameIds],
        fields: ["mask.samples", "tone.style", "tone.exposure", "tone.contrast"]
      };
      await syncFrames(selectedRollId, req);
      setSelectedFrameIds(new Set());
      const items = await listFrames(selectedRollId);
      setFrames(items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Sync failed");
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

        <div className="previewWrap" onClick={handlePreviewClick}>
          {isRendering ? (
            <div className="previewLoading">
              <ImageIcon size={34} />
              <span>Rendering...</span>
            </div>
          ) : previewUrl ? (
            <>
              <img
                ref={previewImgRef}
                src={previewUrl}
                alt="Rendered film preview"
                onLoad={(e) => {
                  setPreviewNaturalSize({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight });
                }}
              />
              {selectedFrame && previewNaturalSize && previewImgRef.current && (() => {
                const markers: { x: number; y: number; type: SampleType }[] = [];
                const s = selectedFrame.pipeline.mask.samples;
                for (const p of s.film_base) markers.push({ x: p[0], y: p[1], type: "film_base" as SampleType });
                for (const p of s.gray) markers.push({ x: p[0], y: p[1], type: "gray" as SampleType });
                for (const p of s.white) markers.push({ x: p[0], y: p[1], type: "white" as SampleType });
                const imgEl = previewImgRef.current;
                const scaleX = imgEl.clientWidth / previewNaturalSize.w;
                const scaleY = imgEl.clientHeight / previewNaturalSize.h;
                return markers.map((m, i) => (
                  <div
                    key={i}
                    className={`sampleMarker ${m.type}`}
                    style={{ left: m.x * scaleX, top: m.y * scaleY }}
                  />
                ));
              })()}
            </>
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
          {selectedFrameIds.size > 0 && selectedFrame && (
            <div className="syncBar">
              <span>{selectedFrameIds.size} selected</span>
              <button onClick={handleSync}>Sync from {selectedFrame.frame_id}</button>
            </div>
          )}
        </div>
        <div className="frames">
          {frames.map((frame) => (
            <button
              key={frame.frame_id}
              className={
                (frame.frame_id === selectedFrameId ? "frame active" : "frame") +
                (selectedFrameIds.has(frame.frame_id) ? " selected" : "")
              }
              onClick={(e) => {
                if (e.ctrlKey || e.metaKey) {
                  setSelectedFrameIds((prev) => {
                    const next = new Set(prev);
                    if (next.has(frame.frame_id)) next.delete(frame.frame_id);
                    else next.add(frame.frame_id);
                    return next;
                  });
                } else {
                  setSelectedFrameId(frame.frame_id);
                  setPreviewUrl("");
                }
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
        <div className="sectionLabel">SAMPLES</div>
        <div className="sampleTools">
          <button
            className={activeSampleType === "film_base" ? "activeFilmBase" : ""}
            onClick={() => setActiveSampleType("film_base")}
          >
            Film Base
          </button>
          <button
            className={activeSampleType === "gray" ? "activeGray" : ""}
            onClick={() => setActiveSampleType("gray")}
          >
            Gray
          </button>
          <button
            className={activeSampleType === "white" ? "activeWhite" : ""}
            onClick={() => setActiveSampleType("white")}
          >
            White
          </button>
        </div>
        {selectedFrame && (() => {
          const samples = selectedFrame.pipeline.mask.samples;
          const items: { type: SampleType; x: number; y: number }[] = [];
          for (const s of samples.film_base) items.push({ type: "film_base" as SampleType, x: s[0], y: s[1] });
          for (const s of samples.gray) items.push({ type: "gray" as SampleType, x: s[0], y: s[1] });
          for (const s of samples.white) items.push({ type: "white" as SampleType, x: s[0], y: s[1] });
          if (items.length === 0) return null;
          return (
            <div className="sampleList">
              {items.map((item, i) => (
                <div className="sampleItem" key={i}>
                  <span className={`sampleDot ${item.type}`} />
                  <span>{item.type}</span>
                  <span>({item.x}, {item.y})</span>
                  <button
                    onClick={() => {
                      const updated = { ...selectedFrame };
                      const newSamples = { ...updated.pipeline.mask.samples };
                      const arr = newSamples[item.type].filter((p: number[]) => !(p[0] === item.x && p[1] === item.y));
                      newSamples[item.type] = arr;
                      updated.pipeline = { ...updated.pipeline, mask: { ...updated.pipeline.mask, samples: newSamples } };
                      setFrames((current) => current.map((f) => (f.frame_id === updated.frame_id ? updated : f)));
                      sendSamples(updated);
                    }}
                  >
                    x
                  </button>
                </div>
              ))}
            </div>
          );
        })()}
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
