import { useEffect, useRef, useState } from "react";
import { ingestText, uploadFile, listDocuments, deleteDocument } from "../api.js";

export default function UploadPanel() {
  const [text, setText] = useState("");
  const [docs, setDocs] = useState([]);
  const [total, setTotal] = useState(0);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState(null); // {type:'ok'|'err', msg}
  const fileRef = useRef(null);

  async function refresh() {
    try {
      const data = await listDocuments();
      setDocs(data.documents);
      setTotal(data.total);
    } catch (err) {
      setStatus({ type: "err", msg: err.message });
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleAddText(e) {
    e.preventDefault();
    if (!text.trim() || busy) return;
    setBusy(true);
    setStatus(null);
    try {
      const r = await ingestText(text);
      setStatus({ type: "ok", msg: `Added ${r.inserted} chunk(s).` });
      setText("");
      await refresh();
    } catch (err) {
      setStatus({ type: "err", msg: err.message });
    } finally {
      setBusy(false);
    }
  }

  async function handleFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setStatus(null);
    try {
      const r = await uploadFile(file);
      setStatus({ type: "ok", msg: `“${file.name}” → ${r.inserted} chunk(s).` });
      await refresh();
    } catch (err) {
      setStatus({ type: "err", msg: err.message });
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function handleDelete(id) {
    setBusy(true);
    try {
      await deleteDocument(id);
      await refresh();
    } catch (err) {
      setStatus({ type: "err", msg: err.message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="upload">
      <header className="chat-header">
        <div className="dot" />
        <div>
          <div className="title">Upload knowledge</div>
          <div className="subtitle">{total} chunk(s) in vector store</div>
        </div>
      </header>

      <div className="upload-body">
        <form className="upload-form" onSubmit={handleAddText}>
          <label className="upload-label">Paste text</label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste any knowledge text here…"
            rows={5}
            disabled={busy}
          />
          <div className="upload-actions">
            <button type="submit" disabled={busy || !text.trim()}>
              Add text
            </button>
            <span className="or">or</span>
            <label className="file-btn">
              {busy ? "Working…" : "Upload .txt / .md"}
              <input
                ref={fileRef}
                type="file"
                accept=".txt,.md,.markdown,.csv,.json,text/*"
                onChange={handleFile}
                disabled={busy}
                hidden
              />
            </label>
          </div>
        </form>

        {status && (
          <div className={`status ${status.type}`}>{status.msg}</div>
        )}

        <div className="doc-list">
          <div className="doc-list-title">Documents</div>
          {docs.length === 0 && <div className="empty">No documents yet.</div>}
          {docs.map((d) => (
            <div key={d.id} className="doc-row">
              <span className="doc-id">#{d.id}</span>
              <span className="doc-text">{d.content_text}</span>
              <button
                className="doc-del"
                onClick={() => handleDelete(d.id)}
                disabled={busy}
                title="Delete"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
