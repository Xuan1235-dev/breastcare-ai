import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Activity, AlertTriangle, Bot, CheckCircle2, Clock3, Download, FileSpreadsheet,
  HeartPulse, History, Mail, RefreshCw, Send, ShieldCheck, Trash2, UploadCloud,
  UserRound, XCircle
} from 'lucide-react';
import './style.css';
import './readability.css';
import AgentPanel from './AgentPanel';

const API = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const DISCLAIMER = 'Kết quả chỉ phục vụ học tập và nghiên cứu, không thay thế kết luận chẩn đoán của bác sĩ.';

function makeUuid() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.random() * 16 | 0;
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
  });
}
function getSessionId() {
  try {
    let id = localStorage.getItem('breastcare_session_id');
    if (!id) {
      id = makeUuid();
      localStorage.setItem('breastcare_session_id', id);
    }
    return id;
  } catch {
    return makeUuid();
  }
}
const SESSION_ID = getSessionId();

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}), 'X-Session-ID': SESSION_ID };
  if (options.body && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
  const response = await fetch(`${API}${path}`, { ...options, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === 'string' ? body.detail : `Máy chủ trả về lỗi ${response.status}`);
  }
  return response.json();
}
const number = value => Number(value).toLocaleString('vi-VN', { maximumFractionDigits: 4 });
const percent = value => `${(Number(value || 0) * 100).toFixed(1)}%`;
const dateTime = value => value ? new Date(value).toLocaleString('vi-VN') : '—';

