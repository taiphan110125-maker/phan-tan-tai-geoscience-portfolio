"""Kiểm thử đầu-cuối các luồng có đăng nhập, chạy với backend Supabase giả lập.

Bao phủ:
- Trang quản trị: đăng nhập (admin và tài khoản thường bị từ chối), 9 mục,
  môn học, bài tập (thêm có file / không file, sửa, đổi môn, thùng rác,
  khôi phục, xóa vĩnh viễn), dự án (thêm có ảnh và báo cáo, thùng rác,
  khôi phục, xóa vĩnh viễn), ảnh giới thiệu, phản hồi, lời nhắn, tài khoản,
  đăng xuất.
- Trang công khai: đăng ký, đăng xuất, đăng nhập sai/đúng, nhận xét riêng,
  thảo luận công khai, liên hệ, trợ lý ảo (backend và chế độ dự phòng).
- Trang xem tài liệu.
Mỗi luồng chạy trên desktop (1440 px) và điện thoại (390 px); kiểm tra lỗi
JavaScript và tràn ngang.

Không ghi dữ liệu thật: mọi request tới *.supabase.co được tests/fake_supabase.py
trả lời trong trình duyệt; WebSocket Realtime được giả lập. Mật khẩu dùng
trong kiểm thử được sinh ngẫu nhiên mỗi lần chạy.

Chạy từ thư mục gốc repository:
    python tests/e2e_mock_test.py
Tùy chọn: SUPABASE_JS_PATH=/duong/dan/supabase.js (dùng supabase-js cục bộ).
"""
import functools
import http.server
import os
import pathlib
import secrets
import socketserver
import struct
import sys
import threading
import zlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fake_supabase import FakeSupabase  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
SUPABASE_JS = os.environ.get('SUPABASE_JS_PATH')
results = {'pass': 0, 'fail': []}


def check(cond, msg):
    if cond:
        results['pass'] += 1
    else:
        results['fail'].append(msg)
        print('  LỖI', msg)


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = socketserver.ThreadingTCPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=str(ROOT)))
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def tiny_png():
    raw = b'\x00' + b'\x80\x60\x40' * 4
    data = b''.join([b'\x00' + b'\x80\x60\x40' * 4 for _ in range(4)])
    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 4, 4, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(data)) + chunk(b'IEND', b'')) if raw else b''


PDF = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'

OVERFLOW_JS = """() => document.documentElement.scrollWidth - document.documentElement.clientWidth"""


def new_page(browser, fake, mobile, lang='vi'):
    vp = dict(width=390, height=844) if mobile else dict(width=1440, height=900)
    ctx = browser.new_context(viewport=vp, is_mobile=mobile, has_touch=mobile, service_workers='block')
    ctx.route('https://*.supabase.co/**', fake.handle)
    ctx.route_web_socket('**', lambda ws: None)
    if SUPABASE_JS:
        body = pathlib.Path(SUPABASE_JS).read_bytes()
        ctx.route('https://cdn.jsdelivr.net/**', lambda r: r.fulfill(status=200, body=body,
                  headers={'content-type': 'application/javascript'}))
    page = ctx.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('dialog', lambda d: d.accept('Môn đổi tên kiểm thử') if d.type == 'prompt' else d.accept())
    page.add_init_script(f"localStorage.setItem('ptt-site-language','{lang}')")
    return ctx, page, errors


def row(fake, table, **kw):
    return next((r for r in fake.db[table] if all(r.get(k) == v for k, v in kw.items())), None)


