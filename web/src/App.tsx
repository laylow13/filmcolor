import { Aperture, Grid2X2, ImageIcon, Play, SlidersHorizontal } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { getEngines, importRoll, listFrames, listRolls, renderPreview, setFrameEngine, setFrameStyle, syncFrames } from "./api";
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
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [frameDiagnostics, setFrameDiagnostics] = useState<Record<string, Record<string, unknown>>>({});
  const [showImport, setShowImport] = useState(false);
  const [importPath, setImportPath] = useState("");
  const [importName, setImportName] = useState("");
  const [importing, setImporting] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string>("");
  const [previewedFrames, setPreviewedFrames] = useState<Set<string>>(new Set());
  function toggleSection(name: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

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

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;

      if (e.key === " " && selectedFrame && selectedRollId) {
        e.preventDefault();
        handleRenderPreview();
      } else if (e.key === "1") {
        setActiveSampleType("film_base");
      } else if (e.key === "2") {
        setActiveSampleType("gray");
      } else if (e.key === "3") {
        setActiveSampleType("white");
      } else if (e.key === "Backspace" && selectedFrame) {
        const samples = selectedFrame.pipeline.mask.samples;
        const all: { type: SampleType; x: number; y: number }[] = [];
        for (const s of samples.film_base) all.push({ type: "film_base" as SampleType, x: s[0], y: s[1] });
        for (const s of samples.gray) all.push({ type: "gray" as SampleType, x: s[0], y: s[1] });
        for (const s of samples.white) all.push({ type: "white" as SampleType, x: s[0], y: s[1] });
        if (all.length === 0) return;
        const last = all[all.length - 1];
        const newSamples = { ...samples };
        newSamples[last.type] = newSamples[last.type].filter((p: number[]) => !(p[0] === last.x && p[1] === last.y));
        const updated = { ...selectedFrame, pipeline: { ...selectedFrame.pipeline, mask: { ...selectedFrame.pipeline.mask, samples: newSamples } } };
        setFrames((current) => current.map((f) => (f.frame_id === updated.frame_id ? updated : f)));
        sendSamples(updated);
      } else if ((e.ctrlKey || e.metaKey) && e.key === "a" && frames.length > 0) {
        e.preventDefault();
        setSelectedFrameIds(new Set(frames.map((f) => f.frame_id)));
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [selectedFrame, selectedRollId, frames]);

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
      handleRenderPreview();
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
      setPreviewedFrames((prev) => new Set(prev).add(selectedFrame.frame_id));
      setFrameDiagnostics((prev) => ({ ...prev, [selectedFrame.frame_id]: result.diagnostics || {} }));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Render failed");
    } finally {
      setIsRendering(false);
    }
  }

  async function handleImport() {
    if (!importPath.trim() || !importName.trim()) return;
    setImporting(true);
    try {
      await importRoll(importPath.trim(), importName.trim());
      const items = await listRolls();
      setRolls(items);
      setSelectedRollId(items[items.length - 1]?.id ?? "");
      setShowImport(false);
      setImportPath("");
      setImportName("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setImporting(false);
    }
  }

  const toneTimerRef = useRef<ReturnType<typeof setTimeout>>();

  async function updateTone(patch: Record<string, unknown>) {
    if (!selectedRollId || !selectedFrame) return;
    const resp = await fetch(`/api/rolls/${selectedRollId}/frames/${selectedFrame.frame_id}/pipeline`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tone: patch })
    });
    if (!resp.ok) throw new Error(await resp.text());
    const updated = await resp.json() as FrameSidecar;
    setFrames((current) =>
      current.map((f) => (f.frame_id === updated.frame_id ? updated : f))
    );
    if (toneTimerRef.current) clearTimeout(toneTimerRef.current);
    toneTimerRef.current = setTimeout(() => handleRenderPreview(), 400);
  }

  const samplesTimerRef = useRef<ReturnType<typeof setTimeout>>();

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
    if (samplesTimerRef.current) clearTimeout(samplesTimerRef.current);
    samplesTimerRef.current = setTimeout(() => handleRenderPreview(), 500);
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
      const result = await syncFrames(selectedRollId, req);
      setSyncMessage(`Synced ${result.synced_count} frame${result.synced_count !== 1 ? "s" : ""}`);
      setTimeout(() => setSyncMessage(""), 3000);
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
        {showImport ? (
          <div className="importForm">
            <input
              type="text"
              placeholder="Folder path (e.g. D:/scans/roll-001)"
              value={importPath}
              onChange={(e) => setImportPath(e.target.value)}
            />
            <input
              type="text"
              placeholder="Roll name"
              value={importName}
              onChange={(e) => setImportName(e.target.value)}
            />
            <div className="importActions">
              <button onClick={handleImport} disabled={importing} className="importBtn" style={{ fontSize: "12px" }}>
                {importing ? "Importing..." : "Import"}
              </button>
              <button onClick={() => setShowImport(false)} className="cancelBtn">
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <button onClick={() => setShowImport(true)} className="importBtn" style={{ marginBottom: "12px" }}>
            + Import Roll
          </button>
        )}
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
              {previewUrl && (
                <div className="sampleCursorLabel">
                  <span className="sampleCursorDot" style={{
                    background: activeSampleType === "film_base" ? "#c26b2b" : activeSampleType === "gray" ? "#808080" : "#ddd",
                    border: activeSampleType === "white" ? "1px solid #999" : "none"
                  }} />
                  Placing: {activeSampleType === "film_base" ? "Film Base" : activeSampleType === "gray" ? "Gray" : "White"}
                </div>
              )}
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
                    onContextMenu={(e) => {
                      e.preventDefault();
                      const newSamples = { ...selectedFrame!.pipeline.mask.samples };
                      newSamples[m.type] = newSamples[m.type].filter((p: number[]) => !(p[0] === m.x && p[1] === m.y));
                      const updatedFrame = { ...selectedFrame!, pipeline: { ...selectedFrame!.pipeline, mask: { ...selectedFrame!.pipeline.mask, samples: newSamples } } };
                      setFrames((current) => current.map((f) => (f.frame_id === updatedFrame.frame_id ? updatedFrame : f)));
                      sendSamples(updatedFrame);
                    }}
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
              <button
                className="selectAllBtn"
                onClick={() => {
                  if (selectedFrameIds.size === frames.length && selectedFrameIds.size > 0) {
                    setSelectedFrameIds(new Set());
                  } else {
                    setSelectedFrameIds(new Set(frames.map((f) => f.frame_id)));
                  }
                }}
              >
                {selectedFrameIds.size === frames.length && selectedFrameIds.size > 0 ? "Deselect All" : "Select All"}
              </button>
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
              {previewedFrames.has(frame.frame_id) && selectedRollId && (
                <div
                  className="frameThumb"
                  style={{ backgroundImage: `url(/api/rolls/${selectedRollId}/frames/${frame.frame_id}/preview)` }}
                />
              )}
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
        <div className="sectionHeader" onClick={() => toggleSection("engine")}>
          <span className="sectionLabel" style={{ marginBottom: 0 }}>ENGINE</span>
          <span className={`chevron ${collapsed.has("engine") ? "" : "open"}`}>&#9654;</span>
        </div>
        <div className={`sectionBody ${collapsed.has("engine") ? "collapsed" : ""}`} style={{ maxHeight: "200px" }}>
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
        </div>
        <div className="sectionHeader" onClick={() => toggleSection("samples")}>
          <span className="sectionLabel" style={{ marginBottom: 0 }}>SAMPLES</span>
          <span className={`chevron ${collapsed.has("samples") ? "" : "open"}`}>&#9654;</span>
        </div>
        <div className={`sectionBody ${collapsed.has("samples") ? "collapsed" : ""}`} style={{ maxHeight: "600px" }}>
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
                    {(() => {
                      const sv = (frameDiagnostics[selectedFrame.frame_id] as any)?.sampled_values;
                      if (!sv) return null;
                      const vals = sv[item.type];
                      if (!vals) return null;
                      const samplesArr = selectedFrame.pipeline.mask.samples[item.type];
                      const idx = samplesArr.findIndex((p: number[]) => p[0] === item.x && p[1] === item.y);
                      if (idx < 0 || idx >= vals.length) return null;
                      const rgb = vals[idx];
                      return <span className="sampleValue">RGB {rgb.map((v: number) => Math.round(v * 255)).join(", ")}</span>;
                    })()}
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
        </div>
        <div className="sectionHeader" onClick={() => toggleSection("style")}>
          <span className="sectionLabel" style={{ marginBottom: 0 }}>STYLE</span>
          <span className={`chevron ${collapsed.has("style") ? "" : "open"}`}>&#9654;</span>
        </div>
        <div className={`sectionBody ${collapsed.has("style") ? "collapsed" : ""}`} style={{ maxHeight: "400px" }}>
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
            <>
            <dl className="readout">
              <div>
                <dt>Mask confidence</dt>
                <dd>{selectedFrame?.pipeline.mask.auto.confidence.toFixed(2) ?? "0.00"}</dd>
              </div>
            </dl>
            <div className="toneSlider">
              <label>
                Exposure
                <span>{(selectedFrame?.pipeline.tone.exposure ?? 0).toFixed(1)}</span>
              </label>
              <input
                type="range"
                min="-3"
                max="3"
                step="0.1"
                value={selectedFrame?.pipeline.tone.exposure ?? 0}
                onChange={(e) => {
                  const val = parseFloat(e.target.value);
                  if (!selectedFrame) return;
                  const updated = { ...selectedFrame, pipeline: { ...selectedFrame.pipeline, tone: { ...selectedFrame.pipeline.tone, exposure: val } } };
                  setFrames((current) => current.map((f) => (f.frame_id === updated.frame_id ? updated : f)));
                  updateTone({ exposure: val });
                }}
              />
            </div>
            <div className="toneSlider">
              <label>
                Contrast
              <span>{(selectedFrame?.pipeline.tone.contrast ?? 0.12).toFixed(2)}</span>
              </label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.01"
                value={selectedFrame?.pipeline.tone.contrast ?? 0.12}
                onChange={(e) => {
                  const val = parseFloat(e.target.value);
                  if (!selectedFrame) return;
                  const updated = { ...selectedFrame, pipeline: { ...selectedFrame.pipeline, tone: { ...selectedFrame.pipeline.tone, contrast: val } } };
                  setFrames((current) => current.map((f) => (f.frame_id === updated.frame_id ? updated : f)));
                  updateTone({ contrast: val });
                }}
              />
            </div>
            </>
          )}
        </div>
        {syncMessage ? (
          <div className="syncToast">{syncMessage}</div>
        ) : null}
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
