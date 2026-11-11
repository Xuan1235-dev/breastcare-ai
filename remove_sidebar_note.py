"""Run: python remove_sidebar_note.py [project_directory]"""
from pathlib import Path
from datetime import datetime
import os
import re
import shutil
import sys

def update(text):
    pattern = r'\s*<div className="sidebar-note">\s*<div className="note-icon">.*?</div>\s*<strong>Không gian thực nghiệm</strong>\s*<p>.*?</p>\s*</div>'
    result, count = re.subn(pattern, '', text, flags=re.S)
    if count > 1 or 'className="sidebar-note"' in result or 'Không gian thực nghiệm' in result:
        raise ValueError('Cau truc giao dien khac ban da kiem tra. Chua thay doi file nao.')
    return result

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
        print('Khung Khong gian thuc nghiem da duoc bo.')
        return
    backup = path.parent / ('breastcare_backup_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    backup.mkdir()
    shutil.copy2(path, backup / path.name)
    try:
        path.write_text(result, encoding='utf-8')
    except Exception:
        shutil.copy2(backup / path.name, path)
        raise
    print('DA BO khung Khong gian thuc nghiem trong thanh ben.')
    print('BAN SAO LUU: ' + str(backup))
    print('Tai lai trang web bang Ctrl + F5.')

if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('LOI: ' + str(error), file=sys.stderr)
        sys.exit(1)
