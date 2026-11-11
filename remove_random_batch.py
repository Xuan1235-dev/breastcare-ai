"""Run from the project directory: python remove_random_batch.py"""
from pathlib import Path
from datetime import datetime
import os
import re
import shutil
import sys

def update(text):
    text = re.sub(r'\n  async function loadRandomBatch\(\) \{.*?\n  \}\n', '\n', text, flags=re.S)
    text = re.sub(r'\s*<button\b[^>]*onClick=\{loadRandomBatch\}.*?</button>', '', text, flags=re.S)
    text = text.replace('Tải tệp CSV gồm 30 đặc trưng hoặc lấy mẫu từ WDBC, sau đó dự đoán tối đa 100 mẫu trong một lượt.', 'Tải tệp CSV gồm 30 đặc trưng WDBC để dự đoán tối đa 100 mẫu trong một lượt.')
    text = text.replace('Hãy tải tệp CSV hoặc lấy 100 mẫu ngẫu nhiên trước.', 'Hãy tải tệp CSV trước khi dự đoán.')
    if any(token in text for token in ['loadRandomBatch', '/api/random-batch', 'Lấy 100 mẫu ngẫu nhiên']):
        raise ValueError('Ma nguon khac ban da kiem tra. Chua thay doi file nao.')
    return text

def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
    matches = []
    for directory, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in {'node_modules', '.venv', 'venv', '.git', 'dist', 'build', '__pycache__'} and not d.startswith('breastcare_backup_')]
        for name in files:
            if name.endswith(('.jsx', '.tsx')):
                path = Path(directory) / name
                text = path.read_text(encoding='utf-8-sig')
                if 'breastcare_session_id' in text and 'function PredictionResult(' in text:
                    matches.append((path, text))
    if len(matches) != 1:
        raise ValueError('Can dung 1 file giao dien BreastCare, tim thay %s. Hay chay trong thu muc frontend chinh.' % len(matches))
    path, original = matches[0]
    result = update(original)
    if result == original:
        print('Phan lay 100 mau ngau nhien da duoc bo. Khong can sua them.')
        return
    backup = path.parent / ('breastcare_backup_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    backup.mkdir()
    shutil.copy2(path, backup / path.name)
    try:
        path.write_text(result, encoding='utf-8')
    except Exception:
        shutil.copy2(backup / path.name, path)
        raise
    print('DA BO: nut Lay 100 mau ngau nhien va ham goi API tuong ung.')
    print('GIU LAI: tai CSV, du doan hang loat, lay mau ngau nhien ca nhan va giao dien hien tai.')
    print('BAN SAO LUU: ' + str(backup))
    print('Tai lai trang web bang Ctrl + F5.')

if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('LOI: ' + str(error), file=sys.stderr)
        sys.exit(1)