def admin_suite(browser, base, mobile):
    tag = '[admin ' + ('mobile' if mobile else 'desktop') + ']'
    print(tag)
    pw_admin, pw_user = secrets.token_urlsafe(12), secrets.token_urlsafe(12)
    fake = FakeSupabase('admin@example.test', pw_admin)
    fake.add_user('user@example.test', pw_user, 'Người dùng thử', confirmed=False)
    ctx, page, errors = new_page(browser, fake, mobile)

    # Tài khoản thường bị từ chối
    page.goto(base + '/admin-login.html')
    page.wait_for_function('window.pttSupabase')
    page.fill('#adminEmail', 'user@example.test')
    page.fill('#adminPassword', pw_user)
    page.click('#adminLoginForm button[type=submit]')
    page.wait_for_function("document.getElementById('adminLoginStatus').textContent.includes('quyền quản trị')")
    check('admin-login.html' in page.url, f'{tag} tài khoản thường không bị giữ ở trang đăng nhập')

    # Sai mật khẩu
    page.fill('#adminEmail', 'admin@example.test')
    page.fill('#adminPassword', 'sai-mat-khau')
    page.click('#adminLoginForm button[type=submit]')
    page.wait_for_function("document.getElementById('adminLoginStatus').textContent.length > 0 && "
                           "!document.getElementById('adminLoginStatus').textContent.includes('Đang')")
    check('admin-login.html' in page.url, f'{tag} sai mật khẩu vẫn vào được admin')

    # Admin
    page.fill('#adminPassword', pw_admin)
    page.click('#adminLoginForm button[type=submit]')
    page.wait_for_url('**/admin.html', timeout=15000)
    page.wait_for_function("document.querySelectorAll('#adminAssignmentRows tr').length >= 3", timeout=15000)
    check(page.locator('#metricGrid > *').count() > 0, f'{tag} Tổng quan không có số liệu')

    for view in ['dashboard', 'assignments', 'projects', 'site-image', 'feedback', 'messages', 'accounts',
                 'trash', 'security']:
        page.evaluate(f"pttAdminGo('{view}')")
        page.wait_for_timeout(150)
        check(page.locator(f'.admin-view[data-panel="{view}"]').evaluate("e => e.classList.contains('active')"),
              f'{tag} mục {view} không hiển thị')
        check(page.evaluate(OVERFLOW_JS) <= 1, f'{tag} mục {view} tràn ngang')

    # Môn học
    page.evaluate("pttAdminGo('assignments')")
    page.click('#manageSubjectsBtn')
    page.fill('#subjectName', 'Địa chấn thăm dò')
    page.click('#subjectForm button[type=submit]')
    page.wait_for_timeout(800)
    new_subject = row(fake, 'assignment_subjects', name='Địa chấn thăm dò')
    check(new_subject is not None, f'{tag} không thêm được môn học')
    shown = page.evaluate("document.getElementById('subjectManagerList').textContent.includes('Địa chấn thăm dò')")
    check(shown, f'{tag} thêm môn học: đã lưu nhưng danh sách không cập nhật, form không xóa '
                 '(event.currentTarget dùng sau await, admin.html)')
    if not shown:  # tải lại dữ liệu để các bước sau vẫn chạy
        page.evaluate('loadAdminData().then(renderSubjects)')
        page.wait_for_timeout(500)
        errors[:] = [e for e in errors if "reading 'reset'" not in e]
    slug = new_subject['slug'] if new_subject else ''
    page.click(f'[data-toggle-subject="{slug}"]')
    page.wait_for_timeout(400)
    check(new_subject and new_subject.get('active') is False, f'{tag} không ẩn được môn học')
    page.click(f'[data-toggle-subject="{slug}"]')
    page.wait_for_timeout(400)
    page.click(f'[data-rename-subject="{slug}"]')
    page.wait_for_timeout(400)
    check(row(fake, 'assignment_subjects', slug=slug)['name'] == 'Môn đổi tên kiểm thử', f'{tag} không đổi tên môn')
    page.click('#subjectModalClose')

    # Bài tập có file
    page.click('#addAssignmentBtn')
    page.fill('#assignmentDate', '2026-10-20')
    page.select_option('#assignmentSubject', slug)
    page.fill('#assignmentTitle', 'Bài kiểm thử tự động')
    page.fill('#assignmentTopic', 'Minh giải tài liệu địa vật lý giếng khoan')
    page.click('#assignmentContent')
    page.keyboard.type('Nội dung bài tập kiểm thử.')
    page.set_input_files('#assignmentFile', files=[{'name': 'bai-kiem-thu.pdf', 'mimeType': 'application/pdf',
                                                    'buffer': PDF}])
    page.click('#assignmentSaveBtn')
    page.wait_for_function("document.getElementById('assignmentStatus').textContent.startsWith('Đã lưu')",
                           timeout=15000)
    a1 = row(fake, 'assignments', title='Bài kiểm thử tự động')
    check(a1 and a1['file_path'].endswith('bai-kiem-thu.pdf') and a1['assignment_number'] == 1,
          f'{tag} bài tập có file lưu sai: {a1}')
    check(any(w[0] == 'UPLOAD' and w[1] == 'assignments' for w in fake.writes), f'{tag} không tải file lên Storage')
    check(a1 and 'Nội dung bài tập kiểm thử' in a1['content_text'], f'{tag} mất nội dung rich-text')
    page.wait_for_timeout(800)

    # Bài tập không file, cùng ngày → số bài 2
    page.click('#addAssignmentBtn')
    page.fill('#assignmentDate', '2026-10-20')
    page.select_option('#assignmentSubject', slug)
    page.fill('#assignmentTitle', 'Bài không file')
    page.click('#assignmentSaveBtn')
    page.wait_for_function("document.getElementById('assignmentStatus').textContent.startsWith('Đã lưu')")
    a2 = row(fake, 'assignments', title='Bài không file')
    check(a2 and a2['assignment_number'] == 2 and not a2['file_path'], f'{tag} bài không file sai: {a2}')
    page.wait_for_timeout(800)

    # Sửa bài tập
    page.click(f'[data-edit-assignment="{a2["id"]}"]')
    page.fill('#assignmentTitle', 'Bài không file (đã sửa)')
    page.click('#assignmentSaveBtn')
    page.wait_for_function("document.getElementById('assignmentStatus').textContent.includes('Đã lưu thay đổi')")
    check(row(fake, 'assignments', id=a2['id'])['title'] == 'Bài không file (đã sửa)', f'{tag} không sửa được bài')
    page.wait_for_timeout(800)

    # Đổi môn ngay trên danh sách
    old_subject = fake.db['assignment_subjects'][0]['slug']
    page.select_option(f'[data-assignment-subject="{a2["id"]}"]', old_subject)
    page.wait_for_timeout(500)
    check(row(fake, 'assignments', id=a2['id'])['subject'] == old_subject, f'{tag} không đổi được môn của bài')

    # Thùng rác: chuyển, khôi phục, xóa vĩnh viễn
    page.click(f'[data-delete-assignment="{a1["id"]}"]')
    page.wait_for_function(f"!document.querySelector('[data-delete-assignment=\"{a1['id']}\"]')")
    check(row(fake, 'assignments', id=a1['id'])['deleted_at'] is not None, f'{tag} không chuyển bài vào thùng rác')
    check(row(fake, 'assignments', id=a2['id'])['assignment_number'] == 1, f'{tag} không đánh lại số bài')
    page.evaluate("pttAdminGo('trash')")
    page.click(f'[data-restore-assignment="{a1["id"]}"]')
    page.wait_for_timeout(700)
    check(row(fake, 'assignments', id=a1['id'])['deleted_at'] is None, f'{tag} không khôi phục được bài')
    page.evaluate("pttAdminGo('assignments')")
    page.click(f'[data-delete-assignment="{a1["id"]}"]')
    page.wait_for_timeout(700)
    page.evaluate("pttAdminGo('trash')")
    page.click(f'[data-purge-assignment="{a1["id"]}"]')
    page.wait_for_timeout(700)
    check(row(fake, 'assignments', id=a1['id']) is None, f'{tag} không xóa vĩnh viễn được bài')
    check(any(w[0] == 'REMOVE' and w[1] == 'assignments' for w in fake.writes), f'{tag} không xóa file của bài')

    # Dự án có ảnh và báo cáo
    page.evaluate("pttAdminGo('projects')")
    page.click('#addProjectBtn')
    page.fill('#projectTitle', 'Dự án kiểm thử tự động')
    page.fill('#projectType', 'Đánh giá tầng chứa')
    page.fill('#projectSummary', 'Tóm tắt dự án dùng cho kiểm thử tự động.')
    page.fill('#projectTags', 'Well logging, Petrophysics')
    page.set_input_files('#projectImageFile', files=[{'name': 'anh.png', 'mimeType': 'image/png', 'buffer': tiny_png()}])
    page.set_input_files('#projectReportFiles', files=[{'name': 'bao-cao.pdf', 'mimeType': 'application/pdf',
                                                        'buffer': PDF}])
    page.wait_for_timeout(500)
    page.click('#projectSaveBtn')
    page.wait_for_function("/Đã (thêm|lưu)/.test(document.getElementById('projectStatus').textContent)",
                           timeout=15000)
    p1 = row(fake, 'projects', title='Dự án kiểm thử tự động')
    check(p1 and p1['image_path'] and len(p1['report_files']) == 1 and p1['tags'] == ['Well logging', 'Petrophysics'],
          f'{tag} dự án lưu sai: {p1}')
    page.wait_for_timeout(900)
    page.click(f'[data-delete-project="{p1["id"]}"]')
    page.wait_for_timeout(600)
    check(row(fake, 'projects', id=p1['id'])['deleted_at'] is not None, f'{tag} không chuyển dự án vào thùng rác')
    page.evaluate("pttAdminGo('trash')")
    page.click(f'[data-restore-project="{p1["id"]}"]')
    page.wait_for_timeout(600)
    check(row(fake, 'projects', id=p1['id'])['deleted_at'] is None, f'{tag} không khôi phục được dự án')
    page.evaluate("pttAdminGo('projects')")
    page.click(f'[data-delete-project="{p1["id"]}"]')
    page.wait_for_timeout(600)
    page.evaluate("pttAdminGo('trash')")
    page.click(f'[data-purge-project="{p1["id"]}"]')
    page.wait_for_timeout(600)
    check(row(fake, 'projects', id=p1['id']) is None, f'{tag} không xóa vĩnh viễn được dự án')
    check(any(w[0] == 'REMOVE' and w[1] == 'project-reports' for w in fake.writes), f'{tag} không xóa báo cáo dự án')

    # Ảnh giới thiệu
    page.evaluate("pttAdminGo('site-image')")
    page.set_input_files('#siteAboutImageFile', files=[{'name': 'gioi-thieu.png', 'mimeType': 'image/png',
                                                         'buffer': tiny_png()}])
    page.wait_for_timeout(500)
    page.click('#saveSiteAboutImageBtn')
    page.wait_for_function("document.getElementById('siteAboutImageStatus').textContent.startsWith('Đã lưu')",
                           timeout=15000)
    check(row(fake, 'site_settings', key='about_image_url') is not None, f'{tag} không lưu được ảnh giới thiệu')

    # Phản hồi và lời nhắn
    page.evaluate("pttAdminGo('feedback')")
    c_id = fake.db['comments'][0]['id']
    chat_id = fake.db['academic_chat_messages'][0]['id']
    page.click(f'[data-delete-comment="{c_id}"]')
    page.wait_for_timeout(500)
    page.click(f'[data-delete-chat="{chat_id}"]')
    page.wait_for_timeout(500)
    check(not fake.db['comments'] and not fake.db['academic_chat_messages'], f'{tag} không xóa được phản hồi')
    page.evaluate("pttAdminGo('messages')")
    page.click(f'[data-delete-message="{fake.db["messages"][0]["id"]}"]')
    page.wait_for_timeout(500)
    check(not fake.db['messages'], f'{tag} không xóa được lời nhắn')

    # Tài khoản
    page.evaluate("pttAdminGo('accounts')")
    user = fake.users['user@example.test']
    page.wait_for_selector(f'[data-confirm-account="{user["id"]}"]')
    page.click(f'[data-confirm-account="{user["id"]}"]')
    page.wait_for_function("document.getElementById('accountStatus').textContent.includes('Đã xác nhận')")
    check(user['confirmed'], f'{tag} không xác nhận được email')
    page.click(f'[data-delete-account="{user["id"]}"]')
    page.wait_for_function("document.getElementById('accountStatus').textContent.includes('Đã xóa')")
    check('user@example.test' not in fake.users, f'{tag} không xóa được tài khoản thường')
    check(page.locator(f'[data-delete-account="{fake.admin_id}"]').count() == 0, f'{tag} tài khoản admin có nút xóa')

    page.click('#logoutBtn')
    page.wait_for_url('**/admin-login.html')
    check(not errors, f'{tag} lỗi JavaScript: {errors}')
    check(not fake.unexpected, f'{tag} request ngoài dự kiến: {fake.unexpected}')
    ctx.close()


