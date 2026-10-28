# Kế hoạch phát triển

Mỗi bước là một nhánh và một Pull Request riêng, có kiểm thử và cách hoàn tác (xem [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)). Mã lỗi tham chiếu [KNOWN_ISSUES.md](KNOWN_ISSUES.md).

## Giai đoạn 0 — Nền tảng (Supabase, Render đã kết nối; còn thiếu quyền ghi GitHub)

| PR / việc | Nội dung | Giải quyết |
| --- | --- | --- |
| 0.1 | Gắn tag `baseline-2026-10-28`; merge bộ tài liệu này | — |
| 0.2 | Lưu 26 migration và mã 3 Edge Functions vào `supabase/` (chỉ lưu, không áp dụng) | Q-08 |
| 0.3 | Bật Pull Request Previews trên Render | Kiểm thử trước khi merge |
| 0.4 | Migration bảo mật (mỗi mục có script áp dụng + hoàn tác, thử trên nhánh/dự án Supabase riêng, chờ duyệt): bỏ quyền liệt kê Storage, làm chặt quy tắc gán admin, thêm policy UPDATE cho metadata `comments`, thu hẹp GRANT, bật Leaked Password Protection | S-01, S-03, S-06, S-07, D-02 |
| 0.5 | Giới hạn tần suất phía server cho thảo luận công khai và form liên hệ | S-05 |

## Giai đoạn 1 — Sửa lỗi và tốc độ (chỉ frontend)

| PR | Nội dung | Giải quyết | Kiểm thử |
| --- | --- | --- | --- |
| **1** | Giá trị form độc lập với ngôn ngữ — **đã xong, chờ duyệt** | I-01 | `tests/form_values_test.py` (112 kiểm tra) |
| 2 | Tải supabase-js không chặn trang (tự host trong `assets/vendor/` + `defer`); áp ngôn ngữ trước lần vẽ đầu bằng script nhỏ trong `<head>` | P-01, L-01 | Ảnh chụp tại 0,5 s ở EN/FR không còn tiếng Việt; thời gian DOMContentLoaded |
| 3 | Chỉ vẽ lại danh sách khi dữ liệu đổi; Realtime chỉ mở khi người xem ở mục Bài tập | P-04, P-05 | Đếm số lần vẽ và số request |
| 4 | Ảnh hero 3 kích thước (`srcset`, ~60/150/326 KB); xóa 10 ảnh không dùng | P-02, Q-03 | Lighthouse mobile trước/sau |

## Giai đoạn 2 — Đa ngôn ngữ hoàn chỉnh

| PR | Nội dung | Giải quyết |
| --- | --- | --- |
| 5 | Chuyển sang khóa dịch (`data-i18n`, hàm `t(key, {n})`) cho chuỗi động, `aria-label`, `<title>`, meta; ngày giờ bằng `Intl.DateTimeFormat` theo ngôn ngữ | L-02, L-04 |
| 6 | Bộ chọn ngôn ngữ cho trang xem tài liệu; dịch trang đăng nhập quản trị | L-03 |
| 7 | Rà soát thuật ngữ chuyên ngành với chủ website | L-05 |
| 8 | Truyền ngôn ngữ cho `geo-ai` và trả lời theo ngôn ngữ đó (sửa Edge Function, triển khai sau khi duyệt) | L-06 |

Kiểm thử chung: script quét tự động phải cho **0 chuỗi tiếng Việt** ở giao diện EN/FR (trừ nội dung tác giả).

## Giai đoạn 3 — Giao diện và bảo trì

| PR | Nội dung | Giải quyết |
| --- | --- | --- |
| 9 | Tự host phông (WOFF2, subset Latin + Vietnamese); gộp CSS vào `assets/site.css` có phiên bản, giữ nguyên giao diện (so ảnh chụp trước/sau ở 390 và 1440 px) | D-01, P-03 |
| 10 | Giảm `backdrop-filter` trên điện thoại; hiệu ứng xuất hiện không ẩn nội dung khi tải lại giữa trang | P-06 |
| 11 | Service worker v24: không trả HTML cũ quá hạn sau deploy, giới hạn số trang xem tài liệu trong cache, thông báo "Có bản mới" | C-01 |
| 12 | Header bảo mật và cache trên Render (CSP, `frame-ancestors`, `Referrer-Policy`, `Cache-Control` dài hạn cho file có phiên bản) | S-04, P-07 |
| 13 | Gom cấu hình Supabase và hàm dùng chung vào `assets/common.js`; xóa mã thừa; sửa hàm tạo slug cho dữ liệu mới | Q-02, Q-04, Q-05, Q-06 |

## Giai đoạn 4 — Chức năng mới (cần chủ website chọn)

- Trạng thái nháp cho dự án và bài tập (dùng cột `published` sẵn có).
- Sắp xếp thủ công thứ tự dự án.
- Tự tạo `public-content.json` khi admin lưu thay đổi (Q-01).
- Kiểm thử tự động đầy đủ cho các luồng chính (đăng nhập thử, admin) chạy trên dự án Supabase thử nghiệm.
