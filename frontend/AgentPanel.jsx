import React, { useEffect, useMemo, useRef, useState } from 'react';
import './agent-panel.css';

const AUTO = 'Hãy giải thích kết quả ác tính của ca này dựa trên toàn bộ 30 đặc trưng, độ nhạy mô hình và tài liệu đã truy xuất. Phân biệt đặc trưng nhân tế bào với kích thước khối u; nêu dữ liệu còn thiếu.';
export default function AgentPanel({ api, singleResult, batchResult, history = [], tab, activeCase = null, onClose }) {
  const [open, setOpen] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const [status, setStatus] = useState(null);
  const [selected, setSelected] = useState('');
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const requestId = useRef(0);
  const sending = useRef(false);
  const controllerRef = useRef(null);
  const attempted = useRef(new Set());
  const cases = useMemo(() => {
    if (activeCase?.historyId != null) return [{id:activeCase.historyId,index:activeCase.rowIndex ?? 0,result:activeCase.result ?? {},label:activeCase.label || 'Ca đang chọn'}];
    if (tab === 'personal' && singleResult?.history_id) return [{id:singleResult.history_id, index:0, result:singleResult, label:'Ca cá nhân vừa dự đoán'}];
    if (tab === 'batch' && batchResult?.history_id) return batchResult.items.map((r,i)=>({id:batchResult.history_id,index:i,result:r,label:`Mẫu ${i+1} · ${r.prediction}`}));
    if (tab === 'history') return history.flatMap(h=>(h.results||[]).map((r,i)=>({id:h.id,index:i,result:r,label:`${new Date(h.created_at).toLocaleString('vi-VN')} · Mẫu ${i+1} · ${r.prediction}`})));
    return [];
  }, [tab, singleResult, batchResult, history, activeCase]);
  const keyOf = c => `${c.id}:${c.index}`;
  const current = cases.find(c=>keyOf(c)===selected) || cases[0];
  const caseKey = current ? keyOf(current) : '';

  function checkStatus() {
    api('/api/agent/status')
      .then(data => {
        // Two backend status formats are supported. A provider label is
        // configuration metadata, not proof that an OpenAI call will succeed.
        const configured = typeof data.configured === 'boolean'
          ? data.configured
          : data.enabled === true && data.local_available === true && !!data.model;
        setStatus({
          ...data,
          configured,
          has_key: typeof data.has_key === 'boolean' ? data.has_key : true,
          unavailable: false
        });
      })
      .catch(() => setStatus({ configured: false, has_key: false, unavailable: true }));
  }
  useEffect(()=>{ checkStatus(); return ()=>{requestId.current += 1; controllerRef.current?.abort();}; }, []);
  useEffect(()=>{
    requestId.current += 1; controllerRef.current?.abort(); controllerRef.current = null; sending.current = false; setBusy(false); setMessages([]); setError(''); setQuestion('');
  }, [caseKey, enabled]);
  useEffect(() => {
    if (activeCase?.historyId != null) setOpen(true);
  }, [activeCase]);

  async function ask(text) {
    if (!current || !enabled || !status?.configured || sending.current || !text.trim()) return;
    const id = ++requestId.current;
    const controller = new AbortController();
    controllerRef.current = controller;
    const timer = setTimeout(() => controller.abort(), 120000);
    sending.current = true; setBusy(true); setError(''); setQuestion(''); setOpen(true);
    setMessages(old=>[...old,{role:'user',text}]);
    try {
      const answer = await api('/api/agent/chat', {method:'POST', signal:controller.signal, body:JSON.stringify({history_id:current.id,sample_index:current.index,question:text,consent:true})});
      if (id === requestId.current) setMessages(old=>[...old,{role:'assistant',...answer}]);
    } catch (e) {
      if (id === requestId.current) setError(e.name === 'AbortError'
        ? 'Yêu cầu đã dừng hoặc quá 120 giây. Kiểm tra Terminal Backend để xem Ollama còn xử lý hay đã lỗi.'
        : e.message);
    } finally {
      clearTimeout(timer);
      if (controllerRef.current === controller) controllerRef.current = null;
      if (id === requestId.current) { sending.current=false; setBusy(false); }
    }
  }
  function cancelRequest() {
    controllerRef.current?.abort();
  }
  useEffect(()=>{
    if (enabled && status?.configured && current && (activeCase || tab === 'personal') &&
       (current.result.prediction_code === 'malignant' || current.result.prediction === 'Ác tính') && !attempted.current.has(caseKey)) {
      attempted.current.add(caseKey); ask(AUTO);
    }
  }, [caseKey, enabled, status?.configured, tab, activeCase]);

  return <div className="bc-agent">
    <button className="bc-agent-launch" aria-expanded={open} aria-controls="bc-agent-panel" onClick={()=>setOpen(!open)}>✦ Trợ lý AI {open ? '−' : '+'}</button>
    {open && <section id="bc-agent-panel" className="bc-agent-panel" aria-label="Trợ lý giải thích ca bệnh">
      <header><div><strong>BreastCare · Trợ lý AI</strong><p>Giải thích mô hình · Tra cứu có nguồn</p></div><button aria-label="Đóng trợ lý" onClick={()=>{setOpen(false); onClose?.();}}>×</button></header>
      <div className="bc-agent-body">
        <p className="bc-agent-notice">Dành cho học tập, không thay thế bác sĩ. Các chỉ số WDBC mô tả nhân tế bào, không xác định kích thước khối u hoặc phác đồ.</p>
        <label className="bc-agent-consent"><input type="checkbox" checked={enabled} onChange={e=>setEnabled(e.target.checked)}/><span>Bật trợ lý: xử lý 30 chỉ số, kết quả và câu hỏi bằng Ollama trên máy này (không gửi OpenAI). Tự phân tích ca cá nhân ác tính mới. Không nhập tên hoặc thông tin định danh bệnh nhân.</span></label>
        {status && !status.configured && <div role="status" className="bc-agent-error">{status.unavailable ? 'Chưa kết nối được chức năng Agent trên backend.' : !status.has_key ? 'Chưa kết nối được mô hình Ollama. Hãy chạy Ollama và kiểm tra tên mô hình.' : 'Cần bật Agent và nạp tài liệu tham khảo trước khi sử dụng.'}<button onClick={checkStatus}>Kiểm tra lại</button></div>}
        <label>Ca đang xem<select value={caseKey} onChange={e=>setSelected(e.target.value)} disabled={!cases.length}>{!cases.length && <option value="">Hãy dự đoán hoặc mở lịch sử trước</option>}{cases.map(c=><option key={keyOf(c)} value={keyOf(c)}>{c.label}</option>)}</select></label>
        <button className="bc-agent-primary" disabled={!enabled || !current || busy || !status?.configured} onClick={()=>ask(AUTO)}>Phân tích ca đang chọn</button>
        <div className="bc-agent-messages" aria-live="polite" aria-busy={busy}>
          {messages.map((m,i)=><article key={i} className={`bc-agent-message ${m.role}`}>
            <strong>{m.role==='user' ? 'Bạn' : 'Trợ lý'}</strong>
            <div className="bc-agent-answer">{m.text || m.answer}</div>
            {m.limitations?.length>0 && <details><summary>Giới hạn của phân tích</summary><ul>{m.limitations.map((s,j)=><li key={j}>{s}</li>)}</ul></details>}
            {m.missing_data?.length>0 && <details><summary>Thông tin cần bổ sung</summary><ul>{m.missing_data.map((s,j)=><li key={j}>{s}</li>)}</ul></details>}
            {m.sources?.length>0 && <details><summary>Nguồn và đoạn trích ({m.sources.length})</summary>{m.sources.map(s=><div className="bc-agent-source" key={s.id}><strong>[{s.id}] {s.title}</strong><div>{s.page ? `Trang ${s.page} · ` : ''}{s.version}</div>{/^https?:\/\//i.test(s.source) ? <a href={s.source} target="_blank" rel="noreferrer">Mở tài liệu gốc</a> : <span>{s.source}</span>}<blockquote>{s.text}</blockquote></div>)}</details>}
            {m.sensitivity && <details><summary>Độ nhạy của mô hình · 30 đặc trưng</summary><p>Thay từng giá trị bằng trung vị nhóm lành của tập tham chiếu. Δ dương: xác suất ban đầu cao hơn sau thay thế. Đây không phải SHAP hoặc nguyên nhân bệnh.</p><div className="bc-agent-table"><table><thead><tr><th>Đặc trưng</th><th>Giá trị</th><th>Δ điểm %</th></tr></thead><tbody>{m.sensitivity.features.map(f=><tr key={f.feature}><td>{f.feature}{f.outside_reference_range ? ' ⚠' : ''}</td><td>{Number(f.value).toPrecision(4)}</td><td>{(f.delta_probability*100).toFixed(2)}</td></tr>)}</tbody></table></div></details>}
            {m.steps && <details><summary>Công cụ đã sử dụng</summary><ol>{m.steps.map((s,j)=><li key={j}>{s}</li>)}</ol></details>}
          </article>)}
          {busy && <div role="status"><p>Đang phân tích 30 chỉ số và tài liệu RAG. Yêu cầu sẽ tự dừng sau tối đa 120 giây.</p><button type="button" onClick={cancelRequest}>Hủy chờ</button></div>}
          {error && <p className="bc-agent-error" role="alert">{error}</p>}
        </div>
        <form onSubmit={e=>{e.preventDefault();ask(question);}}><label htmlFor="bc-agent-question">Hỏi về ca đang chọn</label><textarea id="bc-agent-question" maxLength={1500} rows={3} value={question} onChange={e=>setQuestion(e.target.value)} placeholder="Vì sao ca này được dự đoán ác tính dù mean radius không cao?"/><button className="bc-agent-primary" disabled={!enabled || !current || !question.trim() || busy || !status?.configured}>Gửi câu hỏi</button></form>
      </div>
    </section>}
  </div>;
}
