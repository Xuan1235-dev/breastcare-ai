from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.datasets import load_breast_cancer
from sklearn.model_selection import train_test_split, StratifiedKFold, GridSearchCV, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (accuracy_score, precision_score, recall_score, f1_score, roc_auc_score,
                             roc_curve, ConfusionMatrixDisplay)

ROOT = Path(__file__).resolve().parents[1]
for folder in ('data', 'models', 'results'):
    (ROOT / folder).mkdir(exist_ok=True)
raw = load_breast_cancer()
X = pd.DataFrame(raw.data, columns=raw.feature_names)
y = pd.Series((raw.target == 0).astype(int), name='malignant')  # 1=malignant
export = X.copy()
export['malignant'] = y
export.to_csv(ROOT / 'data' / 'breast_cancer.csv', index=False)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=.2, random_state=42, stratify=y)
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
models = {
    'Logistic Regression': (Pipeline([('scale', StandardScaler()), ('clf', LogisticRegression(max_iter=3000, random_state=42))]), {'clf__C': [0.01, 0.1, 1, 10]}),
    'SVM RBF': (Pipeline([('scale', StandardScaler()), ('clf', SVC(kernel='rbf', probability=True, random_state=42))]), {'clf__C': [0.1, 1, 10], 'clf__gamma': ['scale', 0.01, 0.1]}),
    'k-NN': (Pipeline([('scale', StandardScaler()), ('clf', KNeighborsClassifier())]), {'clf__n_neighbors': [3, 5, 7, 9], 'clf__weights': ['uniform', 'distance']}),
    'Random Forest': (Pipeline([('clf', RandomForestClassifier(random_state=42))]), {'clf__n_estimators': [100, 200], 'clf__max_depth': [None, 5, 10], 'clf__min_samples_leaf': [1, 2]})
}
rows = []
trained = {}
for name, (pipe, grid) in models.items():
    print(f'\nTraining {name}...', flush=True)
    search = GridSearchCV(pipe, grid, scoring='recall', cv=cv, n_jobs=-1, refit=True)
    search.fit(X_train, y_train)
    model = search.best_estimator_
    trained[name] = (model, search.best_score_, search.best_params_)
    pred = model.predict(X_test)
    prob = model.predict_proba(X_test)[:, 1]
    rows.append({'Model': name, 'CV_Recall': search.best_score_, 'Accuracy': accuracy_score(y_test, pred),
                 'Precision': precision_score(y_test, pred), 'Recall': recall_score(y_test, pred),
                 'F1': f1_score(y_test, pred), 'ROC_AUC': roc_auc_score(y_test, prob),
                 'False_Negatives': int(((y_test == 1) & (pred == 0)).sum())})
results = pd.DataFrame(rows)
results.to_csv(ROOT / 'results' / 'model_comparison.csv', index=False)
# Select ONLY from training cross-validation, never from test performance.
best_name = max(trained, key=lambda n: trained[n][1])
best, cv_recall, params = trained[best_name]
# Tune threshold with out-of-fold probabilities from training only.
oof = cross_val_predict(best, X_train, y_train, cv=cv, method='predict_proba', n_jobs=-1)[:, 1]
thresholds = np.round(np.arange(0.20, 0.81, 0.05), 2)
threshold_scores = [(float(t), recall_score(y_train, (oof >= t).astype(int)),
                     precision_score(y_train, (oof >= t).astype(int), zero_division=0)) for t in thresholds]
# Select maximum recall subject to precision >= 0.85; break ties by precision and then higher threshold.
eligible = [row for row in threshold_scores if row[2] >= .85]
threshold = max(eligible, key=lambda r: (r[1], r[2], r[0]))[0] if eligible else .5
joblib.dump(best, ROOT / 'models' / 'best_model.joblib')
metadata = {'model_name': best_name, 'feature_names': list(X.columns), 'threshold': threshold,
            'positive_class': 'malignant', 'cv_recall': float(cv_recall), 'best_params': params,
            'disclaimer': 'Research/education only. Not a clinical diagnostic tool.'}
(ROOT / 'models' / 'metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
prob = best.predict_proba(X_test)[:, 1]
pred = (prob >= threshold).astype(int)
print('\nCOMPARISON (default 0.5 threshold):\n', results.to_string(index=False))
print(f'\nSelected: {best_name}; threshold={threshold}; held-out recall={recall_score(y_test,pred):.3f}; false negatives={int(((y_test==1)&(pred==0)).sum())}')
ConfusionMatrixDisplay.from_predictions(y_test, pred, display_labels=['Benign', 'Malignant'], cmap='Blues')
plt.title(f'{best_name} (threshold={threshold})')
plt.tight_layout(); plt.savefig(ROOT / 'results' / 'confusion_matrix.png', dpi=160); plt.close()
plt.figure(figsize=(7, 5))
for name, (model, _, _) in trained.items():
    p = model.predict_proba(X_test)[:, 1]
    fpr, tpr, _ = roc_curve(y_test, p)
    plt.plot(fpr, tpr, label=f'{name} (AUC={roc_auc_score(y_test,p):.3f})')
plt.plot([0, 1], [0, 1], '--', color='gray')
plt.xlabel('False Positive Rate'); plt.ylabel('True Positive Rate'); plt.title('ROC curves')
plt.legend(); plt.tight_layout(); plt.savefig(ROOT / 'results' / 'roc_curve.png', dpi=160); plt.close()
plt.figure(figsize=(8, 4))
plt.bar(results['Model'], results['Recall'])
plt.ylim(0, 1.05); plt.ylabel('Malignant recall'); plt.xticks(rotation=15, ha='right')
plt.tight_layout(); plt.savefig(ROOT / 'results' / 'model_comparison.png', dpi=160); plt.close()
clf = best.named_steps['clf']
if hasattr(clf, 'feature_importances_'):
    importance = clf.feature_importances_
elif hasattr(clf, 'coef_'):
    importance = np.abs(clf.coef_[0])
else:
    from sklearn.inspection import permutation_importance
    importance = permutation_importance(best, X_test, y_test, scoring='recall', n_repeats=5, random_state=42).importances_mean
indices = np.argsort(importance)[-12:]
plt.figure(figsize=(9, 5)); plt.barh(np.array(X.columns)[indices], importance[indices]); plt.title('Feature importance (model-dependent)')
plt.tight_layout(); plt.savefig(ROOT / 'results' / 'feature_importance.png', dpi=160); plt.close()
