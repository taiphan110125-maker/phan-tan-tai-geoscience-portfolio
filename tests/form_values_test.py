"""Form values must not depend on the interface language.

Checks the contact form (messages.topic) and the private feedback form
(comments.role) in Vietnamese, English and French, including a language switch
while the form is open, and that an invalid value is refused with a visible
error and no request.

No real data is written: every request to Supabase is answered inside the
browser by this script, and Realtime WebSockets are mocked, never connected.

Run from the repository root:
    pip install playwright && python -m playwright install chromium
    python tests/form_values_test.py

Optional: SUPABASE_JS_PATH=/path/to/supabase.js serves supabase-js locally
instead of fetching it from cdn.jsdelivr.net.
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
        print('  FAIL', message)


def serve():
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    handler = functools.partial(QuietHandler, directory=str(ROOT))
    server = socketserver.TCPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


class FakeSupabase:
    """Answers every Supabase request locally and records writes."""

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
    # Mock every WebSocket (Supabase Realtime): never connected to a real server.
    page.route_web_socket('**', lambda ws: None)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.add_init_script(f"localStorage.setItem('ptt-site-language','{lang}')")
    page.goto(base + '/index.html', wait_until='load')
    page.wait_for_function('typeof syncUserUI === "function" && window.supabase && assignments.length > 0', timeout=20000)
    page.wait_for_timeout(800)  # let the initial auth state event settle before the test signs in
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
                      f'{tag} contact topic labels {option_labels(page, "#contactForm select[name=topic]")}')
                for i, expected in enumerate(TOPICS):
                    writes = submit_contact(page, fake, i)
                    check(len(writes) == 1 and writes[0][0] == 'messages' and writes[0][1].get('topic') == expected,
                          f'{tag} contact topic #{i}: expected {expected!r}, sent {writes}')

                open_comment(page)
                check(option_labels(page, '#commentRole') == LABELS[lang]['role'],
                      f'{tag} comment role labels {option_labels(page, "#commentRole")}')
                for i, expected in enumerate(ROLES):
                    writes = submit_comment(page, fake, i)
                    check(len(writes) == 1 and writes[0][0] == 'comments' and writes[0][1].get('role') == expected,
                          f'{tag} comment role #{i}: expected {expected!r}, sent {writes}')

                # Invalid value: an option whose value is a translated label must be refused.
                page.evaluate("""() => { const o = new Option('Lecturer', 'Lecturer');
                    document.getElementById('commentRole').add(o); }""")
                before = len(fake.writes)
                page.fill('#commentText', 'Nhận xét kiểm thử tự động.')
                page.eval_on_selector('#commentRole', 's => { s.selectedIndex = s.options.length - 1; }')
                page.evaluate("document.getElementById('commentForm').requestSubmit()")
                page.wait_for_timeout(400)
                check(page.eval_on_selector('#commentRole', 's => s.value') == 'Lecturer', f'{tag} invalid role not selected')
                check(len(fake.writes) == before, f'{tag} invalid role was sent')
                check(page.text_content('#commentStatus').strip() == ERRORS[lang]['role'],
                      f'{tag} invalid role message: {page.text_content("#commentStatus")!r}')
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
                      f'{tag} invalid topic not selected')
                check(len(fake.writes) == before, f'{tag} invalid topic was sent')
                check(page.text_content('#contactStatus').strip() == ERRORS[lang]['topic'],
                      f'{tag} invalid topic message: {page.text_content("#contactStatus")!r}')

                check(not errors, f'{tag} page errors: {errors}')
                context.close()

        # Switching language while a form is open keeps the selection and the stored value.
        for start, middle, end in [('vi', 'en', 'fr'), ('fr', 'vi', 'en'), ('en', 'fr', 'vi')]:
            tag = f'[switch {start}->{middle}->{end}]'
            print(tag)
            context, page, errors = open_page(browser, base, start, fake)
            open_comment(page)
            page.select_option('#commentRole', index=1)
            set_language(page, middle)
            set_language(page, end)
            check(page.eval_on_selector('#commentRole', 's => s.selectedIndex') == 1, f'{tag} role selection lost')
            check(option_labels(page, '#commentRole') == LABELS[end]['role'], f'{tag} role labels not in {end}')
            before = len(fake.writes)
            page.fill('#commentName', 'Kiểm thử')
            page.fill('#commentText', 'Nhận xét sau khi đổi ngôn ngữ.')
            page.evaluate("document.getElementById('commentForm').requestSubmit()")
            page.wait_for_timeout(500)
            writes = fake.writes[before:]
            check(len(writes) == 1 and writes[0][1].get('role') == 'Sinh viên', f'{tag} comment sent {writes}')
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
            check(len(writes) == 1 and writes[0][1].get('topic') == 'Hợp tác nghiên cứu', f'{tag} contact sent {writes}')
            check(not errors, f'{tag} page errors: {errors}')
            context.close()

        browser.close()
    server.shutdown()

    check(not fake.unexpected, f'unexpected Supabase requests: {fake.unexpected}')
    print(f'\n{passed} checks passed, {len(failures)} failed; {len(fake.writes)} writes answered locally, 0 sent to Supabase.')
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
