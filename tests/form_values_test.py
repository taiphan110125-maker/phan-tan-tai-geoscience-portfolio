"""Giá trị form lưu vào database không được phụ thuộc ngôn ngữ giao diện.

Kiểm tra form Liên hệ (messages.topic) và form Nhận xét riêng (comments.role)
ở Tiếng Việt, English, Français; cả trường hợp đổi ngôn ngữ khi form đang mở;
và giá trị không hợp lệ phải bị từ chối, có thông báo lỗi, không gửi request.

Không ghi dữ liệu thật: mọi request tới Supabase được script trả lời ngay trong
trình duyệt, kết nối Realtime (WebSocket) được giả lập, không nối tới máy chủ.

Chạy từ thư mục gốc repository:
    pip install playwright && python -m playwright install chromium
    python tests/form_values_test.py

Tùy chọn: SUPABASE_JS_PATH=/duong/dan/supabase.js để dùng supabase-js cục bộ
thay vì tải từ cdn.jsdelivr.net.
"""
import functools
import http.server
import json
import os
import pathlib
import socketserver
import sys
import threading

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
SNAPSHOT = json.loads((ROOT / 'public-content.json').read_text(encoding='utf-8'))
SUPABASE_JS = os.environ.get('SUPABASE_JS_PATH')

TOPICS = ['Trao đổi học thuật', 'Góp ý bài tập', 'Hợp tác nghiên cứu', 'Khác']
ROLES = ['Giảng viên', 'Sinh viên', 'Khách']
LABELS = {
    'vi': {'topic': TOPICS, 'role': ROLES},
    'en': {'topic': ['Academic exchange', 'Assignment feedback', 'Research collaboration', 'Other'],
           'role': ['Lecturer', 'Student', 'Guest']},
    'fr': {'topic': ['Échange académique', 'Commentaires sur un devoir', 'Collaboration scientifique', 'Autre'],
           'role': ['Enseignant', 'Étudiant', 'Invité']},
}
ERRORS = {
    'vi': {'topic': 'Chủ đề không hợp lệ. Vui lòng chọn lại trong danh sách.',
           'role': 'Vai trò không hợp lệ. Vui lòng chọn lại trong danh sách.'},
    'en': {'topic': 'Invalid topic. Please choose one from the list.',
           'role': 'Invalid role. Please choose one from the list.'},
    'fr': {'topic': 'Sujet non valide. Veuillez en choisir un dans la liste.',
           'role': 'Rôle non valide. Veuillez en choisir un dans la liste.'},
}

failures = []
passed = 0


def check(condition, message):
    global passed
    if condition:
        passed += 1
    else:
        failures.append(message)
        print('  LỖI', message)


def serve():
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    handler = functools.partial(QuietHandler, directory=str(ROOT))
    server = socketserver.TCPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


class FakeSupabase:
    """Trả lời mọi request Supabase ngay tại chỗ và ghi lại các lần ghi dữ liệu."""

    def __init__(self):
        self.writes = []
        self.unexpected = []

    def handle(self, route):
        request = route.request
        url = request.url
        method = request.method
        if method == 'OPTIONS':
            return route.fulfill(status=204, headers=self.cors())
        if '/rest/v1/' in url and method == 'POST':
            body = json.loads(request.post_data or '{}')
            table = url.split('/rest/v1/')[1].split('?')[0]
            self.writes.append((table, body))
            row = dict(body, id='test-' + str(len(self.writes)), created_at='2026-10-28T08:00:00Z')
            return route.fulfill(status=201, body=json.dumps([row]), headers=self.cors())
        if '/rest/v1/' in url and method == 'GET':
            table = url.split('/rest/v1/')[1].split('?')[0]
            data = {'projects': SNAPSHOT['projects'], 'assignments': SNAPSHOT['assignments'],
                    'assignment_subjects': SNAPSHOT['subjects']}.get(table, [])
            return route.fulfill(status=200, body=json.dumps(data), headers=self.cors())
        if method != 'GET':
            self.unexpected.append(f'{method} {url}')
        return route.abort()

    @staticmethod
    def cors():
        return {'content-type': 'application/json', 'access-control-allow-origin': '*',
                'access-control-allow-headers': '*', 'access-control-allow-methods': '*'}


