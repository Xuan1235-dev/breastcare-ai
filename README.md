# BreastCare AI V3.1 – Bộ mã nguồn hoàn chỉnh

Bản này bao gồm mã nguồn Frontend/Backend, dữ liệu WDBC mẫu, dữ liệu chia Train/Validation/Test, mô hình đã huấn luyện và báo cáo đánh giá. Không bao gồm môi trường `.venv`, `node_modules`, tệp `.env` hoặc lịch sử dự đoán cá nhân.

## 1. Chức năng

- Giao diện sáng, chỉ có 3 mục: **Dự đoán cá nhân**, **Dự đoán hàng loạt**, **Lịch sử phiên**.
- Dự đoán cá nhân bằng cách nhập 30 chỉ số hoặc tải CSV có đúng 1 mẫu.
- Dự đoán hàng loạt từ CSV 1–100 mẫu; xem trước dữ liệu và xuất CSV gồm dữ liệu đầu vào + kết quả.
- Lịch sử phiên được lưu ở Backend (SQLite local; PostgreSQL cho cloud).
- Gửi kết quả tới Telegram Bot hoặc email SMTP sau khi cấu hình thông tin ở Backend.
- Huấn luyện WDBC theo tỷ lệ Train 70%, Validation 15%, Test 15%.

## 2. Cài đặt trên Windows / VS Code

Giải nén toàn bộ nội dung ZIP trực tiếp vào thư mục dự án, ví dụ `D:\breast_cancer_vscode`. Mở Terminal PowerShell tại thư mục gốc và chạy:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Nếu đã có `.venv` hoạt động thì không cần tạo lại môi trường.

### Chạy Backend

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

### Chạy Frontend ở Terminal thứ hai

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Mở `http://127.0.0.1:5173`.

## 3. Huấn luyện lại mô hình

Từ thư mục gốc:

```powershell
.\.venv\Scripts\python.exe -m ml.train
```

Script sẽ tái tạo:
- `data/train.csv` – 398 mẫu
- `data/validation.csv` – 85 mẫu
- `data/test.csv` – 86 mẫu
- `models/best_model.joblib`, `models/metadata.json`
- các báo cáo trong `results/`

Tập Train dùng để fit và GridSearchCV 5-fold. Validation dùng để chọn mô hình/ngưỡng. Test chỉ dùng đánh giá cuối cùng sau khi đã cố định mô hình và ngưỡng.

Lần kiểm tra ngày 09/11/2026 đã tạo môi trường hoạt động `.venv-retrain` (Python 3.12); môi trường `.venv` đi kèm trỏ về Python trên máy LENOVO và không chạy được trên máy hiện tại. Dùng môi trường mới từ thư mục gốc dự án:

```powershell
.\.venv-retrain\Scripts\python.exe -m ml.train
.\.venv-retrain\Scripts\python.exe -m unittest discover -s tests -v
.\.venv-retrain\Scripts\python.exe -m uvicorn backend.main:app --reload
```

Script đọc trực tiếp `data/breast_cancer.csv` có nhãn `malignant` (0=lành tính, 1=ác tính), kiểm tra dữ liệu rồi chia tập theo seed 42. Không ghi đè dữ liệu nguồn bằng dataset đóng gói trong sklearn. Model cũ được giữ ở `models/before_retrain/`.

Các báo cáo mới: `results/split_metrics.csv`, `results/{train,validation,test}_predictions.csv`, `results/{train,validation,test}_errors.csv`, `results/threshold_comparison.csv`. Cột `source_row` là số dòng trong CSV nguồn (tính cả tiêu đề). `Error_Rate` là tỷ lệ sai trên toàn tập; `False_Negative_Rate` là tỷ lệ bỏ sót trong các mẫu ác tính. Xác suất ác tính của từng mẫu không phải tỷ lệ sai của mô hình.

## 4. Đưa dữ liệu mới vào dự đoán

