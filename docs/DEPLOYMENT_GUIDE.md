# Triển khai và khôi phục

## Hiện trạng

Đã xác minh qua connector Render ngày 28/10/2026:

| Thiết lập | Giá trị |
| --- | --- |
| Service | `srv-datbm7qd0e5s73betpbg` (Static Site), tạo 28/09/2026 |
| Repository / nhánh | `taiphan110125-maker/phan-tan-tai-geoscience-portfolio` / `main` |
| Tự động deploy | Cấu hình ghi **bật**, nhưng **thực tế không chạy**: ngày 28/10/2026, merge PR #1–#3 vào `main` không tạo deploy nào. Mọi deploy trong lịch sử đều kích hoạt qua API/thủ công (`trigger: api`) |
| Build command | `echo ready` (không build) |
| Publish directory | `.` (toàn bộ thư mục gốc) |
| Pull Request Previews | **Tắt** |
| Tên miền | Chỉ `phan-tan-tai-geoscience-portfolio.onrender.com` |
| IP được phép | Mọi nơi |
| Bản đang chạy | Deploy `dep-db8ef5ss728c7394t54g`, commit `50e6748` (15/10/2026); trùng byte với `main` |
| Lịch sử | Mọi build/deploy từ 30/09 đến 15/10/2026 đều thành công; không có sự cố máy chủ |

- Cloudflare đứng trước và cache file tối đa 300 giây (`s-maxage=300`).
- Header tùy chỉnh, rewrite/redirect và biến môi trường: connector không trả về; trang không cần biến môi trường vì không có bước build.
- Merge vào `main` **chưa** đưa thay đổi lên website. Phải deploy thủ công: Render Dashboard › service › **Manual Deploy › Deploy latest commit**.
- Nguyên nhân có thể: Render chưa được cấp quyền GitHub cho repository (repo được nối bằng URL công khai). Muốn tự deploy: Render › Account Settings › GitHub › cấp quyền cho repository này, rồi kiểm tra lại bằng một commit nhỏ.
- Sau khi bật được tự deploy, mọi commit lên `main` sẽ lên production ngay; chỉ merge khi đã duyệt.
- Toàn bộ thư mục gốc được phát công khai, kể cả `README.md` và thư mục `docs/`. Không đặt thông tin bí mật vào repository.

## Quy trình đề xuất

```
main ──► nhánh mới (fix/… · feat/… · docs/…) ──► commit ──► Pull Request
          ──► kiểm thử tự động + kiểm tra thủ công ──► Render Preview (đang tắt, nên bật)
          ──► chủ website duyệt ──► merge vào main ──► Render deploy ──► kiểm tra sau deploy
```

1. **Tạo nhánh** từ `main` mới nhất: `git switch main && git pull && git switch -c fix/<tên-ngắn>`.
2. **Mỗi PR một mục tiêu**, mô tả: thay đổi gì, vì sao, cách kiểm tra, cách hoàn tác.
3. **Kiểm thử trước khi mở PR:**
   - Cú pháp JavaScript: trích từng khối `<script>` và chạy `node --check`.
   - `python tests/form_values_test.py` (khi đã có trên `main`): giá trị form ở VI/EN/FR, không ghi dữ liệu thật.
   - Mở trang ở 390 px và 1440 px: không tràn ngang, không lỗi console.
4. **Không merge** khi chưa có phê duyệt của chủ website.
5. **Sau deploy:** tải lại trang chủ, mở một bài tập, mở một dự án, đổi ngôn ngữ, xem console. Với thay đổi liên quan đến tài khoản: đăng nhập thử bằng tài khoản thường.

## Quy tắc cache khi sửa file

| Sửa file | Việc bắt buộc |
| --- | --- |
| File được tham chiếu kèm `?v=` (ví dụ `assets/site-language.js`, `hero-user.webp`) | Đổi giá trị `?v=` ở **mọi** trang tham chiếu; service worker không bao giờ làm mới file có `?v=` cũ |
| `sw.js` | Đổi `CACHE_NAME` (ví dụ `ptt-static-v24-YYYYMMDD`) và `?v=` khi đăng ký trong `index.html` |
| File HTML | Không cần; service worker lấy HTML từ mạng trước. Lưu ý mạng chậm hơn 1,2 s có thể thấy bản cũ ở một lần tải |
| `public-content.json` | Không cần; tạo lại khi nội dung trên Supabase thay đổi nhiều |

## Thay đổi Supabase

- Mọi thay đổi schema, RLS, policy Storage hoặc Edge Function phải có: script áp dụng, script hoàn tác, và kiểm tra trên một dự án Supabase thử nghiệm trước.
- Trước khi sửa dữ liệu production: sao lưu bảng liên quan (`create table <bảng>_backup_<ngày> as select * from <bảng>;`) và chỉ thực hiện khi chủ website đồng ý.

## Khôi phục

| Tình huống | Cách khôi phục | Thời gian |
| --- | --- | --- |
| PR vừa merge gây lỗi | `git revert <commit>` → push `main` → Manual Deploy trên Render | Vài phút |
| Cần quay lại ngay, chưa kịp sửa mã | Render Dashboard › service › Deploys › chọn bản deploy trước › **Rollback** | Dưới 1 phút |
| Người dùng vẫn thấy bản cũ sau khi khôi phục | Tăng `CACHE_NAME` trong `sw.js`; Cloudflare tự hết hạn sau 300 s | Một lần tải lại |
| Service worker gây lỗi nghiêm trọng | Deploy một `sw.js` chỉ gồm: `self.addEventListener('install',()=>self.skipWaiting()); self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(k=>Promise.all(k.map(c=>caches.delete(c)))).then(()=>self.registration.unregister())));` | Lần tải kế tiếp |
| Migration Supabase lỗi | Chạy script hoàn tác đi kèm migration; khôi phục từ bảng sao lưu | Tùy thay đổi |

**Mốc an toàn hiện tại:** commit `50e6748` trên `main` (bản đang chạy). Khi có quyền ghi GitHub, gắn tag `baseline-2026-10-28` vào commit này.