def public_suite(browser, base, mobile, lang):
    tag = f'[công khai {lang} ' + ('mobile' if mobile else 'desktop') + ']'
    print(tag)
    fake = FakeSupabase('admin@example.test', secrets.token_urlsafe(12))
    ctx, page, errors = new_page(browser, fake, mobile, lang)
    page.goto(base + '/index.html')
    page.wait_for_function('typeof syncUserUI === "function" && window.pttSupabase && assignments.length > 0',
                           timeout=20000)
    page.wait_for_timeout(600)
    pw = secrets.token_urlsafe(12)

    # Đăng ký → tự đăng nhập
    page.evaluate("openModal(document.getElementById('userRegisterModal'))")
    page.fill('#userRegisterName', 'Sinh viên thử')
    page.fill('#userRegisterEmail', 'sv@example.test')
    page.fill('#userRegisterPassword', pw)
    page.fill('#userRegisterPassword2', pw)
    page.click('#userRegisterForm button[type=submit]')
    page.wait_for_function("!document.getElementById('userAccountBtn').hidden", timeout=15000)
    check('sv@example.test' in fake.users, f'{tag} không đăng ký được')

    # Đăng xuất
    page.click('#userAccountBtn')
    page.click('#userLogoutBtn')
    page.wait_for_function("document.getElementById('userAccountBtn').hidden")

    # Sai mật khẩu rồi đăng nhập đúng
    page.evaluate("openModal(document.getElementById('userLoginModal'))")
    page.fill('#userLoginEmail', 'sv@example.test')
    page.fill('#userLoginPassword', 'sai-mat-khau')
    page.click('#userLoginForm button[type=submit]')
    page.wait_for_function("document.getElementById('userLoginStatus').textContent.length > 0 && "
                           "!/Đang|Signing|Connexion en cours/.test(document.getElementById('userLoginStatus').textContent)")
    check(page.evaluate("document.getElementById('userAccountBtn').hidden"), f'{tag} sai mật khẩu vẫn đăng nhập')
    page.fill('#userLoginPassword', pw)
    page.click('#userLoginForm button[type=submit]')
    page.wait_for_function("!document.getElementById('userAccountBtn').hidden", timeout=15000)
    page.keyboard.press('Escape')

    # Nhận xét riêng
    page.locator('.comment-open').first.scroll_into_view_if_needed()
    page.locator('.comment-open').first.click()
    page.wait_for_selector('#commentModal.open')
    page.fill('#commentText', 'Nhận xét riêng từ kiểm thử.')
    page.click('#commentForm button[type=submit]')
    page.wait_for_function("document.querySelectorAll('#privateCommentHistory .private-comment-entry').length >= 1",
                           timeout=10000)
    c = row(fake, 'comments', body='Nhận xét riêng từ kiểm thử.')
    check(c and c['user_id'] == fake.users['sv@example.test']['id'], f'{tag} nhận xét riêng lưu sai: {c}')
    page.keyboard.press('Escape')

    # Thảo luận công khai
    page.locator('#academicChatMessage').scroll_into_view_if_needed()
    page.wait_for_timeout(500)
    page.fill('#academicChatMessage', 'Tin nhắn thảo luận kiểm thử.')
    page.click('#academicChatForm button[type=submit]')
    page.wait_for_function("document.getElementById('academicExchangeHistory').textContent"
                           ".includes('Tin nhắn thảo luận kiểm thử.')")
    check(row(fake, 'academic_chat_messages', body='Tin nhắn thảo luận kiểm thử.') is not None,
          f'{tag} không gửi được thảo luận')

    # Liên hệ
    page.fill('#contactForm input[name=name]', 'Khách liên hệ')
    page.fill('#contactForm input[name=email]', 'khach@example.test')
    page.fill('#contactForm textarea[name=message]', 'Nội dung liên hệ kiểm thử.')
    page.evaluate("document.getElementById('contactForm').requestSubmit()")
    page.wait_for_timeout(600)
    check(row(fake, 'messages', email='khach@example.test') is not None, f'{tag} không gửi được liên hệ')

    # Trợ lý ảo: backend và dự phòng
    page.click('#aiFab')
    page.fill('#aiInput', 'Website có những dự án nào?')
    page.click('#aiForm button[type=submit]')
    page.wait_for_function("[...document.querySelectorAll('#aiMessages .msg.bot')].some(m => "
                           "m.textContent.includes('Trả lời giả lập'))", timeout=10000)
    fake.fail_functions.add('geo-ai')
    page.fill('#aiInput', 'Có những bài tập nào?')
    page.click('#aiForm button[type=submit]')
    page.wait_for_function("document.querySelectorAll('#aiMessages .msg.bot:not(.typing)').length >= 3 && "
                           "!document.querySelector('#aiMessages .typing')", timeout=10000)
    last = page.locator('#aiMessages .msg.bot').last.text_content()
    check('Bài' in last or 'bài tập' in last, f'{tag} trợ lý dự phòng trả lời sai: {last[:80]}')
    page.click('#aiClose')

    check(page.evaluate(OVERFLOW_JS) <= 1, f'{tag} tràn ngang')
    check(not errors, f'{tag} lỗi JavaScript: {errors}')
    check(not fake.unexpected, f'{tag} request ngoài dự kiến: {fake.unexpected}')

    # Trang xem tài liệu
    with_file = next(a for a in fake.db['assignments'] if a['file_path'])
    page.goto(base + '/assignment-viewer.html?id=' + with_file['id'])
    page.wait_for_selector('#previewShell iframe', timeout=15000)
    check(page.get_attribute('#downloadBtn', 'aria-disabled') == 'false', f'{tag} viewer: nút tải chưa bật')
    check(page.evaluate(OVERFLOW_JS) <= 1, f'{tag} viewer tràn ngang')
    check(not errors, f'{tag} viewer lỗi JavaScript: {errors}')
    ctx.close()


def main():
    srv = serve()
    base = f'http://127.0.0.1:{srv.server_address[1]}'
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for mobile in (False, True):
            for suite in (lambda: admin_suite(browser, base, mobile),):
                try:
                    suite()
                except Exception as exc:
                    check(False, f'[admin {"mobile" if mobile else "desktop"}] dừng giữa chừng: {exc!s:.300}')
            for lang in ('vi', 'en', 'fr'):
                try:
                    public_suite(browser, base, mobile, lang)
                except Exception as exc:
                    check(False, f'[công khai {lang} {"mobile" if mobile else "desktop"}] dừng giữa chừng: {exc!s:.300}')
        browser.close()
    srv.shutdown()
    print(f"\n{results['pass']} kiểm tra đạt, {len(results['fail'])} lỗi; không có request nào tới Supabase thật.")
    sys.exit(1 if results['fail'] else 0)


if __name__ == '__main__':
    main()
