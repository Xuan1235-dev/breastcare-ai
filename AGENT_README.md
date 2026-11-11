# BreastCare Agent — bản tích hợp phục vụ học tập

## Cài đặt trên Windows

1. Dừng backend và frontend bằng Ctrl+C trước khi cài.
2. Đặt `install_breastcare_agent.py` vào thư mục gốc dự án, mở PowerShell ở đó:

```powershell
python install_breastcare_agent.py
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-agent.txt
python -m breastcare_agent.ingest --nci
```

3. Mở `.env` ở thư mục gốc, thêm hai dòng sau, thay giá trị mẫu bằng khóa riêng của bạn:

```dotenv
OPENAI_API_KEY=YOUR_PRIVATE_API_KEY
OPENAI_MODEL=gpt-4.1-mini
```

Không thêm `VITE_` trước API key, không đưa `.env` lên Git và không gửi khóa qua chat. Dùng model Responses API có hỗ trợ function calling và structured outputs mà tài khoản được phép truy cập. API cần hạn mức sử dụng riêng; kiểm tra quyền truy cập và chi phí trong tài khoản nhà cung cấp.

4. Khởi động lại backend bằng lệnh vốn dùng cho dự án. Nếu module là `backend/main.py`:

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

5. Terminal khác: chuyển vào thư mục chứa `package.json`, chạy `npm run dev`. Mở frontend trên localhost:5173 hoặc 127.0.0.1:5173 phù hợp cấu hình CORS hiện có.
6. Mở nút **Trợ lý AI** ở góc phải dưới. Bật tùy chọn gửi dữ liệu tới OpenAI. Sau đó dự đoán mẫu cá nhân ác tính: Agent tự mở và phân tích. Bật tùy chọn khi đang có kết quả ác tính cũng sẽ phân tích ca đó.
7. Với hàng loạt hoặc lịch sử: chọn đúng mẫu trong bảng chọn của Agent và bấm **Phân tích ca đang chọn**. Không tự gửi đồng loạt 100 mẫu.

Nếu mô hình không trả lời tự động, lỗi được hiển thị trong panel; dùng nút phân tích để thử lại. API trả 429 khi đang xử lý yêu cầu khác: chờ lượt trước xong. Không cần huấn luyện lại SVM để cài Agent.

## Dữ liệu và cơ chế Agent

- Backend lấy 30 giá trị từ bản ghi lịch sử, xác thực mã phiên sở hữu và chỉ số mẫu trước khi gọi AI. Không lấy ca do LLM tự chỉ định.
- Đọc ca và đo độ nhạy là bước bắt buộc. Agent được phép tự gọi lại `read_case`, `explain_model` và `search_guidelines` trong vòng lặp tối đa 5 lần gọi Responses API. Đây là vòng lặp sử dụng công cụ, không chỉ ghép prompt chat.
- RAG cục bộ: chia văn bản có chồng lấn, lập chỉ mục TF-IDF ký tự, mở rộng một số thuật ngữ Việt–Anh và tìm top 5 đoạn. Đây là truy xuất từ khóa gần đúng, **chưa phải semantic embedding hay bộ kiểm định y khoa**. Ngưỡng tương đồng 0.06 chỉ là heuristic, không chứng minh độ liên quan; cần kiểm tra đoạn trích thực tế.
- Model có thể dịch/chỉnh truy vấn tiếng Anh và tìm tiếp. Phần trả lời dùng JSON schema; backend kiểm tra mã nguồn tồn tại và khớp mã trích dẫn trong câu trả lời. Kiểm tra này không tự chứng minh mọi phát biểu được nguồn hỗ trợ: người dùng cần đối chiếu.
- Độ nhạy: thay từng đặc trưng bằng trung vị nhóm lành của dataset dự án rồi chạy lại mô hình. Không phải SHAP, không phải ảnh hưởng nhân quả; các giá trị tương quan có thể tạo tổ hợp phi thực tế. Tương quan Pearson là thống kê dataset, không phải tương quan trong riêng một bệnh nhân. Tập tham chiếu có thể chứa cả các dòng huấn luyện và kiểm thử; đây không phải phép đánh giá độ chính xác.
- WDBC mô tả nhân tế bào từ ảnh FNA. Bán kính nhân không phải kích thước u. Không thể xác định TNM, ER/PR/HER2 hoặc chọn phác đồ từ 30 đặc trưng này.

## Tài liệu RAG

`--nci` tải nội dung từ ba trang chính thức và ghi thời điểm lấy nội dung:

- https://www.cancer.gov/types/breast/hp/breast-treatment-pdq
- https://www.cancer.gov/types/breast/diagnosis/breast-cancer-biomarker-tests
- https://archive.ics.uci.edu/dataset/17/breast-cancer-wisconsin-diagnostic

