"""Kiểm tra lần hiển thị đầu tiên khi tải lại trang ở English/Français.

- Không được thấy chữ giao diện tiếng Việt trước khi bản dịch áp dụng
  (trước đây menu hiện "Trang chủ" rồi mới đổi sang "Home").
- Trang không phụ thuộc CDN bên ngoài: chặn hoàn toàn cdn.jsdelivr.net mà
  trang vẫn chạy bình thường.
- Supabase được giả lập chậm 1,5 giây để mô phỏng mạng yếu; không gửi
  request nào tới Supabase thật.

Chạy: python tests/first_paint_test.py
"""
import functools
import http.server
import pathlib
import socketserver
import sys
import threading
import time

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
passed, failures = 0, []

PROBE = r"""
(() => {
  window.__visibleVietnamese = [];
  window.__firstVisible = null;
  const check = () => {
    const body = document.body;
    if (body) {
      const visible = getComputedStyle(body).visibility !== 'hidden';
      const nav = document.querySelector('#primaryNav a');
      if (visible && window.__firstVisible === null) window.__firstVisible = Math.round(performance.now());
      if (visible && nav && nav.textContent.trim() === 'Trang chủ') window.__visibleVietnamese.push(Math.round(performance.now()));
    }
    if (performance.now() < 6000) requestAnimationFrame(check);
  };
  requestAnimationFrame(check);
})();
"""


def check(cond, msg):
    global passed
    if cond:
        passed += 1
    else:
        failures.append(msg)
        print('  LỖI', msg)


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = socketserver.ThreadingTCPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=str(ROOT)))
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def slow_supabase(route):
    time.sleep(1.5)
    route.fulfill(status=503, body='{}', headers={'access-control-allow-origin': '*', 'content-type': 'application/json'})


def main():
    srv = serve()
    base = f'http://127.0.0.1:{srv.server_address[1]}'
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for lang, home in (('en', 'Home'), ('fr', 'Accueil'), ('vi', 'Trang chủ')):
            for mobile in (False, True):
                tag = f'[{lang} {"mobile" if mobile else "desktop"}]'
                print(tag)
                ctx = browser.new_context(viewport=dict(width=390, height=844) if mobile else dict(width=1440, height=900),
                                          is_mobile=mobile, service_workers='block')
                cdn_requests = []
                ctx.route('https://cdn.jsdelivr.net/**', lambda r: (cdn_requests.append(r.request.url), r.abort()))
                ctx.route('https://*.supabase.co/**', slow_supabase)
                ctx.route_web_socket('**', lambda ws: None)
                page = ctx.new_page()
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.add_init_script(f"localStorage.setItem('ptt-site-language','{lang}');" + PROBE)
                page.goto(base + '/index.html', wait_until='domcontentloaded')
                page.wait_for_timeout(2500)
                vi_seen = page.evaluate('window.__visibleVietnamese')
                first = page.evaluate('window.__firstVisible')
                nav = page.evaluate("document.querySelector('#primaryNav a').textContent.trim()")
                if lang != 'vi':
                    check(not vi_seen, f'{tag} thấy chữ tiếng Việt trước khi dịch (ms: {vi_seen[:3]})')
                check(nav == home, f'{tag} menu hiển thị "{nav}" thay vì "{home}"')
                check(first is not None and first < 1500, f'{tag} trang hiện quá muộn: {first} ms')
                check(not cdn_requests, f'{tag} vẫn gọi CDN ngoài: {cdn_requests}')
                check(page.evaluate('Boolean(window.supabase && window.pttSupabase)'), f'{tag} supabase-js chưa nạp')
                check(page.locator('.assignment-item').count() >= 3, f'{tag} không hiện bài tập (dự phòng snapshot)')
                check(not errors, f'{tag} lỗi JavaScript: {errors}')
                print(f'  hiện trang lúc {first} ms')
                ctx.close()
        browser.close()
    srv.shutdown()
    print(f'\n{passed} kiểm tra đạt, {len(failures)} lỗi.')
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