- **Cá nhân:** nhập 30 giá trị hoặc nhấn **Tải 1 mẫu CSV**. Tệp cần có đúng 1 dòng dữ liệu.
- **Hàng loạt:** nhấn **Tải CSV mẫu**, thêm dữ liệu vào các dòng tiếp theo, lưu CSV rồi tải lên. Mỗi lượt tối đa 100 mẫu.
- Hệ thống hỗ trợ tên cột chuẩn của CSV mẫu và các tên WDBC/Kaggle thông dụng như `radius_mean`, `radius_se`, `radius_worst`; hỗ trợ dấu phẩy hoặc dấu chấm phẩy.
- Có thể giữ thêm `id` và `diagnosis` nếu CSV có tiêu đề và đủ 30 cột đặc trưng. Mô hình chỉ sử dụng 30 đặc trưng, không dùng cột nhãn.
- CSV không có tiêu đề phải có đúng 30 cột số; định dạng WDBC gốc không tiêu đề `ID, diagnosis, 30 đặc trưng` cũng được hỗ trợ.

**Lưu ý:** Dữ liệu mới tải lên được đưa qua mô hình hiện có để dự đoán, không tự động trở thành dữ liệu huấn luyện. Muốn huấn luyện lại cần bộ dữ liệu có nhãn chẩn đoán thực tế. Dữ liệu đầu vào phải tương thích 30 đặc trưng WDBC; dữ liệu có cấu trúc/đơn vị khác cần được chuẩn hóa trước.

## 5. Cấu hình Telegram và email

Sao chép `.env.example` thành `.env` ở thư mục gốc và điền thông tin:

```env
TELEGRAM_BOT_TOKEN=token_bot
TELEGRAM_CHAT_ID=chat_id
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=email_gui
SMTP_PASSWORD=mat_khau_ung_dung
SMTP_FROM=email_gui
SMTP_USE_TLS=true
FRONTEND_ORIGIN=http://127.0.0.1:5173
```

Với Gmail, dùng App Password (mật khẩu ứng dụng), không dùng mật khẩu đăng nhập thông thường. Khởi động lại Backend sau khi sửa `.env`. Không đưa `.env` lên GitHub.

## 6. Triển khai Vercel + Render

**Vercel:** Root Directory `frontend`, Build Command `npm run build`, Output Directory `dist`, Environment Variable `VITE_API_URL=https://<backend-render-domain>`. Redeploy sau khi đổi biến.

**Render:** Build Command `pip install -r requirements-deploy.txt`; Start Command `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`. Cấu hình `FRONTEND_ORIGIN` bằng domain Vercel. Muốn lịch sử tồn tại ổn định sau khi deploy lại, tạo PostgreSQL trên Render và đặt `DATABASE_URL` bằng Internal Database URL thực tế.

## 7. Đánh giá mô hình trong lần huấn luyện hiện tại

- Tổng 569 mẫu: Train 398, Validation 85, Test 86.
- Huấn luyện lại ngày 09/11/2026: SVM RBF; ngưỡng 0.50, chọn trên Validation từ các ngưỡng 0.20–0.50, ưu tiên Recall với Precision >= 85%.
- Kết quả Test: Accuracy 96.51%, Precision 96.77%, Recall 93.75%, F1 95.24%, ROC-AUC 99.88%.
- Test có 2 mẫu ác tính bị bỏ sót và 1 mẫu lành tính bị báo nhầm ác tính. Tỷ lệ sai chung 3.49%; tỷ lệ bỏ sót ác tính 6.25%. Không lựa chọn lại mô hình theo kết quả Test.
- Kiểm tra model cũ cũng có dự đoán ác tính: Train 144, Validation 30, Test 30. Không tái hiện được lỗi “mọi mẫu đều lành tính” khi đưa đúng dữ liệu WDBC vào model.
- Giao diện cũ điền sẵn cùng một vector trung bình (xác suất ác tính khoảng 19.15%), nên phân tích lặp lại sẽ luôn trả lành tính. Giao diện mới yêu cầu nhập hoặc nạp mẫu thật, chặn ô trống và hiển thị bảng đánh giá ba tập. CSV mẫu chỉ còn tiêu đề để tránh lặp lại mẫu trung bình.
- Các chỉ số chỉ phản ánh bộ dữ liệu WDBC và không chứng minh hiệu quả lâm sàng. Kết quả Train là kết quả trên dữ liệu đã học, không dùng để ước lượng hiệu quả trên dữ liệu mới.

## 8. Lưu ý an toàn

Đây là ứng dụng minh họa học máy phục vụ học tập/nghiên cứu, không phải thiết bị y tế và không thay thế bác sĩ, xét nghiệm hay chẩn đoán lâm sàng. Không nhập thông tin nhận dạng cá nhân hoặc hồ sơ bệnh án thật.
