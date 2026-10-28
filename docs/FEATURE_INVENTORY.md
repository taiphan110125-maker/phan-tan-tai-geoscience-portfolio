# Danh sách chức năng

Trạng thái: **Hoạt động** = đã thấy chạy trên production hoặc qua kiểm thử tự động; **Theo mã** = đọc mã, chưa chạy thử với tài khoản thật; **Một phần** = có lỗi hoặc thiếu đã biết (xem [KNOWN_ISSUES.md](KNOWN_ISSUES.md)).

Các mục "Theo mã" dưới đây đã chạy đạt trong kiểm thử đầu-cuối với backend giả lập (`tests/e2e_mock_test.py`, PR #3); chưa thử trên production thật để không ghi dữ liệu.

## Trang công khai (`index.html`, `assignment-viewer.html`)

| # | Chức năng | Mô tả | Dữ liệu | Trạng thái |
| --- | --- | --- | --- | --- |
| 1 | Trang chủ | Ảnh nền, tiêu đề, thẻ chuyên môn, khối "Hồ sơ nhanh" | Tĩnh | Hoạt động |
| 2 | Nội dung học thuật | 3 thẻ dẫn tới Dự án, Bài tập, Trợ lý ảo | Tĩnh | Hoạt động |
| 3 | Giới thiệu | Ảnh (đổi từ admin), đoạn giới thiệu, số dự án và bài tập | `site_settings`, đếm từ dữ liệu | Hoạt động |
| 4 | Dự án nghiên cứu | Lưới thẻ dự án; cửa sổ chi tiết: tóm tắt, thẻ, Mục tiêu, Dữ liệu, Phương pháp, Sản phẩm, danh sách báo cáo | `projects`, bucket `project-reports` | Hoạt động (2 dự án) |
| 5 | Bài tập & tài liệu | Nhóm theo ngày học, đánh số "Bài n" theo ngày, lọc môn học, tìm kiếm | `assignments`, `assignment_subjects` | Hoạt động (9 bài) |
| 6 | Xem tài liệu | PDF, Word/PowerPoint/Excel (Office Online), nội dung rich-text, liên kết ngoài; nút tải file | `assignments`, bucket `assignments` | Hoạt động |
| 7 | Nhận xét riêng tư | Cần đăng nhập; chỉ người gửi và admin xem; hiển thị lịch sử nhận xét của chính mình | `comments` | Theo mã |
| 8 | Thảo luận học thuật công khai | Khách gửi được; cập nhật realtime; tải khi cuộn tới | `academic_chat_messages` | Theo mã (hiện chưa có tin nào) |
| 9 | Liên hệ | Họ tên, email, chủ đề, nội dung; honeypot + giới hạn 10 s phía trình duyệt | `messages` | Theo mã |
| 10 | Trợ lý ảo | Nút nổi + bảng chat; câu hỏi nhanh; dự phòng trả lời cục bộ khi function lỗi | Edge Function `geo-ai` | Theo mã |
| 11 | Tìm kiếm toàn trang | Ctrl/⌘ K; tìm dự án, bài tập, môn học, các mục; bỏ dấu tiếng Việt | Dữ liệu đã tải | Hoạt động |
| 12 | Đăng ký | Họ tên, email, mật khẩu ≥ 8 ký tự; không cần xác nhận email; tự đăng nhập | Edge Function `signup-no-confirm` | Theo mã |
| 13 | Đăng nhập / đăng xuất | Email + mật khẩu; menu tài khoản | Supabase Auth | Theo mã |
| 14 | Chọn ngôn ngữ | Tiếng Việt, English, Français; lưu lựa chọn | `localStorage` | Một phần |
| 15 | Giao diện điện thoại | Menu thu gọn ≤ 980 px, bố cục ≤ 700 px; không tràn ngang ở 390 px | — | Hoạt động |
| 16 | Hoạt động khi mạng kém | Cache `localStorage` 10 phút, snapshot dự phòng, service worker | — | Hoạt động (snapshot đã cũ) |

## Trang quản trị (`admin-login.html`, `admin.html`)

| # | Mục | Chức năng | Trạng thái |
| --- | --- | --- | --- |
| A1 | Đăng nhập quản trị | Email + mật khẩu; từ chối và đăng xuất nếu `profiles.role ≠ admin`; tự chuyển trang nếu đã đăng nhập | Theo mã |
| A2 | Tổng quan | Số liệu, bài tập gần đây, nhận xét mới | Theo mã |
| A3 | Bài tập | Thêm nhiều file cùng lúc (≤ 50 MB/file) hoặc bài không file; nội dung rich-text; liên kết ngoài (chỉ `http/https`); đổi ngày/môn ngay trên danh sách; tự đánh lại số bài; mở file; tải lại file; sửa; chuyển vào Thùng rác | Theo mã |
| A4 | Môn học | Thêm, đổi tên, ẩn/hiện, xóa | Một phần (D-03, đã sửa ở PR #3) |
| A5 | Dự án | Thêm/sửa; ảnh tự nén WebP ≤ 1600 px; nhiều file báo cáo; thẻ (≤ 8); chuyển vào Thùng rác | Theo mã |
| A6 | Ảnh giới thiệu | Đổi ảnh mục Giới thiệu (≤ 8 MB), xóa ảnh cũ | Theo mã |
| A7 | Phản hồi | Xem và xóa nhận xét riêng, tin thảo luận công khai; huy hiệu chưa đọc; thông báo realtime | Theo mã |
| A8 | Lời nhắn | Xem và xóa lời nhắn liên hệ; huy hiệu chưa đọc | Theo mã |
| A9 | Tài khoản | Danh sách người dùng, xác nhận email, xóa tài khoản (tài khoản admin được bảo vệ) | Theo mã |
| A10 | Thùng rác | Khôi phục hoặc xóa vĩnh viễn bài tập/dự án (kèm file và nhận xét) | Theo mã |
| A11 | Bảo mật | Trang thông tin tĩnh, không có chức năng | Theo mã |

## Chức năng còn thiếu hoặc chưa hoàn thiện

- Không có trạng thái nháp: mọi dự án và bài tập lưu ra đều `published = true`, dù cột `published` có tồn tại.
- Không có sắp xếp thủ công dự án trong admin (`sort_order` chỉ gán khi tạo).
- Số nhận xét theo bài tập (`commentCount`) có trong admin nhưng luôn bằng 0 ở trang công khai.
- Trợ lý ảo không biết ngôn ngữ người dùng đang chọn.
- `public-content.json` phải tạo thủ công; hiện chỉ có 3/9 bài tập.
- Trang xem tài liệu và đăng nhập quản trị không có bộ chọn ngôn ngữ.
