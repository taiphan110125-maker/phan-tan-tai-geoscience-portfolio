# PROJECT_HANDOVER — Phan Tấn Tài · Geology & Geophysics Portfolio

Tài liệu bàn giao, cập nhật **28/10/2026**. Đây là điểm vào; chi tiết nằm trong thư mục [`docs/`](docs/).

| Thành phần | Giá trị |
| --- | --- |
| Repository | `taiphan110125-maker/phan-tan-tai-geoscience-portfolio` (công khai, nhánh mặc định `main`) |
| Website | https://phan-tan-tai-geoscience-portfolio.onrender.com |
| Hosting | Render Static Site, service `srv-datbm7qd0e5s73betpbg`, tự deploy mỗi commit lên `main`, phía trước là Cloudflare CDN |
| Backend | Supabase project `aqkasetqystwvpassidd` (Postgres 17, Singapore), 11 bảng, 4 bucket, 3 Edge Functions |
| Frontend | HTML + CSS + JavaScript thuần, không có bước build; supabase-js `2.117.2` từ jsDelivr |
| Lịch sử Git | 234 commit (29/09/2026 → 15/10/2026), một tác giả, phần lớn sửa trực tiếp trên GitHub |

> Repository là **công khai**, nên các tài liệu này không chứa khóa bí mật, dữ liệu cá nhân hay chi tiết khai thác lỗ hổng. Báo cáo kiểm tra bảo mật chi tiết được lưu riêng, không đưa vào repo.

## Bộ tài liệu

| File | Nội dung |
| --- | --- |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Kiến trúc, liên kết giữa các trang và module, luồng dữ liệu, service worker, đa ngôn ngữ |
| [docs/DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md) | Bảng, cột, ràng buộc, Storage, Edge Functions, Realtime, quyền truy cập đã kiểm chứng |
| [docs/FEATURE_INVENTORY.md](docs/FEATURE_INVENTORY.md) | Danh sách chức năng trang công khai và trang quản trị, trạng thái từng chức năng |
| [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) | Quy trình nhánh → PR → kiểm thử → deploy, quy tắc cache, khôi phục |
| [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md) | Lỗi và rủi ro theo mức ưu tiên |
| [docs/DEVELOPMENT_ROADMAP.md](docs/DEVELOPMENT_ROADMAP.md) | Kế hoạch tối ưu và phát triển |

## Trạng thái tiếp nhận

| Hạng mục | Trạng thái | Cách xác minh |
| --- | --- | --- |
| Mã nguồn `main` (10 file văn bản, 18 ảnh) | Đã đọc toàn bộ | Đọc trực tiếp; kiểm tra cú pháp 13 khối JavaScript |
| Lịch sử Git | Đã đọc | 234 commit; không phát hiện khóa bí mật trong toàn bộ lịch sử |
| Production khớp `main` | **Đã xác minh** | SHA-256 của 10 file phục vụ trên Render trùng với commit `50e6748` |
| Trang công khai trên production | Đã kiểm tra | Tải trang, đo thời gian, đọc console và request trong trình duyệt |
| Quyền đọc của khách (anon) trên Supabase | Đã kiểm tra | Truy vấn đọc bằng publishable key, không ghi dữ liệu |
| Lược đồ, RLS, trigger, index, Storage, Realtime của Supabase | **Đã xác minh** | Connector Supabase (OAuth), chỉ đọc metadata |
| Mã nguồn 3 Edge Functions | **Đã đọc** | Connector Supabase; bản sao chưa có trong repo |
| Cấu hình, lịch sử deploy Render | **Đã xác minh** | Connector Render (OAuth), chỉ đọc |
| Trang quản trị và các luồng có đăng nhập | **Đã kiểm thử** với backend giả lập | `tests/e2e_mock_test.py` (PR #3): 170/170 đạt, VI/EN/FR, desktop và mobile; phát hiện và sửa 1 lỗi |
| Log production 24 giờ (Supabase) | Đã đọc | Không có lỗi 5xx, không có lỗi từ Edge Functions |
| Đăng ký, đăng nhập, gửi nhận xét/thảo luận/liên hệ trên production thật | Chưa thử | Không ghi dữ liệu thật khi chưa được phép |

## Quyền truy cập

GitHub (quyền ghi qua ứng dụng Claude), Supabase và Render đã kết nối qua OAuth ngày 28/10/2026. Không gửi `service_role`, `sb_secret`, access token hay mật khẩu vào cuộc trò chuyện.

Để kiểm thử các luồng có đăng nhập (trang quản trị, nhận xét riêng) mà không chạm dữ liệu thật, cần một tài khoản thử riêng hoặc một nhánh Supabase thử nghiệm.

## Nguyên tắc làm việc

- Mỗi thay đổi một nhánh và một Pull Request; không merge `main` khi chưa được chủ website duyệt.
- Không sửa schema, RLS, dữ liệu production hoặc deploy khi chưa được chấp thuận.
- Nội dung nghiên cứu do tác giả viết không bị dịch hay chỉnh sửa tự động.