function downloadCsv(rows, filename) {
  const text = '\uFEFF' + rows.map(row => row.map(value => {
    const v = String(value ?? '');
    return `"${v.replace(/"/g, '""')}"`;
  }).join(',')).join('\r\n');
  const url = URL.createObjectURL(new Blob([text], { type: 'text/csv;charset=utf-8' }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function normalizeHeader(value) {
  return String(value ?? '').replace(/^\uFEFF/, '').trim().toLowerCase()
    .replace(/[_-]+/g, ' ').replace(/\s+/g, ' ');
}

function parseCsvLine(line, delimiter = ',') {
  const cells = [];
  let cell = '';
  let quoted = false;
  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];
    if (char === '"' && quoted && line[i + 1] === '"') {
      cell += '"';
      i += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === delimiter && !quoted) {
      cells.push(cell.trim());
      cell = '';
    } else {
      cell += char;
    }
  }
  cells.push(cell.trim());
  return cells;
}

const HEADER_ALIASES = {
  'mean radius': ['radius mean'],
  'mean texture': ['texture mean'],
  'mean perimeter': ['perimeter mean'],
  'mean area': ['area mean'],
  'mean smoothness': ['smoothness mean'],
  'mean compactness': ['compactness mean'],
  'mean concavity': ['concavity mean'],
  'mean concave points': ['concave points mean'],
  'mean symmetry': ['symmetry mean'],
  'mean fractal dimension': ['fractal dimension mean'],
  'radius error': ['radius se', 'radius standard error'],
  'texture error': ['texture se', 'texture standard error'],
  'perimeter error': ['perimeter se', 'perimeter standard error'],
  'area error': ['area se', 'area standard error'],
  'smoothness error': ['smoothness se', 'smoothness standard error'],
  'compactness error': ['compactness se', 'compactness standard error'],
  'concavity error': ['concavity se', 'concavity standard error'],
  'concave points error': ['concave points se', 'concave points standard error'],
  'symmetry error': ['symmetry se', 'symmetry standard error'],
  'fractal dimension error': ['fractal dimension se', 'fractal dimension standard error'],
  'worst radius': ['radius worst'],
  'worst texture': ['texture worst'],
  'worst perimeter': ['perimeter worst'],
  'worst area': ['area worst'],
  'worst smoothness': ['smoothness worst'],
  'worst compactness': ['compactness worst'],
  'worst concavity': ['concavity worst'],
  'worst concave points': ['concave points worst'],
  'worst symmetry': ['symmetry worst'],
  'worst fractal dimension': ['fractal dimension worst'],
};

function parseCsv(text, featureNames) {
  const lines = text.replace(/^\uFEFF/, '').split(/\r?\n/).filter(line => line.trim());
  if (!lines.length) throw new Error('Tệp CSV không có dữ liệu.');
  const delimiter = (lines[0].match(/;/g) || []).length > (lines[0].match(/,/g) || []).length ? ';' : ',';
  const parsed = lines.map(line => parseCsvLine(line, delimiter));
  const headers = parsed[0].map(normalizeHeader);
  const headerLookup = new Map();
  featureNames.forEach(name => {
    const canonical = normalizeHeader(name);
    const candidates = [canonical, ...(HEADER_ALIASES[canonical] || []).map(normalizeHeader)];
    const found = candidates.find(candidate => headers.includes(candidate));
    if (found) headerLookup.set(name, headers.indexOf(found));
  });
  const hasRecognizedHeader = headerLookup.size > 0;
  const hasHeader = headerLookup.size === featureNames.length;
  const firstRowIsRawWdbc = parsed[0].length === featureNames.length + 2
    && /^\d+$/.test(parsed[0][0])
    && /^(m|b|malignant|benign|0|1)$/i.test(parsed[0][1]);
  const firstRowHasTrailingLabel = parsed[0].length === featureNames.length + 1
    && parsed[0].slice(0, featureNames.length).every(value => value.trim() !== '' && Number.isFinite(Number(value)))
    && /^(m|b|malignant|benign|0|1)$/i.test(parsed[0][featureNames.length]);
  let indexes = null;
  let dataRows = parsed;

  if (hasHeader) {
    indexes = featureNames.map(name => headerLookup.get(name));
    dataRows = parsed.slice(1);
  } else if (hasRecognizedHeader || (!(firstRowIsRawWdbc || firstRowHasTrailingLabel) && parsed[0].some(value => !Number.isFinite(Number(value))))) {
    const missing = featureNames.filter(name => !headerLookup.has(name));
    throw new Error(`Tệp CSV đang có tiêu đề nhưng thiếu ${missing.length} cột đặc trưng: ${missing.slice(0, 5).join(', ')}${missing.length > 5 ? '...' : ''}. Hãy tải CSV mẫu để đối chiếu.`);
  }

  const rows = dataRows.map((row, index) => {
    let values;
    if (indexes) {
      values = indexes.map(i => row[i]);
    } else if (row.length === featureNames.length) {
      values = row;
    } else if (row.length === featureNames.length + 2 && /^\d+$/.test(row[0]) && /^(m|b|malignant|benign|0|1)$/i.test(row[1])) {
      // UCI WDBC without a header: ID, diagnosis, then 30 numeric features.
      values = row.slice(2);
    } else if (row.length === featureNames.length + 1 && /^(m|b|malignant|benign|0|1)$/i.test(row[row.length - 1])) {
      // Headerless file with 30 numeric features followed by a diagnosis label.
      values = row.slice(0, featureNames.length);
    } else if (row.length === featureNames.length + 1 && /^\d+$/.test(row[0])) {
      // Headerless file with an ID column followed by 30 numeric features.
      values = row.slice(1);
    } else {
      throw new Error(`Dòng ${index + 1} có ${row.length} cột; cần đúng 30 đặc trưng số (có thể kèm ID/nhãn theo định dạng WDBC).`);
    }
    if (values.some(value => String(value).trim() === '')) {
      throw new Error(`Dòng ${index + (hasHeader ? 2 : 1)} có ô dữ liệu bị trống.`);
    }
    const nums = values.map(value => Number(String(value).trim()));
    if (nums.length !== featureNames.length || nums.some(value => !Number.isFinite(value))) {
      throw new Error(`Dòng ${index + (hasHeader ? 2 : 1)} có giá trị không phải số hoặc không đủ 30 đặc trưng.`);
    }
    return nums;
  });
  if (!rows.length) throw new Error('Tệp CSV không có dòng dữ liệu.');
  if (rows.length > 100) throw new Error(`Tệp có ${rows.length} mẫu; phiên bản này nhận tối đa 100 mẫu mỗi lần.`);
  return rows;
}

function App() {
  const [tab, setTab] = useState('personal');
  const [online, setOnline] = useState(false);
  const [health, setHealth] = useState(null);
  const [info, setInfo] = useState(null);
  const [dataset, setDataset] = useState(null);
  const [values, setValues] = useState({});
  const [singleResult, setSingleResult] = useState(null);
  const [batchRows, setBatchRows] = useState([]);
  const [batchFileName, setBatchFileName] = useState('');
  const [batchResult, setBatchResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [busy, setBusy] = useState(false);
  const [notifyBusy, setNotifyBusy] = useState('');
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [agentCase, setAgentCase] = useState(null);

  function openAgent(historyId, rowIndex, result, label) {
    setAgentCase({ historyId, rowIndex, malignant: result.prediction_code === 'malignant', label });
  }

  const featureStats = dataset?.features || [];
  const featureNames = info?.features || [];

  async function refreshHistory() {
    const result = await api('/api/history?limit=50');
    setHistory(result.items || []);
  }

  async function refreshHealth() {
    const result = await api('/api/health');
    setHealth(result);
    setOnline(result.status === 'ok' && result.model_loaded);
  }

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [healthData, infoData, datasetData] = await Promise.all([
          api('/api/health'), api('/api/info'), api('/api/dataset')
        ]);
        if (!active) return;
        setHealth(healthData);
        setOnline(healthData.status === 'ok' && healthData.model_loaded);
        setInfo(infoData);
        setDataset(datasetData);
        const initial = {};
        datasetData.features.forEach(feature => { initial[feature.name] = ''; });
        setValues(initial);
        const historyData = await api('/api/history?limit=50');
        if (active) setHistory(historyData.items || []);
      } catch (err) {
        if (active) {
          setOnline(false);
          setError(`Không tải được dữ liệu từ Backend: ${err.message}. Hãy kiểm tra Render hoặc chạy Backend ở cổng 8000.`);
        }
      }
    })();
    return () => { active = false; };
  }, []);

  function updateValue(name, value) {
    setAgentCase(null);
    setValues(current => ({ ...current, [name]: value }));
    setSingleResult(null);
  }

  async function loadExample(kind) {
    setAgentCase(null);
    setBusy(true); setError(''); setSuccess('');
    try {
      const data = await api('/api/examples');
      const selected = data[kind];
      const next = {};
      featureNames.forEach((name, index) => { next[name] = String(selected[index]); });
      setValues(next);
      setSingleResult(null);
      setSuccess(kind === 'benign' ? 'Đã nạp bộ giá trị mẫu lành tính.' : 'Đã nạp bộ giá trị mẫu ác tính.');
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function loadRandomSample() {
    setAgentCase(null);
    setBusy(true); setError(''); setSuccess('');
    try {
      const sample = await api('/api/random-sample');
      const next = {};
      featureNames.forEach((name, index) => { next[name] = String(sample.values[index]); });
      setValues(next);
      setSingleResult(null);
      setSuccess(`Đã nạp mẫu tham khảo #${sample.sample_id} từ bộ dữ liệu WDBC. Nhãn gốc được ẩn.`);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function chooseSingleFile(file) {
    setAgentCase(null);
    if (!file) return;
    setError(''); setSuccess(''); setSingleResult(null);
    try {
      const rows = parseCsv(await file.text(), featureNames);
      if (rows.length !== 1) throw new Error(`Dự đoán cá nhân chỉ nhận đúng 1 dòng dữ liệu; tệp hiện có ${rows.length} dòng.`);
      const next = {};
      featureNames.forEach((name, index) => { next[name] = String(rows[0][index]); });
      setValues(next);
      setSuccess(`Đã nạp 1 mẫu mới từ tệp ${file.name}. Nhấn “Phân tích mẫu” để dự đoán.`);
    } catch (err) { setError(err.message); }
  }

  async function predictSingle() {
    setError(''); setSuccess('');
    const row = featureNames.map(name => Number(values[name]));
    if (row.length !== 30 || featureNames.some(name => String(values[name] ?? '').trim() === '') || row.some(value => !Number.isFinite(value))) {
      setError('Bạn cần nhập đủ 30 đặc trưng bằng số hợp lệ trước khi dự đoán.');
      return;
    }
    setBusy(true);
    try {
      const result = await api('/api/predict', { method: 'POST', body: JSON.stringify({ values: row }) });
      setSingleResult(result);
      if (result.prediction_code === 'malignant') openAgent(result.history_id, 0, result, 'Mẫu cá nhân');
      await refreshHistory();
      setSuccess('Dự đoán đã hoàn tất và được lưu vào lịch sử phiên.');
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function chooseBatchFile(file) {
    setAgentCase(null);
    if (!file) return;
    setError(''); setSuccess(''); setBatchResult(null);
    try {
      const rows = parseCsv(await file.text(), featureNames);
      setBatchRows(rows);
      setBatchFileName(file.name);
      setSuccess(`Đã đọc ${rows.length} mẫu từ tệp ${file.name}.`);
    } catch (err) {
      setBatchRows([]); setBatchFileName(''); setError(err.message);
    }
  }


  async function predictBatch() {
    if (!batchRows.length) { setError('Hãy tải tệp CSV trước khi dự đoán.'); return; }
    setBusy(true); setError(''); setSuccess('');
    try {
      const result = await api('/api/predict-batch', { method: 'POST', body: JSON.stringify({ rows: batchRows }) });
      setBatchResult(result);
      const firstMalignant = result.items.findIndex(item => item.prediction_code === 'malignant');
      if (firstMalignant >= 0) openAgent(result.history_id, firstMalignant, result.items[firstMalignant], `Mẫu ${firstMalignant + 1} · hàng loạt`);
      await refreshHistory();
      setSuccess(`Đã dự đoán ${result.total} mẫu và lưu kết quả vào lịch sử phiên.`);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  function downloadTemplate() {
    downloadCsv([featureNames], 'breastcare_mau_du_lieu.csv');
  }

  function exportBatch() {
    if (!batchResult) return;
    const rows = [['STT', ...featureNames, 'Ket qua du doan', 'Xac suat ac tinh', 'Mo hinh']];
    batchResult.items.forEach((item, index) => rows.push([
      index + 1, ...(batchRows[index] || []), item.prediction,
      item.malignant_probability, item.model
    ]));
    downloadCsv(rows, 'breastcare_ket_qua_du_doan_hang_loat.csv');
  }

  async function sendTelegram(historyId) {
    setNotifyBusy(`telegram:${historyId}`); setError(''); setSuccess('');
    try {
      const result = await api('/api/notify/telegram', { method: 'POST', body: JSON.stringify({ history_id: historyId }) });
      setSuccess(result.message || 'Đã gửi Telegram.');
    } catch (err) { setError(err.message); }
    finally { setNotifyBusy(''); }
  }

  async function sendEmail(historyId) {
    if (!email.trim()) { setError('Hãy nhập địa chỉ email nhận kết quả.'); return; }
    setNotifyBusy(`email:${historyId}`); setError(''); setSuccess('');
    try {
      const result = await api('/api/notify/email', {
        method: 'POST',
        body: JSON.stringify({ history_id: historyId, recipient_email: email.trim() })
      });
      setSuccess(result.message || 'Đã gửi email.');
    } catch (err) { setError(err.message); }
    finally { setNotifyBusy(''); }
  }

  async function clearHistory() {
    if (!window.confirm('Bạn có chắc muốn xóa toàn bộ lịch sử của phiên trình duyệt này?')) return;
    setBusy(true); setError(''); setSuccess('');
    try {
      const result = await api('/api/history', { method: 'DELETE' });
      setHistory([]);
      setAgentCase(null);
      setSuccess(`Đã xóa ${result.deleted} bản ghi lịch sử.`);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  const activeRecordId = tab === 'personal' ? singleResult?.history_id : batchResult?.history_id;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><HeartPulse size={25} /></div>
          <div className="brand-copy">
            <strong>Chẩn đoán ung thư vú</strong>
            <small>HỆ THỐNG HỖ TRỢ PHÂN LOẠI</small>
          </div>
        </div>
        <div className="nav-caption">CHỨC NĂNG CHÍNH</div>
        <nav className="main-nav">
          <button className={`nav-item ${tab === 'personal' ? 'active' : ''}`} onClick={() => setTab('personal')}>
            <UserRound size={19} /> <span>Dự đoán cá nhân</span>
          </button>
          <button className={`nav-item ${tab === 'batch' ? 'active' : ''}`} onClick={() => setTab('batch')}>
            <FileSpreadsheet size={19} /> <span>Dự đoán hàng loạt</span>
          </button>
          <button className={`nav-item ${tab === 'history' ? 'active' : ''}`} onClick={() => { setTab('history'); refreshHistory().catch(err => setError(err.message)); }}>
            <History size={19} /> <span>Lịch sử phiên</span>
          </button>
        </nav>
        <div className="sidebar-bottom">
          <div className="edition"><span className="edition-dot" /> DEMO VERSION 2.1</div>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div className="breadcrumb"><span>BreastCare AI</span><b>/</b><strong>{tab === 'personal' ? 'Dự đoán cá nhân' : tab === 'batch' ? 'Dự đoán hàng loạt' : 'Lịch sử phiên'}</strong></div>
          <div className={`api-status ${online ? 'online' : 'offline'}`}>
            <span /> {online ? 'API đang hoạt động' : 'API chưa kết nối'}
          </div>
        </header>

        <div className="page-content">
          {error && <div className="alert alert-error"><AlertTriangle size={18} /><span>{error}</span><button onClick={() => setError('')} aria-label="Đóng"><XCircle size={17} /></button></div>}
          {success && <div className="alert alert-success"><CheckCircle2 size={18} /><span>{success}</span><button onClick={() => setSuccess('')} aria-label="Đóng"><XCircle size={17} /></button></div>}

          {tab === 'personal' && (
            <>
              <PageHeading eyebrow="PHÂN TÍCH MỘT MẪU" title="Dự đoán cá nhân" description="Nhập 30 đặc trưng của mẫu cần phân tích để nhận kết quả từ mô hình đã huấn luyện." />
              <div className="quick-actions">
                <button className="btn btn-light" onClick={() => loadExample('benign')} disabled={busy}><Activity size={16} /> Mẫu lành tính</button>
                <button className="btn btn-light" onClick={() => loadExample('malignant')} disabled={busy}><Activity size={16} /> Mẫu ác tính</button>
                <button className="btn btn-light" onClick={loadRandomSample} disabled={busy}><RefreshCw size={16} /> Lấy mẫu ngẫu nhiên</button>
                <label className="btn btn-light file-button"><UploadCloud size={16} /> Tải 1 mẫu CSV<input type="file" accept=".csv,text/csv" onChange={event => { chooseSingleFile(event.target.files?.[0]); event.target.value = ''; }} /></label>
                <span className="sample-note">Có thể nhập tay hoặc tải 1 dòng CSV mới theo 30 đặc trưng WDBC.</span>
              </div>
              <div className="predict-layout">
                <section className="card feature-card-wrap">
                  <div className="card-heading">
                    <div><h2>Thông số đầu vào</h2><p>Nhập giá trị chính xác hoặc điều chỉnh thanh trượt theo từng đặc trưng.</p></div>
                    <span className="count-pill">{featureNames.length || 30} đặc trưng</span>
                  </div>
                  <div className="feature-grid">
                    {featureStats.map((feature, index) => {
                      const current = values[feature.name] ?? '';
                      const numeric = Number(current);
                      const sliderValue = Number.isFinite(numeric) ? Math.min(feature.max, Math.max(feature.min, numeric)) : feature.mean;
                      const step = Math.max((feature.max - feature.min) / 1000, 0.000001);
                      return (
                        <div className="feature-field" key={feature.name}>
                          <div className="feature-title"><label htmlFor={`feature-${index}`}>{feature.name}</label><span>{index + 1}/30</span></div>
                          <div className="feature-range"><input type="range" min={feature.min} max={feature.max} step={step} value={sliderValue} onChange={event => updateValue(feature.name, event.target.value)} /></div>
                          <div className="feature-value-row">
                            <small>{number(feature.min)} – {number(feature.max)}</small>
                            <input id={`feature-${index}`} type="number" step="any" value={current} onChange={event => updateValue(feature.name, event.target.value)} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  <div className="form-footer">
                    <span>Đã nhập {Object.values(values).filter(value => value !== '' && Number.isFinite(Number(value))).length} / 30 giá trị</span>
                    <button className="btn btn-primary" onClick={predictSingle} disabled={busy || !online}>
                      {busy ? <span className="spinner" /> : <Activity size={17} />} Phân tích mẫu
                    </button>
                  </div>
                </section>
                <aside className="card result-card">
                  <div className="card-heading"><div><h2>Kết quả dự đoán</h2><p>Phản hồi từ mô hình trên Backend.</p></div></div>
                  {singleResult ? <PredictionResult result={singleResult} /> : <EmptyResult />}
                  {singleResult && <button className="btn btn-light agent-open" onClick={() => openAgent(singleResult.history_id, 0, singleResult, 'Mẫu cá nhân')}><Bot size={17} /> Hỏi trợ lý về ca này</button>}
                  {singleResult && <NotificationPanel
                    historyId={singleResult.history_id}
                    health={health}
                    email={email}
                    setEmail={setEmail}
                    notifyBusy={notifyBusy}
                    onTelegram={sendTelegram}
                    onEmail={sendEmail}
                  />}
                </aside>
              </div>
            </>
          )}

          {tab === 'batch' && (
            <>
              <PageHeading eyebrow="PHÂN TÍCH NHIỀU MẪU" title="Dự đoán hàng loạt" description="Tải tệp CSV gồm 30 đặc trưng WDBC để dự đoán tối đa 100 mẫu trong một lượt." />
              <div className="batch-toolbar">
                <button className="btn btn-light" onClick={downloadTemplate} disabled={!featureNames.length}><Download size={16} /> Tải CSV mẫu</button>
              </div>
              <div className="card upload-card">
                <label className="upload-zone">
                  <input type="file" accept=".csv,text/csv" onChange={event => chooseBatchFile(event.target.files?.[0])} />
                  <span className="upload-icon"><UploadCloud size={28} /></span>
                  <strong>{batchFileName || 'Chọn hoặc kéo thả tệp CSV vào đây'}</strong>
                  <small>CSV cần đủ 30 đặc trưng WDBC; hỗ trợ tiêu đề chuẩn/Kaggle hoặc 30 cột số, tối đa 100 dòng.</small>
                  <span className="btn btn-primary">Chọn tệp CSV</span>
                </label>
                {batchRows.length > 0 && <div className="file-summary"><CheckCircle2 size={18} /><span>Đã sẵn sàng <b>{batchRows.length}</b> mẫu để dự đoán.</span><button className="text-button" onClick={() => { setBatchRows([]); setBatchResult(null); setBatchFileName(''); }}>Bỏ tệp</button></div>}
                {batchRows.length > 0 && <div className="preview-table"><div className="table-caption">Xem trước 5 mẫu đầu tiên</div><div className="table-scroll"><table><thead><tr><th>STT</th><th>Mean radius</th><th>Mean texture</th><th>Mean perimeter</th><th>Mean area</th></tr></thead><tbody>{batchRows.slice(0, 5).map((row, index) => <tr key={index}><td>{index + 1}</td><td>{number(row[0])}</td><td>{number(row[1])}</td><td>{number(row[2])}</td><td>{number(row[3])}</td></tr>)}</tbody></table></div></div>}
                <div className="batch-submit"><span>Không cần cột nhãn để dự đoán; có thể bỏ qua ID/diagnosis nếu tệp có đủ 30 đặc trưng.</span><button className="btn btn-primary" onClick={predictBatch} disabled={busy || !batchRows.length || !online}>{busy ? <span className="spinner" /> : <Activity size={17} />} Dự đoán {batchRows.length || ''} mẫu</button></div>
              </div>
              {batchResult && <>
                <section className="card result-card batch-result-card">
                  <div className="card-heading"><div><h2>Kết quả dự đoán hàng loạt</h2><p>{batchResult.total} mẫu đã được xử lý và lưu lịch sử.</p></div><button className="btn btn-light" onClick={exportBatch}><Download size={16} /> Xuất kết quả CSV</button></div>
                  <div className="batch-stats">
                    <div><small>Tổng số mẫu</small><strong>{batchResult.total}</strong></div>
                    <div className="stat-benign"><small>Dự đoán lành tính</small><strong>{batchResult.benign_count}</strong></div>
                    <div className="stat-malignant"><small>Dự đoán ác tính</small><strong>{batchResult.malignant_count}</strong></div>
                  </div>
                  <div className="table-scroll"><table><thead><tr><th>STT</th><th>Kết quả dự đoán</th><th>Xác suất ác tính</th><th>Trợ lý AI</th></tr></thead><tbody>{batchResult.items.map((item, index) => <tr key={index}><td>{index + 1}</td><td><ResultBadge item={item} /></td><td>{percent(item.malignant_probability)}</td><td><button className="btn btn-light" onClick={() => openAgent(batchResult.history_id, index, item, `Mẫu ${index + 1} · hàng loạt`)}><Bot size={15} /> Hỏi trợ lý</button></td></tr>)}</tbody></table></div>
                  <NotificationPanel
                    historyId={batchResult.history_id}
                    health={health}
                    email={email}
                    setEmail={setEmail}
                    notifyBusy={notifyBusy}
                    onTelegram={sendTelegram}
                    onEmail={sendEmail}
                  />
                </section>
              </>}
            </>
          )}

          {tab === 'history' && (
            <>
              <PageHeading eyebrow="DỮ LIỆU ĐÃ LƯU" title="Lịch sử phiên" description="Các lần dự đoán được lưu ở cơ sở dữ liệu Backend và vẫn còn sau khi tải lại trang hoặc mở lại trình duyệt này." right={<div className="heading-actions"><button className="btn btn-light" onClick={() => refreshHistory().catch(err => setError(err.message))}><RefreshCw size={16} /> Làm mới</button><button className="btn btn-danger" onClick={clearHistory} disabled={!history.length || busy}><Trash2 size={16} /> Xóa lịch sử</button></div>} />
              <div className="history-summary">
                <div className="summary-tile"><Clock3 size={19} /><div><small>Lượt dự đoán đã lưu</small><strong>{history.length}</strong></div></div>
                <div className="summary-tile"><UserRound size={19} /><div><small>Lượt dự đoán cá nhân</small><strong>{history.filter(item => item.mode === 'individual').length}</strong></div></div>
                <div className="summary-tile"><FileSpreadsheet size={19} /><div><small>Lượt dự đoán hàng loạt</small><strong>{history.filter(item => item.mode === 'batch').length}</strong></div></div>
              </div>
              <section className="card history-card">
                <div className="card-heading"><div><h2>Các lần dự đoán gần đây</h2><p>Lịch sử được lọc theo mã phiên riêng của trình duyệt này.</p></div><span className="count-pill">Tối đa 50 lượt gần nhất</span></div>
                {!history.length ? <EmptyResult history /> : <div className="history-list">
                  {history.map(item => (
                    <details className="history-item" key={item.id}>
                      <summary>
                        <span className={`history-icon ${item.mode === 'batch' ? 'batch' : ''}`}>{item.mode === 'batch' ? <FileSpreadsheet size={18} /> : <UserRound size={18} />}</span>
                        <span className="history-main"><b>{item.mode === 'batch' ? `Dự đoán hàng loạt · ${item.total} mẫu` : 'Dự đoán cá nhân'}</b><small>{dateTime(item.created_at)} · {item.model_name}</small></span>
                        <span className="history-counts"><b className="text-danger">{item.malignant_count} ác tính</b><b className="text-success">{item.benign_count} lành tính</b></span>
                        <span className="expand-hint">Xem chi tiết</span>
                      </summary>
                      <div className="history-details">
                        <div className="history-meta"><span>Tổng: <b>{item.total}</b></span><span>Mô hình: <b>{item.model_name}</b></span></div>
                        <div className="table-scroll"><table><thead><tr><th>STT</th><th>Kết quả</th><th>Xác suất ác tính</th><th>Trợ lý AI</th></tr></thead><tbody>{(item.results || []).map((result, index) => <tr key={index}><td>{index + 1}</td><td><ResultBadge item={result} /></td><td>{percent(result.malignant_probability)}</td><td><button className="btn btn-light" onClick={() => openAgent(item.id, index, result, `Mẫu ${index + 1} · lịch sử`)}><Bot size={15} /> Hỏi trợ lý</button></td></tr>)}</tbody></table></div>
                      </div>
                    </details>
                  ))}
                </div>}
              </section>
            </>
          )}

          <footer className="page-footer"><ShieldCheck size={16} /><span>{DISCLAIMER}</span><b>BREASTCARE AI · DEMO VERSION 2.1</b></footer>
        </div>
      </main>
      {agentCase && <AgentPanel key={`${agentCase.historyId}:${agentCase.rowIndex}`} api={api} activeCase={agentCase} onClose={() => setAgentCase(null)} />}
    </div>
  );
}

function PageHeading({ eyebrow, title, description, right }) {
  return <div className="page-heading"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p>{description}</p></div>{right && <div>{right}</div>}</div>;
}
function EmptyResult({ history = false }) {
  return <div className="empty-result"><div className="empty-symbol">{history ? <History size={28} /> : <Activity size={28} />}</div><h3>{history ? 'Chưa có lịch sử dự đoán' : 'Chưa có kết quả'}</h3><p>{history ? 'Sau khi bạn thực hiện dự đoán cá nhân hoặc hàng loạt, các bản ghi sẽ xuất hiện tại đây.' : 'Nhập các đặc trưng ở bên trái rồi nhấn “Phân tích mẫu” để xem kết quả.'}</p></div>;
}
function ResultBadge({ item }) {
  const malignant = item.prediction_code === 'malignant' || item.prediction === 'Ác tính';
  return <span className={`result-badge ${malignant ? 'malignant' : 'benign'}`}>{malignant ? 'Ác tính' : 'Lành tính'}</span>;
}
function PredictionResult({ result }) {
  const malignant = result.prediction_code === 'malignant' || result.prediction === 'Ác tính';
  return <div className="prediction-result">
    <div className={`result-symbol ${malignant ? 'malignant' : 'benign'}`}>{malignant ? <AlertTriangle size={27} /> : <CheckCircle2 size={27} />}</div>
    <span className="result-kicker">KẾT QUẢ PHÂN LOẠI</span>
    <h2 className={malignant ? 'text-danger' : 'text-success'}>{result.prediction}</h2>
    <div className="probability-label"><span>Xác suất ác tính do mô hình ước lượng</span><b>{percent(result.malignant_probability)}</b></div>
    <div className="probability-track"><span className={malignant ? 'malignant' : 'benign'} style={{ width: `${Math.max(0, Math.min(100, result.malignant_probability * 100))}%` }} /></div>
    
    <div className="result-meta"><span>Mô hình sử dụng</span><b>{result.model}</b></div>
    <div className="result-warning"><AlertTriangle size={16} /><span>{DISCLAIMER}</span></div>
  </div>;
}
function NotificationPanel({ historyId, health, email, setEmail, notifyBusy, onTelegram, onEmail }) {
  if (!historyId) return null;
  const telegramBusy = notifyBusy === `telegram:${historyId}`;
  const emailBusy = notifyBusy === `email:${historyId}`;
  return <div className="notification-panel">
    <div className="notification-heading"><Send size={16} /><b>Gửi kết quả dự đoán</b></div>
    <button className="btn btn-telegram" onClick={() => onTelegram(historyId)} disabled={telegramBusy || !health?.telegram_configured}>
      <Bot size={16} /> {telegramBusy ? 'Đang gửi...' : 'Gửi tới Telegram Bot'}
    </button>
    {!health?.telegram_configured && <small className="config-hint">Cần cấu hình Bot Token và Chat ID trên Backend.</small>}
    <div className="email-send-row"><input type="email" placeholder="Email người nhận" value={email} onChange={event => setEmail(event.target.value)} /><button className="btn btn-email" onClick={() => onEmail(historyId)} disabled={emailBusy || !health?.email_configured}><Mail size={16} /> {emailBusy ? 'Đang gửi...' : 'Gửi email'}</button></div>
    {!health?.email_configured && <small className="config-hint">Cần cấu hình SMTP trên Backend để gửi email.</small>}
    <small className="privacy-hint">Thông tin Bot Token và mật khẩu email chỉ được lưu ở Backend, không gửi xuống trình duyệt.</small>
  </div>;
}

createRoot(document.getElementById('root')).render(<App />);
