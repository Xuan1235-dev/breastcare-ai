"""Patch BreastCare AI V2.1: 100 random WDBC rows + one-click predictions.
Run from the project root: python them_100_mau_ngau_nhien.py
Makes .bak_random100 backups before changing files.
"""
from pathlib import Path
import shutil

ROOT = Path.cwd()
BACK = ROOT / 'backend' / 'main.py'
FRONT = ROOT / 'frontend' / 'src.jsx'
STYLE = ROOT / 'frontend' / 'style.css'
for path in (BACK, FRONT, STYLE):
    if not path.is_file():
        raise SystemExit(f'Khong tim thay {path}. Hay chay trong thu muc goc D:\\breast_cancer_vscode')

backend = BACK.read_text(encoding='utf-8')
frontend = FRONT.read_text(encoding='utf-8')
style = STYLE.read_text(encoding='utf-8')

# An exact-structure check prevents applying a patch meant for V2.1 to another version.
if "@app.get('/api/random-batch')" in backend or 'async function generateRandomBatch()' in frontend:
    raise SystemExit('Tinh nang 100 mau ngau nhien co ve da duoc cai. Khong sua lap.')

endpoint_anchor = "@app.get('/api/dataset')\ndef dataset_summary():"
endpoint = '''@app.get('/api/random-batch')
def random_batch(count: int = Query(default=100, ge=1, le=100)):
    """Return uniformly sampled distinct WDBC rows, WITHOUT revealing target labels.

    Sampling without replacement within each request; subsequent requests can overlap.
    """
    size = len(dataset)
    if count > size:
        raise HTTPException(status_code=400, detail='So mau vuot qua kich thuoc dataset')
    positions = secrets.SystemRandom().sample(range(size), count)
    selected = dataset.iloc[positions]
    return {
        'rows': selected.loc[:, features].astype(float).values.tolist(),
        'sample_ids': [int(i) + 1 for i in positions],
        'count': count,
        'total_samples': size,
        'message': '100 mau ngau nhien tu WDBC. Nhan goc duoc an.',
    }


'''

state_old = "  const [rows,setRows] = useState([]),[fileName,setFileName]=useState(''),[err,setErr]=useState(''),[working,setWorking]=useState(false),[results,setResults]=useState([]);"
state_new = "  const [rows,setRows] = useState([]),[fileName,setFileName]=useState(''),[err,setErr]=useState(''),[working,setWorking]=useState(false),[results,setResults]=useState([]),[randomBusy,setRandomBusy]=useState(false);"

old_func = "  async function predictBatch(){if(!rows.length)return;setWorking(true);setErr('');try{const data=await api('/api/predict-batch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({rows})});setResults(data.items);onRecord({time:new Date().toLocaleString('vi-VN'),type:'Hàng loạt',source:fileName,label:`${data.items.length} mẫu`,probability:null});}catch(e){setErr(e.message);}finally{setWorking(false);}}"
new_funcs = '''  async function predictBatch(inputRows=rows, sourceName=fileName){
    if(!inputRows.length)return;
    setWorking(true);setErr('');
    try {
      const data=await api('/api/predict-batch', {
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({rows:inputRows})
      });
      setResults(data.items);
      onRecord({time:new Date().toLocaleString('vi-VN'),type:'Hàng loạt',source:sourceName,
        label:`${data.items.length} mẫu`,probability:null});
    } catch(e) {setErr(e.message);}
    finally {setWorking(false);}
  }
  async function generateRandomBatch(){
    if(working || randomBusy)return;
    setRandomBusy(true);setErr('');setResults([]);
    try {
      const data=await api('/api/random-batch?count=100');
      if(!Array.isArray(data.rows) || data.rows.length!==100 ||
         data.rows.some(row=>!Array.isArray(row)||row.length!==30)) {
        throw new Error('API không trả về đúng 100 mẫu gồm 30 đặc trưng.');
      }
      const name='100 mẫu ngẫu nhiên từ WDBC (569 mẫu)';
      setRows(data.rows);setFileName(name);
      // Send the newly fetched rows directly; React state is asynchronous.
      await predictBatch(data.rows, name);
    } catch(e) {setErr(`Không thể tạo mẫu ngẫu nhiên: ${e.message}`);}
    finally {setRandomBusy(false);}
  }'''

old_ui = '<Card title="Nhập bộ dữ liệu" subtitle="Định dạng CSV: hàng đầu là tên 30 đặc trưng, mỗi hàng sau là một mẫu"><label className="upload-zone">'
new_ui = '''<Card title="Nhập bộ dữ liệu" subtitle="Có thể tạo ngay 100 mẫu ngẫu nhiên hoặc tải lên tệp CSV">
      <div className="random100-panel">
        <div><strong><Shuffle size={18}/> Mẫu ngẫu nhiên từ dữ liệu WDBC</strong>
        <p>Chọn 100/569 mẫu thực tế, không trùng trong một lần lấy. Tự điền và dự đoán, không cần tệp CSV.</p></div>
        <button className="btn btn-primary" disabled={working||randomBusy} onClick={generateRandomBatch}>
          <Shuffle size={17}/>{working||randomBusy?'Đang tạo và dự đoán...':'Tạo 100 mẫu ngẫu nhiên'}
        </button>
      </div>
      <label className="upload-zone">'''

css = '''
/* BreastCare V2.1 - Tao 100 mau ngau nhien trong trang Du doan hang loat */
.random100-panel { display:flex; justify-content:space-between; align-items:center; gap:16px; padding:18px; margin-bottom:18px; border:1px solid #c7d2fe; background:linear-gradient(110deg,#eef2ff,#f8fafc); border-radius:14px; }
.random100-panel strong { display:flex; align-items:center; gap:8px; color:#283b7c; font-size:15px; }
.random100-panel p { margin:6px 0 0; color:#64748b; font-size:13px; line-height:1.55; }
.random100-panel button { flex-shrink:0; }
@media (max-width:700px) { .random100-panel { flex-direction:column; align-items:stretch; } .random100-panel button { width:100%; justify-content:center; } }
'''

def replace_once(s, old, new, label):
    count = s.count(old)
    if count != 1:
        raise SystemExit(f'Khong tim thay dung vi tri {label} (so lan: {count}). Khong sua file nao. Gui src.jsx va main.py de duoc ho tro.')
    return s.replace(old, new, 1)

backend = replace_once(backend, endpoint_anchor, endpoint + endpoint_anchor, 'API')
frontend = replace_once(frontend, state_old, state_new, 'state BatchPage')
frontend = replace_once(frontend, old_func, new_funcs, 'predictBatch')
frontend = replace_once(frontend, old_ui, new_ui, 'nut trong BatchPage')
frontend = replace_once(frontend, 'onClick={predictBatch}', 'onClick={()=>predictBatch()}', 'su kien nut Du doan')
style += css
for path in (BACK, FRONT, STYLE):
    backup = path.with_name(path.name + '.bak_random100')
    if not backup.exists():
        shutil.copy2(path, backup)
BACK.write_text(backend, encoding='utf-8')
FRONT.write_text(frontend, encoding='utf-8')
STYLE.write_text(style, encoding='utf-8')
print('DA CAP NHAT THANH CONG!')
print('Da them API GET /api/random-batch?count=100 va nut tao 100 mau trong Du doan hang loat.')
print('Da sao luu main.py, src.jsx va style.css (*.bak_random100).')
print('Hay khoi dong lai Backend va Frontend trong VS Code.')
