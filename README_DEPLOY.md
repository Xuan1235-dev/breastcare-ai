# Hướng dẫn đưa BreastCare AI V2.1 lên Internet (Vercel + Render)

Chạy trên Windows PowerShell trong `D:\breast_cancer_vscode`:

```powershell
python .\cau_hinh_deploy_breastcare.py
```

Script chỉnh đúng hai vị trí: API URL React và CORS FastAPI; giữ các chức năng hiện có. Tạo các file `.python-version`, `.gitignore`, `requirements-deploy.txt`, `frontend/vercel.json`. Có bản sao lưu `.bak_deploy`.

## 1. Chuẩn bị mã và mô hình trên máy tính

```powershell
cd D:\breast_cancer_vscode
Test-Path .\models\best_model.joblib
Test-Path .\models\metadata.json
Test-Path .\data\breast_cancer.csv
Test-Path .\results\model_comparison.csv
```

Tất cả phải là `True`; nếu thiếu, chạy `python -m ml.train` trước khi đưa lên GitHub. Những file dữ liệu / mô hình này phải có trong repo, vì máy chủ không dùng được ổ D: của bạn.

## 2. Đưa mã nguồn lên GitHub

Tạo repository trống trên github.com (ví dụ `breastcare-ai`). Đứng tại gốc dự án và chạy:

```powershell
git init
git add .
git commit -m "Deploy BreastCare AI"
git branch -M main
git remote add origin https://github.com/TEN_TAI_KHOAN/breastcare-ai.git
git push -u origin main
```

Thay `TEN_TAI_KHOAN` bằng tên GitHub của bạn. Nếu bạn đã có repository Git, không chạy `git init`/`remote add` lặp; chỉ cần `git add .`, `git commit ...`, `git push`.

Trước khi push hãy kiểm tra `git status`, bảo đảm KHÔNG tải lên mật khẩu, `.env`, dữ liệu bệnh nhân thật hoặc khóa bí mật. Repo công khai chỉ dành cho mã và bộ dữ liệu nghiên cứu công khai.

## 3. Deploy Backend FastAPI trên Render

- Mở https://dashboard.render.com → New → Web Service → chọn repository GitHub.
- **Root Directory**: để trống (vì cần truy cập `backend`, `models`, `data`, `results`).
- **Language/Runtime**: Python.
- **Build Command**: `pip install -r requirements-deploy.txt`
- **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- **Plan**: Free để demo (có thể ngủ khi ít dùng).
- File `.python-version` đặt Python 3.14.8 để phù hợp máy gốc. Nếu joblib/sklearn báo không tương thích, cần đồng bộ phiên bản scikit-learn hai môi trường; không nạp file joblib không tin cậy.
- Deploy. Nhận URL Render có dạng `https://breastcare-api-xxxx.onrender.com`.
- Kiểm tra: `https://<TEN-DICH-VU>.onrender.com/api/health` phải hiện JSON `status: ok, model_loaded: true`.

## 4. Deploy Frontend React trên Vercel

- Mở https://vercel.com/new → import **cùng repository GitHub**.
- **Root Directory**: `frontend`.
- **Framework**: Vite.
- **Build Command**: `npm run build`.
- **Output Directory**: `dist`.
- **Environment Variables**:
  - KEY: `VITE_API_URL`
  - VALUE: `https://breastcare-api-xxxx.onrender.com` (URL Render của bạn, KHÔNG kèm `/api`)
- Chọn Production, nhấn Deploy. Nhận địa chỉ `https://<ten-web>.vercel.app`.

Quan trọng: `VITE_API_URL` được nhúng khi build, sửa biến này thì phải Redeploy frontend.

## 5. Bật CORS để trang web kết nối được mô hình

Render → backend → Environment → Add Environment Variable:

- KEY: `FRONTEND_ORIGIN`
- VALUE: `https://<ten-web>.vercel.app` (không có dấu `/` cuối)

Save & Deploy/restart service. Đảm bảo URL khớp chính xác giao diện công khai. Sau đó kiểm tra bằng mạng 4G trên điện thoại:

- Trang Tổng quan lấy dữ liệu thành công.
- Trang Dự đoán cá nhân → thử mẫu minh họa → có kết quả.
- Trang Dự đoán hàng loạt → thử CSV/100 mẫu ngẫu nhiên → có kết quả.
- Các biểu đồ xuất hiện ở trang So sánh mô hình.

## 6. Khắc phục lỗi thường gặp

- `Không kết nối được backend`: kiểm tra Vercel `VITE_API_URL`, Render /api/health, Render log; kiểm tra CORS FRONTEND_ORIGIN đúng tên miền.
- `RuntimeError: Chua co mo hinh`: phải push `models/best_model.joblib`, `models/metadata.json`, `data/breast_cancer.csv` lên GitHub; kiểm tra `.gitignore` không loại chúng.
- `Model version mismatch`: đồng bộ phiên bản sklearn giữa file joblib và requirements của máy chủ. Chỉ load mô hình do chính bạn tạo, không load joblib tải không rõ nguồn.
- `Không có biểu đồ`: push các file `results/*.png` và `results/model_comparison.csv`.
- Render Free ngủ sau 15 phút nhàn rỗi và khởi động lại khi có request; muốn API luôn sẵn sàng nhanh phải chọn gói có máy chủ luôn hoạt động.
- Không đưa dữ liệu y tế cá nhân thật lên ứng dụng demo công khai khi chưa có bảo vệ phù hợp. Mô hình này chỉ mang tính học tập, **không thay thế chẩn đoán của bác sĩ**.

Nguồn: https://render.com/docs/deploy-fastapi ; https://render.com/docs/free ; https://vercel.com/docs/frameworks/frontend/vite
