import React, { useEffect, useRef, useState } from 'react';
import { Bot, Send, X, ChevronDown } from 'lucide-react';
import './agent.css';

const INITIAL = 'Giải thích kết quả ca này dựa trên đủ 30 chỉ số, độ nhạy mô hình và nguồn tài liệu.';
const LABELS = { inspect_case: 'Đọc 30 chỉ số', explain_model: 'Đo độ nhạy mô hình', search_guidelines: 'Truy xuất tài liệu', feature_correlations: 'Kiểm tra tương quan', compare_feature_group: 'So sánh nhóm đặc trưng' };

function Answer({ result }) {
  const sourceMap = Object.fromEntries(result.sources.map(source => [source.id, source]));
  return <div className="agent-answer">
    <span className="agent-mode">{result.mode === 'llm' ? 'AI Agent · gọi công cụ + RAG' : 'Phân tích cục bộ · chưa phải hội thoại LLM'}</span>
    {result.warning && <p className="agent-warning">{result.warning}</p>}
    {result.paragraphs.map((paragraph, index) => <p key={index}>{paragraph.text}{paragraph.source_ids.map(id => sourceMap[id] && <a key={id} href={sourceMap[id].url} target="_blank" rel="noopener noreferrer"> [{id}]</a>)}</p>)}
    <details><summary>Bằng chứng từ mô hình và 30 chỉ số</summary>
      <p>Trung vị, phân vị và tương quan chỉ tính trên tập Train. Chênh lệch dương: xác suất giảm khi thay biến bằng trung vị.</p>
      <div className="agent-table"><table><thead><tr><th>Chỉ số</th><th>Giá trị</th><th>Phân vị Train</th><th>Δ điểm %</th></tr></thead><tbody>
        {result.case.features.map(feature => <tr key={feature.name}><td>{feature.name}{feature.outside_train_range ? ' ⚠ Ngoài miền Train' : ''}</td><td>{feature.value.toPrecision(5)}</td><td>{feature.train_percentile}%</td><td>{result.sensitivity.find(row => row.feature === feature.name)?.delta_percentage_points.toFixed(2)}</td></tr>)}
      </tbody></table></div>
      <p>Tương quan Pearson với {result.correlations.feature}: {result.correlations.pairs.map(pair => `${pair.feature} (r=${pair.r.toFixed(2)})`).join('; ')}.</p>
    </details>
    <details><summary>Nguồn đã truy xuất ({result.sources.length})</summary>{result.sources.map(source => <div className="agent-source" key={source.id}><a href={source.url} target="_blank" rel="noopener noreferrer">{source.title}</a><small>{source.section} · Kiểm tra nguồn: {source.reviewed_on}</small><small>{source.kind || 'Tài liệu do quản trị viên bổ sung'}</small><p>{source.text}</p></div>)}</details>
    <details><summary>Các bước công cụ đã thực hiện</summary><ol>{result.trace.map((step, index) => <li key={index}>{LABELS[step.tool] || step.tool}{step.arguments.group ? `: ${step.arguments.group}` : ''}</li>)}</ol></details>
    <p className="agent-warning">{result.limitation}</p>
  </div>;
}

export default function AgentPanel({ api, activeCase, onClose }) {
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [collapsed, setCollapsed] = useState(false);
  const [status, setStatus] = useState(null);
  const controller = useRef(null);
  const inFlight = useRef(false);
  const alive = useRef(true);
  const scroll = useRef(null);

  async function ask(text) {
    if (!text.trim() || inFlight.current) return;
    inFlight.current = true;
    setBusy(true); setError('');
    const abort = new AbortController();
    controller.current = abort;
    const timeout = setTimeout(() => abort.abort(), 140000);
    try {
      const result = await api('/api/agent/analyze', { method: 'POST', signal: abort.signal, body: JSON.stringify({
        history_id: activeCase.historyId, row_index: activeCase.rowIndex,
        question: text, conversation: messages.slice(-6).flatMap(message => [
          { role: 'user', content: message.question.slice(0, 2000) },
          { role: 'assistant', content: message.result.paragraphs.map(p => p.text).join('\n').slice(0, 2000) },
        ]),
      }) });
      if (alive.current && !abort.signal.aborted) {
        setMessages(current => [...current, { question: text, result }]);
        setQuestion('');
      }
    } catch (err) {
      if (alive.current) setError(err.name === 'AbortError' ? 'Lượt phân tích đã dừng hoặc hết thời gian. Bạn có thể thử lại.' : err.message);
    } finally {
      clearTimeout(timeout);
      inFlight.current = false;
      if (alive.current) setBusy(false);
    }
  }

  useEffect(() => {
    alive.current = true;
    api('/api/agent/status').then(value => { if (alive.current) setStatus(value); }).catch(() => {});
    if (activeCase.malignant) ask(INITIAL);
    return () => { alive.current = false; controller.current?.abort(); };
  }, []);
  useEffect(() => { scroll.current?.scrollTo({ top: scroll.current.scrollHeight, behavior: 'smooth' }); }, [messages, busy, error]);

  return <section className={`agent-panel ${collapsed ? 'agent-collapsed' : ''}`} aria-label="Trợ lý phân tích ca bệnh">
    <header className="agent-header"><Bot size={23} /><div><strong>Trợ lý BreastCare</strong><small>{activeCase.label} · {activeCase.historyId.slice(0, 8)}</small></div><button onClick={() => setCollapsed(!collapsed)} aria-label={collapsed ? 'Mở trợ lý' : 'Thu gọn trợ lý'} aria-expanded={!collapsed}><ChevronDown size={20} /></button><button onClick={onClose} aria-label="Đóng trợ lý"><X size={20} /></button></header>
    {!collapsed && <>
      <div className="agent-body" ref={scroll} aria-live="polite">
        <p className="agent-intro">Giải thích mô hình phục vụ học tập. {status === null ? 'Đang kiểm tra chế độ kết nối AI…' : status.enabled ? 'Chế độ AI gửi 30 chỉ số và câu hỏi tới OpenAI; không nhập thông tin định danh.' : 'Chế độ cục bộ không gửi dữ liệu tới dịch vụ AI.'}</p>
        {!messages.length && !busy && <p>Hỏi về các đặc trưng của ca đang chọn hoặc nhấn “Phân tích ca”.</p>}
        {messages.map((message, index) => <div className="agent-turn" key={index}><div className="agent-question">{message.question}</div><Answer result={message.result} /></div>)}
        {busy && <p role="status">Đang đọc ca, kiểm tra mô hình và truy xuất tài liệu…</p>}
        {error && <p role="alert" className="agent-warning">{error}</p>}
      </div>
      <div className="agent-prompts"><button disabled={busy} onClick={() => ask(INITIAL)}>Phân tích ca</button><button disabled={busy} onClick={() => ask('Tại sao ca này có nguy cơ ác tính cao dù kích thước không quá lớn? Kiểm tra độ lõm, texture và tương quan.')}>Vì sao ác tính dù kích thước nhỏ?</button></div>
      <form className="agent-form" onSubmit={event => { event.preventDefault(); ask(question); }}><label htmlFor="agent-question" className="agent-sr-only">Câu hỏi cho trợ lý</label><textarea id="agent-question" maxLength={2000} value={question} onChange={event => setQuestion(event.target.value)} placeholder="Hỏi về ca đang chọn…" disabled={busy} /><button type="submit" disabled={busy || !question.trim()} aria-label="Gửi câu hỏi"><Send size={20} /></button></form>
    </>}
  </section>;
}