def open_page(browser, base, lang, fake, mobile=False):
    viewport = dict(width=390, height=844) if mobile else dict(width=1440, height=900)
    context = browser.new_context(viewport=viewport, is_mobile=mobile, has_touch=mobile, service_workers='block')
    context.route('https://*.supabase.co/**', fake.handle)
    if SUPABASE_JS:
        body = pathlib.Path(SUPABASE_JS).read_bytes()
        context.route('https://cdn.jsdelivr.net/**', lambda r: r.fulfill(status=200, body=body,
                      headers={'content-type': 'application/javascript'}))
    page = context.new_page()
    # Giả lập mọi WebSocket (Supabase Realtime): không bao giờ nối tới máy chủ thật.
    page.route_web_socket('**', lambda ws: None)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.add_init_script(f"localStorage.setItem('ptt-site-language','{lang}')")
    page.goto(base + '/index.html', wait_until='load')
    page.wait_for_function('typeof syncUserUI === "function" && window.supabase && assignments.length > 0', timeout=20000)
    page.wait_for_timeout(800)  # chờ sự kiện trạng thái đăng nhập ban đầu xong rồi mới đăng nhập giả
    return context, page, errors


def option_labels(page, selector):
    return page.eval_on_selector_all(selector + ' option', 'os => os.map(o => o.textContent.trim())')


def set_language(page, lang):
    page.evaluate("""lang => { const s = document.getElementById('pttLanguageSelector');
        s.value = lang; s.dispatchEvent(new Event('change', {bubbles: true})); }""", lang)
    page.wait_for_timeout(150)


def submit_contact(page, fake, index):
    page.evaluate("localStorage.removeItem('ptt-contact-last')")
    before = len(fake.writes)
    page.fill('#contactForm input[name=name]', 'Kiểm thử')
    page.fill('#contactForm input[name=email]', 'test@example.com')
    page.fill('#contactForm textarea[name=message]', 'Nội dung kiểm thử tự động.')
    page.select_option('#contactForm select[name=topic]', index=index)
    page.evaluate("document.getElementById('contactForm').requestSubmit()")
    page.wait_for_timeout(500)
    return fake.writes[before:]


def open_comment(page):
    page.evaluate("""() => { syncUserUI({id: '00000000-0000-0000-0000-000000000001',
        email: 'test@example.com', name: 'Kiểm thử'}); openComment(assignments[0].id); }""")
    page.wait_for_selector('#commentModal.open')


def submit_comment(page, fake, index):
    before = len(fake.writes)
    page.fill('#commentName', 'Kiểm thử')
    page.fill('#commentText', 'Nhận xét kiểm thử tự động.')
    page.select_option('#commentRole', index=index)
    page.evaluate("document.getElementById('commentForm').requestSubmit()")
    page.wait_for_timeout(500)
    return fake.writes[before:]


