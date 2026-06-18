import { useState } from "react";

export default function SourceList({ sources }) {
  const [open, setOpen] = useState(false);
  const [info, setInfo] = useState(false);
  return (
    <div className="sources">
      <button className="sources-toggle" onClick={() => setOpen((o) => !o)}>
        {open ? "▾" : "▸"} {sources.length} source{sources.length > 1 ? "s" : ""}
      </button>
      {open && (
        <>
          <ul className="sources-list">
            {sources.map((s) => (
              <li key={s.id}>
                <span className="score">{(s.score * 100).toFixed(0)}%</span>
                <span className="snippet">{s.content_text}</span>
              </li>
            ))}
          </ul>

          <button className="info-toggle" onClick={() => setInfo((v) => !v)}>
            {info ? "▾" : "▸"} How is % measured?
          </button>
          {info && (
            <div className="score-info">
              <div>
                <strong>%</strong> = cosine&nbsp;similarity × 100 ={" "}
                <code>(1 − cosine&nbsp;distance) × 100</code>
              </div>
              <div className="formula">
                similarity = cos(θ) = (A · B) / (‖A‖ × ‖B‖)
              </div>
              <ul className="score-legend">
                <li><b>A</b> = embedding ของคำถาม (query)</li>
                <li><b>B</b> = embedding ของเอกสาร (document)</li>
                <li>vector มาจาก <code>text-embedding-3-large</code> (3072 มิติ)</li>
                <li>
                  DB ใช้ตัวดำเนินการ <code>embedding &lt;=&gt; query</code> ของ pgvector
                  = cosine distance; score = <code>1 − distance</code>
                </li>
                <li>1.0 = เหมือนกันมากที่สุด, 0 = ไม่เกี่ยวข้อง</li>
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  );
}
