"""Huấn luyện BreastCare AI với 3 tập Train / Validation / Test độc lập.

Chạy từ thư mục gốc dự án: python -m ml.train
- Train: fit pipeline và GridSearchCV 5-fold để chọn siêu tham số.
- Validation: chọn mô hình và ngưỡng phân loại.
- Test: chỉ đánh giá sau khi đã cố định mô hình và ngưỡng.

Dữ liệu WDBC dùng cho giảng dạy/nghiên cứu, không dùng để chẩn đoán lâm sàng.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import platform

import joblib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.datasets import load_breast_cancer
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    confusion_matrix,
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

ROOT = Path(__file__).resolve().parents[1]
for folder in ('data', 'models', 'results'):
    (ROOT / folder).mkdir(exist_ok=True)

SEED = 42
raw = load_breast_cancer()
# Read the project's labelled data; never silently replace it with sklearn data.
source_path = ROOT / 'data' / 'breast_cancer.csv'
all_data = pd.read_csv(source_path)
if set(all_data.columns) != {*raw.feature_names, 'malignant'}:
    raise ValueError('Dataset must contain 30 WDBC features and malignant (0=benign, 1=malignant).')
X = all_data.loc[:, raw.feature_names].apply(pd.to_numeric, errors='raise')
y = all_data['malignant']
if not np.isfinite(X.to_numpy()).all() or not y.isin([0, 1]).all() or y.nunique() != 2:
    raise ValueError('Dataset contains missing/non-finite values or invalid labels.')
if X.duplicated().any():
    raise ValueError('Duplicate feature rows must be resolved before splitting to prevent leakage.')
y = y.astype(int)

# 569 mau -> 398 Train, 85 Validation, 86 Test.
# Chia theo nhan, co random_state de tai lap, khong chong cheo.
X_train, X_temp, y_train, y_temp = train_test_split(
    X, y, test_size=0.30, random_state=SEED, stratify=y
)
X_val, X_test, y_val, y_test = train_test_split(
    X_temp, y_temp, test_size=0.50, random_state=SEED, stratify=y_temp
)


def export_split(filename, x_part, y_part):
    part = x_part.copy()
    part['malignant'] = y_part
    part.to_csv(ROOT / 'data' / filename, index=False)


export_split('train.csv', X_train, y_train)
export_split('validation.csv', X_val, y_val)
export_split('test.csv', X_test, y_test)
assert len(X_train) + len(X_val) + len(X_test) == len(X)
assert set(X_train.index).isdisjoint(X_val.index)
assert set(X_train.index).isdisjoint(X_test.index)
assert set(X_val.index).isdisjoint(X_test.index)

split_sizes = {
    'train': len(X_train), 'validation': len(X_val), 'test': len(X_test),
    'total': len(X), 'seed': SEED,
    'train_malignant': int(y_train.sum()),
    'validation_malignant': int(y_val.sum()),
    'test_malignant': int(y_test.sum()),
}
print('\nCHIA DU LIEU 70/15/15:', split_sizes, flush=True)

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
models = {
    'Logistic Regression': (
        Pipeline([('scale', StandardScaler()),
                  ('clf', LogisticRegression(max_iter=3000, random_state=SEED))]),
        {'clf__C': [0.01, 0.1, 1, 10]},
    ),
    'SVM RBF': (
        Pipeline([('scale', StandardScaler()),
                  ('clf', SVC(kernel='rbf', probability=True, random_state=SEED))]),
        {'clf__C': [0.1, 1, 10], 'clf__gamma': ['scale', 0.01, 0.1]},
    ),
    'k-NN': (
        Pipeline([('scale', StandardScaler()), ('clf', KNeighborsClassifier())]),
        {'clf__n_neighbors': [3, 5, 7, 9],
         'clf__weights': ['uniform', 'distance']},
    ),
    'Random Forest': (
        Pipeline([('clf', RandomForestClassifier(random_state=SEED))]),
        {'clf__n_estimators': [100, 200],
         'clf__max_depth': [None, 5, 10],
         'clf__min_samples_leaf': [1, 2]},
    ),
}


def scores(y_true, predictions, probabilities):
    tn, fp, fn, tp = confusion_matrix(y_true, predictions, labels=[0, 1]).ravel()
    return {
        'Accuracy': float(accuracy_score(y_true, predictions)),
        'Precision': float(precision_score(y_true, predictions, zero_division=0)),
        'Recall': float(recall_score(y_true, predictions, zero_division=0)),
        'F1': float(f1_score(y_true, predictions, zero_division=0)),
        'ROC_AUC': float(roc_auc_score(y_true, probabilities)),
        'False_Negatives': int(((y_true == 1) & (predictions == 0)).sum()),
        'False_Positives': int(fp),
        'True_Positives': int(tp),
        'True_Negatives': int(tn),
        'Error_Rate': float((fp + fn) / len(y_true)),
        'False_Negative_Rate': float(fn / (tp + fn)),
        'Specificity': float(tn / (tn + fp)),
        'Predicted_Malignant': int(tp + fp),
        'Predicted_Benign': int(tn + fn),
    }

# 1) Chi fit model tren TRAIN; GridSearchCV 5 folds cung chi dung TRAIN.
trained = {}
validation_rows = []
for name, (pipeline, param_grid) in models.items():
    print(f'\nTRAIN + CV: {name}...', flush=True)
    search = GridSearchCV(
        pipeline, param_grid, scoring='recall', cv=cv, n_jobs=-1, refit=True
    )
    search.fit(X_train, y_train)
    model = search.best_estimator_
    trained[name] = {
        'model': model,
        'cv_recall': float(search.best_score_),
        'params': search.best_params_,
    }

    # 2) Dung VALIDATION de so sanh cac model, KHONG dung TEST de chon.
    val_prob = model.predict_proba(X_val)[:, 1]
    val_pred = (val_prob >= 0.50).astype(int)
    val_metrics = scores(y_val, val_pred, val_prob)
    validation_rows.append({
        'Model': name, 'CV_Recall': float(search.best_score_), **val_metrics
    })

val_results = pd.DataFrame(validation_rows)
val_results.to_csv(ROOT / 'results' / 'validation_comparison.csv', index=False)

# Chon: Recall validation cao nhat; neu hoa, AUC, Precision va CV Recall.
best_row = max(
    validation_rows,
    key=lambda r: (r['Recall'], r['ROC_AUC'], r['Precision'], r['CV_Recall'])
)
best_name = best_row['Model']
best = trained[best_name]['model']
cv_recall = trained[best_name]['cv_recall']
params = trained[best_name]['params']

# 3) Chon nguong dua tren VALIDATION, khong xem nhan TEST.
val_prob = best.predict_proba(X_val)[:, 1]
# Do not raise the screening threshold above 0.50 on a small validation set.
threshold_candidates = np.round(np.arange(0.20, 0.51, 0.05), 2)
threshold_scores = []
for candidate in threshold_candidates:
    predictions = (val_prob >= candidate).astype(int)
    threshold_scores.append((
        float(candidate),
        float(recall_score(y_val, predictions, zero_division=0)),
        float(precision_score(y_val, predictions, zero_division=0)),
    ))
valid_thresholds = [row for row in threshold_scores if row[2] >= 0.85]
threshold = (
    max(valid_thresholds, key=lambda row: (row[1], row[2], row[0]))[0]
    if valid_thresholds else 0.50
)
selected_val_scores = scores(y_val, (val_prob >= threshold).astype(int), val_prob)
pd.DataFrame(threshold_scores, columns=['Threshold', 'Recall', 'Precision']).to_csv(
    ROOT / 'results' / 'threshold_comparison.csv', index=False
)

# Model cuoc cung CHI FIT tren TRAIN; VALIDATION khong bi dung de fit.
joblib.dump(best, ROOT / 'models' / 'best_model.joblib')

# 4) Cuoi cung moi doc tap TEST cho viec danh gia.
# Bao cao tat ca mo hinh tren test (nguong mac dinh 0.50) de giu tuong thich
# Dashboard cu; viec chon model/nguong da hoan tat truoc khoi lenh nay.
test_rows = []
for name, info in trained.items():
    model = info['model']
    test_prob_model = model.predict_proba(X_test)[:, 1]
    test_pred_model = (test_prob_model >= 0.50).astype(int)
    test_rows.append({
        'Model': name, 'CV_Recall': info['cv_recall'],
        **scores(y_test, test_pred_model, test_prob_model),
    })
results = pd.DataFrame(test_rows)
results.to_csv(ROOT / 'results' / 'model_comparison.csv', index=False)

best_test_prob = best.predict_proba(X_test)[:, 1]
best_test_pred = (best_test_prob >= threshold).astype(int)
final_test_scores = scores(y_test, best_test_pred, best_test_prob)

# Report resubstitution errors separately from held-out validation/test errors.
split_metrics = {}
for split_name, x_part, y_part in (
    ('train', X_train, y_train), ('validation', X_val, y_val), ('test', X_test, y_test)
):
    probability = best.predict_proba(x_part)[:, list(best.classes_).index(1)]
    prediction = (probability >= threshold).astype(int)
    split_metrics[split_name] = scores(y_part, prediction, probability)
    if np.unique(prediction).size != 2:
        raise RuntimeError(f'Degenerate model predicts only one class on {split_name}.')
    detail = x_part.copy()
    detail.insert(0, 'source_row', x_part.index + 2)
    detail['actual_malignant'] = y_part
    detail['predicted_malignant'] = prediction
    detail['malignant_probability'] = probability
    detail['correct'] = prediction == y_part.to_numpy()
    detail.to_csv(ROOT / 'results' / f'{split_name}_predictions.csv', index=False)
    detail.loc[~detail['correct']].to_csv(
        ROOT / 'results' / f'{split_name}_errors.csv', index=False
    )
pd.DataFrame.from_dict(split_metrics, orient='index').rename_axis('Split').to_csv(
    ROOT / 'results' / 'split_metrics.csv'
)

# Luu du doan test kem nhan that: phuc vu kiem tra voi giang vien.
test_predictions = X_test.copy()
test_predictions['actual_malignant'] = y_test
test_predictions['predicted_malignant'] = best_test_pred
test_predictions['malignant_probability'] = best_test_prob
# The detailed test_predictions.csv above also includes source rows and errors.

metadata = {
    'model_name': best_name,
    'feature_names': list(X.columns),
    'threshold': threshold,
    'positive_class': 'malignant',
    'cv_recall': float(cv_recall),
    'best_params': params,
    'split': split_sizes,
    'validation_metrics': selected_val_scores,
    'test_metrics': final_test_scores,
    'train_metrics': split_metrics['train'],
    'class_labels': {'0': 'benign', '1': 'malignant'},
    'trained_at': datetime.now(timezone.utc).isoformat(),
    'python_version': platform.python_version(),
    'sklearn_version': sklearn.__version__,
    'dataset_sha256': hashlib.sha256(source_path.read_bytes()).hexdigest(),
    'selection_rule': 'Max validation Recall, then ROC_AUC, Precision, CV_Recall',
    'threshold_rule': 'Validation Recall max with Precision >= 0.85; candidates 0.20..0.50; ties: precision, then threshold',
    'disclaimer': 'Research/education only. Not a clinical diagnostic tool.',
}
(ROOT / 'models' / 'metadata.json').write_text(
    json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8'
)
(ROOT / 'results' / 'split_summary.json').write_text(
    json.dumps({
        'split_sizes': split_sizes,
        'selected_model': best_name,
        'selected_threshold': threshold,
        'validation_metrics': selected_val_scores,
        'final_test_metrics': final_test_scores,
        'train_metrics': split_metrics['train'],
    }, ensure_ascii=False, indent=2), encoding='utf-8'
)

print('\nVALIDATION (cho viec chon model; nguong mac dinh 0.50):\n',
      val_results.to_string(index=False))
print('\nTEST (bao cao cac model; nguong mac dinh 0.50):\n',
      results.to_string(index=False))
print(f'\nSELECTED VIA VALIDATION: {best_name}; threshold={threshold:.2f}')
print('FINAL TEST METRICS (selected model & threshold):', final_test_scores)

# Ve bieu do test sau khi da co dinh model va threshold.
ConfusionMatrixDisplay.from_predictions(
    y_test, best_test_pred,
    display_labels=['Benign', 'Malignant'], cmap='Blues'
)
plt.title(f'{best_name} (Test, threshold={threshold:.2f})')
plt.tight_layout()
plt.savefig(ROOT / 'results' / 'confusion_matrix.png', dpi=160)
plt.close()

plt.figure(figsize=(7, 5))
for name, info in trained.items():
    p = info['model'].predict_proba(X_test)[:, 1]
    fpr, tpr, _ = roc_curve(y_test, p)
    plt.plot(fpr, tpr, label=f'{name} (AUC={roc_auc_score(y_test, p):.3f})')
plt.plot([0, 1], [0, 1], '--', color='gray')
plt.xlabel('False Positive Rate')
plt.ylabel('True Positive Rate')
plt.title('ROC Curves on Test Set')
plt.legend()
plt.tight_layout()
plt.savefig(ROOT / 'results' / 'roc_curve.png', dpi=160)
plt.close()

plt.figure(figsize=(8, 4))
plt.bar(results['Model'], results['Recall'])
plt.ylim(0, 1.05)
plt.ylabel('Malignant recall (Test, threshold=0.50)')
plt.xticks(rotation=15, ha='right')
plt.tight_layout()
plt.savefig(ROOT / 'results' / 'model_comparison.png', dpi=160)
plt.close()

# Dung VALIDATION cho feature importance, khong chon lai model bang TEST.
clf = best.named_steps['clf']
if hasattr(clf, 'feature_importances_'):
    importance = clf.feature_importances_
elif hasattr(clf, 'coef_'):
    importance = np.abs(clf.coef_[0])
else:
    importance = permutation_importance(
        best, X_val, y_val, scoring='recall',
        n_repeats=5, random_state=SEED
    ).importances_mean
indices = np.argsort(importance)[-12:]
plt.figure(figsize=(9, 5))
plt.barh(np.array(X.columns)[indices], importance[indices])
plt.title('Feature importance (model-dependent)')
plt.tight_layout()
plt.savefig(ROOT / 'results' / 'feature_importance.png', dpi=160)
plt.close()

print('\nDA LUU: data/train.csv, data/validation.csv, data/test.csv,')
print('results/validation_comparison.csv, results/model_comparison.csv,')
print('results/test_predictions.csv, results/split_summary.json,')
print('models/best_model.joblib, models/metadata.json va cac bieu do.')