def main():
    server = serve()
    base = f'http://127.0.0.1:{server.server_address[1]}'
    fake = FakeSupabase()
    with sync_playwright() as p:
        browser = p.chromium.launch()

        for lang in ['vi', 'en', 'fr']:
            for mobile in [False, True]:
                tag = f"[{lang} {'mobile' if mobile else 'desktop'}]"
                print(tag)
                context, page, errors = open_page(browser, base, lang, fake, mobile)

                check(option_labels(page, '#contactForm select[name=topic]') == LABELS[lang]['topic'],
                      f'{tag} nhãn Chủ đề sai: {option_labels(page, "#contactForm select[name=topic]")}')
                for i, expected in enumerate(TOPICS):
                    writes = submit_contact(page, fake, i)
                    check(len(writes) == 1 and writes[0][0] == 'messages' and writes[0][1].get('topic') == expected,
                          f'{tag} Chủ đề #{i}: cần {expected!r}, đã gửi {writes}')

                open_comment(page)
                check(option_labels(page, '#commentRole') == LABELS[lang]['role'],
                      f'{tag} nhãn Vai trò sai: {option_labels(page, "#commentRole")}')
                for i, expected in enumerate(ROLES):
                    writes = submit_comment(page, fake, i)
                    check(len(writes) == 1 and writes[0][0] == 'comments' and writes[0][1].get('role') == expected,
                          f'{tag} Vai trò #{i}: cần {expected!r}, đã gửi {writes}')

                # Giá trị không hợp lệ: lựa chọn có value là nhãn đã dịch phải bị từ chối.
                page.evaluate("""() => { const o = new Option('Lecturer', 'Lecturer');
                    document.getElementById('commentRole').add(o); }""")
                before = len(fake.writes)
                page.fill('#commentText', 'Nhận xét kiểm thử tự động.')
                page.eval_on_selector('#commentRole', 's => { s.selectedIndex = s.options.length - 1; }')
                page.evaluate("document.getElementById('commentForm').requestSubmit()")
                page.wait_for_timeout(400)
                check(page.eval_on_selector('#commentRole', 's => s.value') == 'Lecturer', f'{tag} chưa chọn được vai trò không hợp lệ')
                check(len(fake.writes) == before, f'{tag} vai trò không hợp lệ vẫn bị gửi đi')
                check(page.text_content('#commentStatus').strip() == ERRORS[lang]['role'],
                      f'{tag} thông báo lỗi Vai trò sai: {page.text_content("#commentStatus")!r}')
                page.keyboard.press('Escape')

                page.evaluate("""() => { const o = new Option('Academic exchange', 'Academic exchange');
                    document.querySelector('#contactForm select[name=topic]').add(o); }""")
                page.evaluate("localStorage.removeItem('ptt-contact-last')")
                page.fill('#contactForm input[name=name]', 'Kiểm thử')
                page.fill('#contactForm input[name=email]', 'test@example.com')
                page.fill('#contactForm textarea[name=message]', 'Nội dung kiểm thử tự động.')
                page.eval_on_selector('#contactForm select[name=topic]', 's => { s.selectedIndex = s.options.length - 1; }')
                before = len(fake.writes)
                page.evaluate("document.getElementById('contactForm').requestSubmit()")
                page.wait_for_timeout(400)
                check(page.eval_on_selector('#contactForm select[name=topic]', 's => s.value') == 'Academic exchange',
                      f'{tag} chưa chọn được chủ đề không hợp lệ')
                check(len(fake.writes) == before, f'{tag} chủ đề không hợp lệ vẫn bị gửi đi')
                check(page.text_content('#contactStatus').strip() == ERRORS[lang]['topic'],
                      f'{tag} thông báo lỗi Chủ đề sai: {page.text_content("#contactStatus")!r}')

                check(not errors, f'{tag} lỗi JavaScript trên trang: {errors}')
                context.close()

        # Đổi ngôn ngữ khi form đang mở: giữ nguyên lựa chọn và giá trị lưu.
        for start, middle, end in [('vi', 'en', 'fr'), ('fr', 'vi', 'en'), ('en', 'fr', 'vi')]:
            tag = f'[switch {start}->{middle}->{end}]'
            print(tag)
            context, page, errors = open_page(browser, base, start, fake)
            open_comment(page)
            page.select_option('#commentRole', index=1)
            set_language(page, middle)
            set_language(page, end)
            check(page.eval_on_selector('#commentRole', 's => s.selectedIndex') == 1, f'{tag} mất lựa chọn Vai trò')
            check(option_labels(page, '#commentRole') == LABELS[end]['role'], f'{tag} nhãn Vai trò không ở ngôn ngữ {end}')
            before = len(fake.writes)
            page.fill('#commentName', 'Kiểm thử')
            page.fill('#commentText', 'Nhận xét sau khi đổi ngôn ngữ.')
            page.evaluate("document.getElementById('commentForm').requestSubmit()")
            page.wait_for_timeout(500)
            writes = fake.writes[before:]
            check(len(writes) == 1 and writes[0][1].get('role') == 'Sinh viên', f'{tag} nhận xét đã gửi {writes}')
            page.keyboard.press('Escape')

            set_language(page, start)
            page.evaluate("localStorage.removeItem('ptt-contact-last')")
            page.fill('#contactForm input[name=name]', 'Kiểm thử')
            page.fill('#contactForm input[name=email]', 'test@example.com')
            page.fill('#contactForm textarea[name=message]', 'Nội dung sau khi đổi ngôn ngữ.')
            page.select_option('#contactForm select[name=topic]', index=2)
            set_language(page, middle)
            set_language(page, end)
            before = len(fake.writes)
            page.evaluate("document.getElementById('contactForm').requestSubmit()")
            page.wait_for_timeout(500)
            writes = fake.writes[before:]
            check(len(writes) == 1 and writes[0][1].get('topic') == 'Hợp tác nghiên cứu', f'{tag} lời nhắn đã gửi {writes}')
            check(not errors, f'{tag} lỗi JavaScript trên trang: {errors}')
            context.close()

        browser.close()
    server.shutdown()

    check(not fake.unexpected, f'request Supabase ngoài dự kiến: {fake.unexpected}')
    print(f'\n{passed} kiểm tra đạt, {len(failures)} lỗi; {len(fake.writes)} lần ghi được trả lời tại chỗ, 0 lần gửi tới Supabase.')
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
