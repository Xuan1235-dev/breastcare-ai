# BreastCare AI — VS Code Edition 2.1

**Dự án minh họa môn Học máy. Không dùng để chẩn đoán hay ra quyết định điều trị.**

## Tính năng

1. **Tổng quan** — 4 KPI, phân phối dữ liệu, biểu đồ Recall / ROC-AUC và mô hình được chọn.
2. **Khám phá dữ liệu** — phân phối nhãn, histogram tùy chọn 30 đặc trưng, thống kê và xem trước dữ liệu.
3. **So sánh mô hình** — bảng 4 thuật toán, GridSearchCV, ROC, Confusion Matrix, feature importance.
4. **Dự đoán cá nhân** — 30 thanh trượt có Min/Max theo dữ liệu thật, ô số nhập chính xác, nút mẫu ngẫu nhiên từ tất cả 569 bản ghi, nút mẫu lành tính/ác tính, khởi tạo giá trị TB (mẫu tổng hợp), xuất kết quả CSV.
5. **Dự đoán hàng loạt** — tải file CSV mẫu, dự đoán tối đa 100 hàng, xuất CSV kết quả.
6. **Lịch sử phiên** — chỉ lưu tạm trong bộ nhớ trang, xóa khi tải lại. Có thể xuất hoặc xóa thủ công.
7. **Giới thiệu đề tài** — pipeline và giải thích thuật toán, Recall, False Negative.

## Nâng cấp từ dự án cũ mà không mất mô hình

Chỉ cần chép đè `frontend/` và `backend/main.py` từ gói nâng cấp, **giữ nguyên** `models/`, `data/`, `results/`, `.venv/`, `ml/` của bạn.

### Terminal 1 — Backend

Mở từ thư mục gốc của dự án, trên Windows:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

Mở http://127.0.0.1:8000/docs. Nếu backend cũ đang chạy với `--reload`, lưu `backend/main.py` sẽ tự reload; nếu không, nhấn Ctrl+C rồi chạy lại.

### Terminal 2 — Frontend

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Mở http://127.0.0.1:5173.

**Cần** có dữ liệu và mô hình từ lần chạy `python -m ml.train` trước đó. Nếu triển khai bằng gói dự án đầy đủ trên máy khác, chạy huấn luyện để tạo file models/data/results.

## API

- `GET /api/health`, `/api/info`, `/api/examples`, `/api/random-sample` (tùy chọn `?exclude_id=123`)
- `GET /api/dataset`, `/api/distribution?feature=mean%20radius`, `/api/results`
- `POST /api/predict` JSON `{ "values": [30 số] }`
- `POST /api/predict-batch` JSON `{ "rows": [[30 số], ...] }`, tối đa 100 mẫu
- `GET /charts/roc_curve.png` và các biểu đồ tạo khi train

## Lưu ý khoa học

- Nguồn: Wisconsin Diagnostic Breast Cancer, `sklearn.datasets.load_breast_cancer()`.
- Nhãn gốc được đổi: **1 = ác tính**, **0 = lành tính**.
- GridSearchCV chọn mô hình từ cross-validation trên tập train. Ngưỡng dự đoán dùng out-of-fold train; không tối ưu trên test.
- Các chỉ số trong bảng so sánh được báo cáo tại **ngưỡng 0.5**; demo dự đoán dùng **ngưỡng đã điều chỉnh** trong `metadata.json`.
- SVM sử dụng xác suất từ bản huấn luyện hiện có. Các xác suất không được xác thực lâm sàng.
- Không lưu thông tin bệnh nhân thật lên website minh họa.
- Chỉ nạp file `joblib` được chính bạn tạo ra, không nạp model từ nguồn lạ.

## Bổ sung V2.1: thanh trượt và mẫu ngẫu nhiên

- Vào **Dự đoán cá nhân**, 30 trường có thanh trượt; kéo để sửa nhanh hoặc nhập số chính xác bên dưới.
- Giới hạn thanh trượt lấy từ min/max của cột tương ứng trong `data/breast_cancer.csv`; đây **không phải** giới hạn y khoa. Nếu nhập ngoài khoảng, website sẽ cảnh báo nhưng vẫn cho phép thử nghiệm.
- Nút **Lấy mẫu ngẫu nhiên** gọi API `/api/random-sample`, mỗi lần chọn đều từ **toàn bộ 569 mẫu**, có loại trừ lần chọn ngay trước để tránh trùng liên tiếp. Giao diện chỉ hiện mã mẫu, không tiết lộ nhãn thật trước dự đoán.
- Giá trị khởi tạo **trung bình** của 30 cột chỉ là mẫu tổng hợp để thao tác thanh trượt ngay, **không phải mẫu thực trong dataset**.
- Giữ nguyên `models/`, `results/`, `data/`, `.venv/` và `ml/`; không cần huấn luyện lại.
- Cần khởi động lại backend để API mới hoạt động nếu không dùng `--reload`.
