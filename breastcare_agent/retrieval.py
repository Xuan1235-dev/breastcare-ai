import json
import re
from pathlib import Path
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

EXPANSIONS = {
    'kích thước': 'size radius nuclei tumor', 'bán kính': 'radius nuclei',
    'độ lõm': 'concavity concave points', 'kết cấu': 'texture',
    'ác tính': 'malignant malignancy breast cancer', 'điều trị': 'treatment therapy',
    'phác đồ': 'treatment biomarkers stage ER PR HER2', 'giai đoạn': 'stage staging',
    'nhỏ': 'small size radius', 'tế bào': 'cell nuclei nuclear',
}

class Retriever:
    def __init__(self, path):
        self.path = Path(path)
        self.stamp = None
        self.rows = []
        self.matrix = None

    def refresh(self):
        stamp = self.path.stat().st_mtime_ns if self.path.exists() else None
        if stamp == self.stamp:
            return
        rows = json.loads(self.path.read_text(encoding='utf-8')) if stamp else []
        if not isinstance(rows, list) or len(rows) > 20000:
            raise ValueError('Invalid corpus')
        for row in rows:
            if not all(isinstance(row.get(k), str) and row[k] for k in ('id', 'title', 'text', 'source', 'version')):
                raise ValueError('Missing source metadata')
        self.rows, self.stamp = rows, stamp
        if rows:
            self.vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=(3, 5), max_features=60000)
            self.matrix = self.vectorizer.fit_transform([r['title'] + ' ' + r['text'] for r in rows])
        else:
            self.matrix = None

    def search(self, query, limit=5):
        self.refresh()
        if self.matrix is None:
            return []
        query = query[:1000]
        lower = query.lower()
        query += ' ' + ' '.join(v for k, v in EXPANSIONS.items() if k in lower)
        scores = (self.matrix @ self.vectorizer.transform([query]).T).toarray().ravel()
        indices = np.argsort(-scores)[:limit]
        return [{**self.rows[i], 'score': round(float(scores[i]), 4)} for i in indices if scores[i] >= 0.06]