NCI PDQ là tài liệu tham khảo, không phải phác đồ Bộ Y tế/NCCN. Gói cài **không chứa hoặc giả lập tài liệu Bộ Y tế/NCCN**. HTML có thể thay đổi; nếu tải thất bại hoặc trích xuất sai, sửa bộ nạp và kiểm tra trước sử dụng. Chạy lại lệnh để cập nhật bản chụp tài liệu; không tự cập nhật nền. Kiểm tra `breastcare_agent/corpus.json` để xem văn bản thực sự được lập chỉ mục.

Để thêm PDF được phép sử dụng, sao chép `pdf_manifest.example.json` thành `pdf_manifest.json`, điền đường dẫn PDF, tên, nguồn, phiên bản thật, sau đó chạy:

```powershell
python -m breastcare_agent.ingest --manifest pdf_manifest.json
```

Đường dẫn PDF tính từ thư mục chứa manifest. PDF ảnh cần OCR và rà soát trước. Số trang hiển thị là số trang PDF (bắt đầu từ 1), có thể khác số trang in trên tài liệu. Bảng biểu trong PDF có thể bị mất cấu trúc khi trích xuất; đối chiếu bản gốc trước khi dùng thông tin điều trị. Không nhập tài liệu không rõ nguồn. Chạy lại cùng nguồn sẽ thay các đoạn của nguồn cũ. Nên khởi động lại backend sau khi cập nhật corpus.

## Bảo mật và phạm vi

Giao diện tắt gửi dữ liệu mặc định sau mỗi lần tải lại; khi bật, 30 giá trị, kết quả, độ nhạy, đoạn tài liệu truy xuất và lịch sử hỏi đáp ngắn được gửi tới OpenAI. Không gửi API key xuống frontend. `store=False` được đặt cho Responses API; đây không phải cam kết không lưu trữ ở nhà cung cấp. Không nhập dữ liệu định danh. Bộ nạp tài liệu chạy cục bộ; chỉ đoạn truy xuất được gửi khi hỏi AI.

Trò chuyện lưu trong RAM tối đa 64 ca, 4 lượt hỏi đáp mỗi ca, hết hạn 20 phút. Không lưu hội thoại bền vững. Mã phiên hiện có là cơ chế của bản demo, không thay thế đăng nhập phân quyền: trước khi triển khai cho bệnh nhân thật cần xác thực tài khoản, quản lý đồng ý, chính sách lưu trữ và đánh giá lâm sàng. Giới hạn 1 yêu cầu đang chạy và 12 câu/phút áp dụng cho một tiến trình backend; nhiều worker cần bộ giới hạn dùng chung.

Agent không tự kê thuốc, chọn phác đồ cá nhân hoặc xác nhận chẩn đoán. Hiển thị số liệu công cụ và nguồn, không hiển thị chuỗi suy nghĩ nội bộ.

## Kiểm tra và khôi phục

Sau cài: `/api/agent/status` phải có `configured:true` sau khi có khóa và corpus. Thử một ca ác tính, mở 30 chỉ số độ nhạy, kiểm tra nguồn, hỏi tiếp, đổi ca và kiểm tra lịch sử không lẫn ca. Thử tắt Agent để chắc chắn không phát sinh yêu cầu tự động mới. Thử nhập mã lịch sử của phiên khác: API phải từ chối.

Installer sao lưu tất cả file ghi đè vào `agent_backup_<thời gian>` cùng `manifest.json`; các chỉnh sửa giao diện trước đó được giữ. Cài lại không thay `.env`, corpus hoặc mô hình. Muốn khôi phục: dừng server, chép các file đã tồn tại từ bản sao lưu về đường dẫn tương ứng; các file `existed:false` trong manifest là file do lần cài đó tạo, có thể bỏ sau khi khôi phục frontend/backend. Không dùng bản sao lưu cũ nếu bạn đã sửa mã thêm sau khi cài.

Bản phát hành được kiểm tra cục bộ bằng mô hình/dữ liệu thử và API AI giả lập. Cần kiểm thử API OpenAI thực tế, tài liệu thực và giao diện trong dự án của bạn sau cấu hình; chưa xác nhận chất lượng câu trả lời y khoa.

Có thể chạy kiểm tra logic sau khi cài: `python -m unittest test_breastcare_agent -v`. Các kiểm tra này gọi trực tiếp hàm xử lý endpoint với SDK giả lập, không xác nhận HTTP/CORS hoặc chất lượng đầu ra AI thật. Môi trường xây dựng không tải được gói npm nên chưa kiểm tra build React hoặc bố cục bằng trình duyệt.
