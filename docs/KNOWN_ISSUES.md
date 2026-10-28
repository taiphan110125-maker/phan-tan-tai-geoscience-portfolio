# Lỗi và rủi ro đã biết

Cập nhật 28/10/2026. Mức ưu tiên: **P1** xử lý trước mọi phát triển mới · **P2** trong đợt nâng cấp kế tiếp · **P3** dọn dẹp.

> Repository công khai, nên các mục bảo mật chỉ ghi ở mức hướng xử lý. Chi tiết kỹ thuật được lưu trong báo cáo riêng của chủ website.
>
> Kiểm toán Supabase (28/10/2026, chỉ đọc) xác nhận: RLS bật trên mọi bảng; người dùng **không** tự nâng quyền admin được; nhận xét riêng chỉ người gửi và admin đọc được; 3 Edge Functions đều kiểm tra origin, giới hạn tần suất và (với chức năng quản trị) kiểm tra quyền admin phía server.

## P1

| ID | Vấn đề | Ảnh hưởng | Trạng thái |
| --- | --- | --- | --- |
| I-01 | Form Liên hệ (Chủ đề) và Nhận xét riêng (Vai trò) ghi **nhãn đã dịch** vào database khi người dùng chọn English/Français | Dữ liệu trộn ngôn ngữ trong admin | **Đã sửa** (PR #2, đã deploy). Dữ liệu cũ không bị ảnh hưởng |
| S-01 | Quy tắc gán quyền admin tự động khi tạo tài khoản kết hợp với đăng ký không xác nhận email: an toàn khi tài khoản chủ website còn tồn tại, nhưng cần làm chặt hơn | Quyền quản trị | **Đã sửa** 28/10/2026 (migration `security_hardening_20261028`): tài khoản mới luôn là `user`; admin mới chỉ cấp bằng SQL thủ công |
| S-03 | Policy Storage cho phép khách liệt kê tên file trong 4 bucket công khai (mở file theo URL không cần quyền này) | Lộ danh sách file, kể cả file của bài đã xóa mềm | **Đã sửa** 28/10/2026 (PR #5 + migration): khách không liệt kê được; file vẫn mở bằng URL công khai |
| P-01 | supabase-js (55 KB nén) tải **đồng bộ** từ jsDelivr, chặn toàn bộ script phía sau | Trang không tương tác được và hiện tiếng Việt cho tới khi thư viện tải xong; nếu CDN chậm hoặc bị chặn, chờ tới khi lỗi | **Đã sửa** (PR #7): supabase-js tự host trong `assets/vendor/`, service worker lưu sẵn, không còn phụ thuộc CDN ngoài |
| L-01 | Khi chọn EN/FR, trang luôn hiện tiếng Việt trước rồi mới dịch (do P-01 và cơ chế dịch sau khi vẽ) | Mỗi lần tải lại trông như tải hai lần | **Đã sửa** (PR #7): ẩn trang tới khi bản dịch áp dụng (tối đa 2,5 giây); kiểm thử `tests/first_paint_test.py` |

## P2

| ID | Vấn đề | Ảnh hưởng |
| --- | --- | --- |
| L-02 | Còn 45 chuỗi tiếng Việt ở trang chủ khi chọn EN/FR: chuỗi ghép động ("1 bài", "4 kết quả phù hợp", "Bài 1"…), 20 nhãn `aria-label`, `<title>`, meta, ngày giờ `vi-VN`, thông báo lỗi đăng nhập/đăng ký, lời chào trợ lý ảo | Trộn ngôn ngữ |
| L-03 | `assignment-viewer.html` (17 chuỗi) và `admin-login.html` (10 chuỗi) gần như chưa dịch, không có bộ chọn ngôn ngữ | Trộn ngôn ngữ |
| L-04 | Dịch bằng so khớp nguyên chuỗi: sửa một dấu câu trong HTML là mất bản dịch | Dễ vỡ khi bảo trì |
| L-05 | Thuật ngữ nên chỉnh: "Đánh giá tầng chứa" → *Formation Evaluation* / *Évaluation des formations*; "Đánh giá thông số tầng chứa" → *Petrophysical Evaluation* / *Évaluation pétrophysique*; "Seismics" → *Seismic Methods* / *Méthodes sismiques*; "Resistivity" → *Electrical Resistivity Methods* / *Méthodes électriques* | Độ chính xác chuyên môn |
| P-02 | Ảnh hero 1672×941 px, 326 KB, dùng cho cả điện thoại (không `srcset`) | Lần tải đầu chậm trên 4G |
| P-03 | 30 khối `<style>` (~2.200 dòng) inline trong `index.html` (195 KB, 44 KB nén) | Không cache riêng; khó bảo trì |
| P-04 | Mỗi lượt xem: 5–6 request Supabase + 1 kết nối Realtime theo dõi 5 bảng | Tốn kết nối đồng thời của gói Free |
| P-05 | Danh sách dự án/bài tập bị vẽ lại toàn bộ mỗi lần dữ liệu về, kể cả khi không đổi | Ảnh nhấp nháy |
| P-06 | 18 khai báo `backdrop-filter: blur()` | Cuộn kém mượt trên điện thoại tầm trung |
| P-07 | Cloudflare trả `max-age=0` cho cả ảnh và JS | Trình duyệt chưa có service worker kiểm tra lại mọi file mỗi lần |
| D-01 | Phông Be Vietnam Pro và Source Serif 4 khai báo nhưng không được tải | Chữ hiển thị khác nhau giữa Windows, macOS, Android |
| S-04 | Chưa có header `Content-Security-Policy`, `frame-ancestors`/`X-Frame-Options`; supabase-js từ CDN không có kiểm tra toàn vẹn (SRI) | Giảm lớp phòng vệ |
| S-05 | Chống spam cho thảo luận công khai và form liên hệ chỉ có ở trình duyệt (đăng ký và trợ lý ảo đã có giới hạn phía server) | Có thể bị gửi hàng loạt — **Đã sửa** 28/10/2026: trigger giới hạn theo IP (thảo luận 5 tin/phút, 30 tin/giờ; liên hệ 3 lần/10 phút, 10 lần/ngày), chặn nội dung trùng trong 10 phút; IP chỉ lưu dạng băm |
| S-06 | Tắt "Leaked Password Protection" của Supabase Auth (cảnh báo của Supabase Advisor) | Người dùng đặt được mật khẩu đã bị lộ — tính năng chỉ có từ gói Pro; dự án đang dùng gói Free |
| S-07 | Quyền bảng (GRANT) cho `anon`/`authenticated` ở mức mặc định rộng | Giảm lớp phòng vệ — **Một phần đã sửa** 28/10/2026: thu hồi TRUNCATE, TRIGGER, REFERENCES; SELECT/INSERT/UPDATE/DELETE vẫn do RLS chặn |
| D-03 | Thêm môn học trong admin: lưu được nhưng danh sách không cập nhật, form không xóa (`event.currentTarget` dùng sau `await`) | Dễ bấm lại, báo trùng | **Đã sửa** (PR #3, đã deploy) |
| D-02 | Bảng `comments` không có policy UPDATE, nên khi admin sửa bài tập, thông tin bài tập lưu kèm nhận xét không được cập nhật (lỗi bị bỏ qua) | Nhận xét cũ hiện tiêu đề/ngày cũ — **Đã sửa** 28/10/2026: thêm policy `comments_admin_update` |
| L-06 | Trợ lý ảo (`geo-ai`) luôn trả lời tiếng Việt và từ chối câu hỏi ngoài phạm vi bằng tiếng Việt | Trộn ngôn ngữ ở EN/FR |
| C-01 | Service worker trả HTML đã cache khi mạng chậm hơn 1,2 s; trang xem tài liệu cache riêng mỗi `?id=`, không giới hạn | Có thể thấy bản cũ sau deploy; cache phình dần |

## P3

| ID | Vấn đề |
| --- | --- |
| Q-01 | `public-content.json` tạo ngày 01/10/2026, chỉ có 3/9 bài tập; ở chế độ dự phòng, ảnh dự án hiện ảnh mặc định |
| Q-02 | Hàm tạo slug bỏ chữ "Đ" hoa (`ia-vat-ly-ung-dung`); tên file mất chữ "đ" (`admin.html`, `subjectSlug`, `safeName`). Slug cũ giữ nguyên để không làm hỏng dữ liệu |
| Q-03 | 10 ảnh không dùng trong `assets/` (~127 KB) |
| Q-04 | Mã lặp giữa các trang: cấu hình Supabase (4 nơi), `escapeHtml`, `sanitizeRichHtml` (3 nơi) |
| Q-05 | Mã thừa: `academicExchanges`, `commentCount` ở trang công khai, `BroadcastChannel('ptt-content-sync')` không có nơi nghe; theo dõi Realtime `assignment_subjects` dù bảng không được phát; cột `assignments.day_number` không còn dùng |
| Q-08 | Ràng buộc độ dài trùng lặp trên `comments`, `messages`, `academic_chat_messages`; 26 migration và mã 3 Edge Functions chưa có trong repository |
| Q-06 | Ô lọc môn học trong HTML khai báo cứng 3 môn, bị ghi đè khi dữ liệu về |
| Q-07 | Trình soạn rich-text của admin dùng `document.execCommand` (API đã lỗi thời nhưng còn chạy) |

## Nội dung chờ chủ website quyết định

Không tự sửa dữ liệu nghiên cứu. Các điểm phát hiện: thẻ dự án "trãi nghiệm" (đúng: "trải nghiệm"); Đồ án 1 ghi "Bể Z" ở Mục tiêu nhưng "Bể Cửu Long" ở Sản phẩm, câu Sản phẩm dừng ở chữ "theo"; loại dự án "Thực Địa" viết hoa không thống nhất.
