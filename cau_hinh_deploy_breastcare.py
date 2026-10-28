"""Prepare an existing BreastCare AI V2.1 project for Vercel + Render.
Preserves existing UI and features. Run from the project root.
"""
from pathlib import Path
import re
import shutil

root = Path(__file__).resolve().parent
frontend = root / 'frontend' / 'src.jsx'
backend = root / 'backend' / 'main.py'
if not (frontend.is_file() and backend.is_file()):
    raise SystemExit('LOI: Can dat file nay trong D:\\breast_cancer_vscode (noi co frontend/src.jsx va backend/main.py).')


def patch(path: Path, transform):
    original = path.read_text(encoding='utf-8')
    updated = transform(original)
    if updated == original:
        print(f'Khong can sua: {path.relative_to(root)}')
        return
    backup = path.with_suffix(path.suffix + '.bak_deploy')
    if not backup.exists():
        shutil.copy2(path, backup)
    path.write_text(updated, encoding='utf-8')
    print(f'Da cap nhat: {path.relative_to(root)} (co ban sao luu)')


def frontend_transform(s):
    if 'import.meta.env.VITE_API_URL' in s:
        return s
    needle = "const API = 'http://127.0.0.1:8000';"
    if needle not in s:
        raise SystemExit('Khong tim thay bien const API mac dinh trong frontend/src.jsx. Hay xem README_DEPLOY.md de sua thu cong.')
    return s.replace(needle, "const API = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000').replace(/\\/$/, '');", 1)


def backend_transform(s):
    if 'FRONTEND_ORIGIN' in s:
        return s
    s = re.sub(r'(?m)^import json$', 'import json\nimport os', s, count=1)
    needle = "allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'],"
    if needle not in s:
        raise SystemExit('Khong tim thay cau hinh CORS mac dinh trong backend/main.py. Hay xem README_DEPLOY.md de sua thu cong.')
    replacement = "allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'] + [url.strip().rstrip('/') for url in os.getenv('FRONTEND_ORIGIN', '').split(',') if url.strip()],"
    return s.replace(needle, replacement, 1)

patch(frontend, frontend_transform)
patch(backend, backend_transform)
(root / '.python-version').write_text('3.14.8\n', encoding='utf-8')
(root / 'requirements-deploy.txt').write_text('''numpy>=1.24,<3
pandas>=2.0,<3
scikit-learn>=1.3,<2
joblib>=1.3,<2
fastapi>=0.110,<1
uvicorn>=0.27,<1
pydantic>=2,<3
''', encoding='utf-8')
(root / '.gitignore').write_text('''# Local Python / Node environments
.venv/
venv/
__pycache__/
*.py[cod]
.pytest_cache/
frontend/node_modules/
frontend/dist/
node_modules/
.env
.env.*
!.env.example
# Local backups, archives, OS files
*.bak_deploy
*.bak_random100
*.bak_synthetic100
*.zip
.DS_Store
Thumbs.db
# KEEP: data/*.csv, models/*.joblib, models/*.json, results/*
''', encoding='utf-8')
vercel = root / 'frontend' / 'vercel.json'
if not vercel.exists():
    vercel.write_text('''{\n  "rewrites": [\n    { "source": "/(.*)", "destination": "/index.html" }\n  ]\n}\n''', encoding='utf-8')
print('\nHOAN TAT CAU HINH DEPLOY!')
print('Tiep theo: kiem tra data/, models/, results/; dua code len GitHub; deploy backend Render truoc, frontend Vercel sau.')
print('HUONG DAN: README_DEPLOY.md (trong file ZIP cung cap).')
