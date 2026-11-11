# Trợ lý BreastCare — cấu hình và giới hạn

## Chạy

Backend (PowerShell tại thư mục dự án):

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

Frontend (Terminal thứ hai):

```powershell
cd frontend
npm.cmd run dev
```

Mở http://127.0.0.1:5173. Dự đoán mẫu ác tính để mở trợ lý tự động.
Với bảng hàng loạt, tự mở ca ác tính đầu tiên; dùng nút **Hỏi trợ lý** ở từng dòng để đổi ca.
Trong lịch sử cũng có nút theo từng mẫu. Trợ lý dùng dữ liệu đã lưu ở backend,
không lấy nội dung đang sửa trên biểu mẫu. Đổi ca sẽ tạo hội thoại mới.

## Bật AI Agent có mô hình ngôn ngữ

Tạo `.env` từ `.env.example` nếu chưa có; giữ nguyên các cấu hình hiện hữu.
Điền ở backend, không đặt khóa trong frontend hoặc biến `VITE_*`:

```dotenv
AGENT_ENABLED=true
OPENAI_API_KEY=YOUR_API_KEY
OPENAI_MODEL=gpt-4.1-mini
```

Khởi động lại backend. Có thể đổi `OPENAI_MODEL` sang mô hình được tài khoản API
cho phép và hỗ trợ Chat Completions, function calling, JSON mode.
Khóa API và quyền sử dụng API do chủ dự án cung cấp. Việc bật chế độ này gửi
30 giá trị, thống kê mô hình, các câu hỏi và đoạn tài liệu tới OpenAI; không nhập
thông tin định danh hay bệnh án thật. Không lưu khóa vào mã nguồn.

Nếu chưa bật, giao diện ghi rõ **Phân tích cục bộ**: vẫn tính số liệu và truy xuất
tài liệu nhưng câu trả lời theo mẫu, không giả là LLM hiểu câu hỏi tự do.
Khi gọi AI lỗi, hết ngân sách bước hoặc nguồn trích dẫn không hợp lệ, trả về phân
tích cục bộ có thông báo. Một lượt tối đa 5 lần gọi API, 5 công cụ mỗi lần;
backend giới hạn 2 yêu cầu phân tích đồng thời. Chưa có xác thực tài khoản hay
hạn mức theo người dùng: cần bổ sung trước khi mở dịch vụ công khai có API trả phí.

## Agent thực hiện gì

1. Backend xác minh mã phiên sở hữu ca và lấy đúng dòng đã lưu.
2. Đọc 30 đặc trưng và phân vị trên Train.
3. Thay từng đặc trưng bằng trung vị Train, chạy lại chính mô hình đã lưu.
4. So sánh thay đồng thời nhóm kích thước nhân, hình dạng, texture; tính tương quan Pearson trên Train.
5. Truy xuất các đoạn tài liệu bằng TF-IDF ký tự 3–5 và cosine similarity.
6. Khi bật LLM: bắt buộc ít nhất một vòng gọi công cụ; Agent có thể tìm tài liệu
   bổ sung, kiểm tra tương quan hay thử nhóm đặc trưng, rồi tổng hợp có nguồn.

Các công cụ chỉ đọc và tính toán, không sửa dự đoán, không gửi thông báo, không
chạy mã do LLM sinh, không truy cập URL do người hỏi cung cấp. UI hiển thị bước
công cụ đã chạy, không hiển thị chuỗi suy nghĩ nội bộ. Nội dung AI được render
dạng văn bản, không thực thi HTML. ID nguồn được đối chiếu với kết quả truy xuất;
đây không phải kiểm chứng tự động rằng mọi khẳng định đều được nguồn hỗ trợ.

## Kho tài liệu

`backend/knowledge/seed.json` chứa **bản tóm tắt tiếng Việt có nguồn**, được kiểm
tra ngày 12/11/2026: UCI WDBC và NCI Breast Cancer Treatment PDQ (bản chuyên môn).
Đây là kho khởi đầu nhỏ, không phải toàn văn phác đồ; không cập nhật web theo
thời gian thực và **chưa có NCCN hoặc hướng dẫn Bộ Y tế**.

Để bổ sung tài liệu được phép sử dụng, tạo tệp JSON trong `backend/knowledge/`
theo cấu trúc bên dưới, kiểm tra nội dung rồi khởi động lại backend. Trích văn bản
từ PDF trước và giữ đúng số trang trong `section`; không tự suy đoán số trang.
Không có chức năng tải tài liệu qua API công khai để tránh đầu độc kho nguồn.

```json
[
  {
    "id": "unique-document-id",
    "title": "Tên tài liệu và phiên bản",
    "url": "https://official-source.example/document",
    "section": "Mục hoặc số trang chính xác",
    "reviewed_on": "YYYY-MM-DD",
    "kind": "Trích đoạn được phép sử dụng hoặc bản tóm tắt đã kiểm tra",
    "text": "Nội dung tài liệu thực tế đã được quản trị viên xác minh."
  }
]
```

Hệ thống chia văn bản thành các đoạn tối đa 200 từ, chồng lấn 50 từ, giữ metadata
và ID trích dẫn. Nếu không có tài liệu đủ liên quan, phải báo thiếu căn cứ.
Không đổi tiêu đề nguồn thành NCCN/Bộ Y tế khi nội dung không đến từ nguồn đó.

## Diễn giải đúng

WDBC mô tả nhân tế bào trên ảnh FNA; radius không phải kích thước khối u theo cm.
Độ nhạy thay trung vị là phép khảo sát mô hình, không phải SHAP, không cộng thành
100%, không chứng minh nhân quả. Các biến tương quan có thể làm phép thay tạo
mẫu không thực tế. Nhóm được thay bằng nhiều trung vị cũng có giới hạn này.
Xác suất là đầu ra mô hình, không được khẳng định là nguy cơ lâm sàng đã hiệu chuẩn.
Các ca ngoài miền Train được đánh dấu trong bảng 30 chỉ số.
Không suy ra giai đoạn hay phác đồ cá thể hóa từ WDBC; cần các dữ liệu lâm sàng,
mô bệnh học và dấu ấn sinh học tương ứng. Mục đích là học tập và nghiên cứu.

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
cd frontend
npm.cmd run build
```

Kiểm thử bao gồm độ nhạy khớp mô hình, nguồn truy xuất, kho rỗng, vòng công cụ
LLM giả lập, fallback, phân quyền phiên và chọn đúng dòng hàng loạt.
Kiểm thử không gọi dịch vụ trả phí; muốn xác minh end-to-end LLM cần khóa API thật.
