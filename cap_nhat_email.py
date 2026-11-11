"""BreastCare AI: patch only frontend mail panel; preserve Agent/Ollama/RAG and backend."""
from pathlib import Path
import re
import shutil
import sys
from datetime import datetime

root = Path(__file__).resolve().parent
# Allow file alongside project or inside patch subdirectory
if not (root / 'frontend' / 'src.jsx').exists():
    root = root.parent
source = root / 'frontend' / 'src.jsx'
if not source.is_file():
    sys.exit('LOI: Khong tim thay frontend/src.jsx. Dat cap_nhat_email.py vao thu muc goc du an.')
text = source.read_text(encoding='utf-8-sig')
if 'BREASTCARE_EMAIL_ONLY_V1' in text:
    print('Da cai patch email truoc do. Khong can cai lai.')
    sys.exit(0)

if 'function NotificationPanel(' not in text or 'onTelegram={sendTelegram}' not in text or "'/api/notify/email'" not in text:
    sys.exit('LOI: Cau truc src.jsx da khac ban mau. Khong ghi de; hay gui file src.jsx hien tai de chinh xac.')

panel = '''// BREASTCARE_EMAIL_ONLY_V1: Người truy cập nhập email của chính mình, backend gửi tới đó.
function NotificationPanel({ historyId, health, email, setEmail, notifyBusy, onEmail }) {
  if (!historyId) return null;
  const emailBusy = notifyBusy === `email:${historyId}`;
  const validEmail = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(email.trim());
  return <div className="notification-panel">
    <div className="notification-heading"><Mail size={16} /><b>Nhận kết quả dự đoán qua email</b></div>
    <p>Nhập email của bạn để nhận kết quả dự đoán của ca vừa phân tích.</p>
    <div className="email-send-row">
      <input
        type="email"
        aria-label="Địa chỉ email nhận kết quả"
        placeholder="Email của bạn, ví dụ: ban@gmail.com"
        value={email}
        maxLength={254}
        autoComplete="email"
        onChange={event => setEmail(event.target.value)}
        onKeyDown={event => { if (event.key === 'Enter' && validEmail && !emailBusy && health?.email_configured) onEmail(historyId); }}
      />
      <button className="btn btn-email" onClick={() => onEmail(historyId)}
        disabled={emailBusy || !health?.email_configured || !validEmail}>
        <Mail size={16} /> {emailBusy ? 'Đang gửi...' : 'Gửi kết quả vào email của tôi'}
      </button>
    </div>
    {!health?.email_configured && <small className="config-hint">Chưa cấu hình Gmail SMTP trên Backend.</small>}
    <small className="privacy-hint">Email được gửi tới địa chỉ bạn vừa nhập. Tài khoản gửi và mật khẩu SMTP chỉ nằm trên Backend. Chỉ gửi dữ liệu bạn có quyền chia sẻ.</small>
  </div>;
}
'''

# Replace only the component, not the Agent/RAG code in other parts of src.jsx.
start = text.index('function NotificationPanel(')
end = text.find('\ncreateRoot(', start)
if end < 0:
    sys.exit('LOI: Khong tim thay ranh gioi cuoi NotificationPanel. Khong thay doi file.')
text = text[:start] + panel + text[end:]
text = text.replace('onTelegram={sendTelegram}', '')
# Remove obsolete function with an anchor to the following existing email method.
text, n = re.subn(r'(?ms)^  async function sendTelegram\(historyId\) \{.*?(?=^  async function sendEmail\(historyId\) \{)', '', text, count=1)
if n != 1:
    sys.exit('LOI: Khong tim thay ham sendTelegram trong ban nay. Khong thay doi file.')
# Bot icon may be used elsewhere: leave imports unchanged to avoid breaking unrelated UI.
backup = source.with_name('src.jsx.bak-email-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
shutil.copy2(source, backup)
source.write_text(text, encoding='utf-8')
print('OK: Da sua', source)
print('Ban sao luu:', backup)
print('Email nhan duoc lay tu o nhap, khong lay tu SMTP_USER / SMTP_FROM.')
print('Khong sua backend/main.py, Agent, Ollama, RAG, hay .env.')
