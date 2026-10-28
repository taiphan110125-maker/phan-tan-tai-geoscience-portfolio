"""Backend Supabase giả lập dùng cho kiểm thử trên trình duyệt (Playwright).

Mọi request tới *.supabase.co được trả lời ngay trong trình duyệt bằng dữ liệu
trong bộ nhớ: Auth, REST (PostgREST rút gọn), Storage, Edge Functions. Không
có request nào tới Supabase thật, nên không ghi dữ liệu production.

Chỉ mô phỏng những gì frontend dùng; không mô phỏng RLS (trừ quyền admin
được đọc từ bảng profiles) và không thay thế kiểm thử trên Supabase thật.
"""
import base64
import copy
import json
import pathlib
import time
import uuid
from urllib.parse import parse_qsl, unquote, urlsplit

ROOT = pathlib.Path(__file__).resolve().parent.parent

UUID_TABLES = {'comments', 'messages', 'academic_chat_messages'}
KEYS = {
    'projects': 'id', 'assignments': 'id', 'assignment_subjects': 'slug', 'comments': 'id',
    'messages': 'id', 'academic_chat_messages': 'id', 'profiles': 'id', 'site_settings': 'key',
    'admin_notification_state': 'admin_id',
}
DEFAULTS = {
    'projects': {'published': True, 'deleted_at': None, 'deleted_by': None, 'tags': [], 'report_files': [],
                 'sort_order': 0, 'image_url': '', 'image_path': ''},
    'assignments': {'published': True, 'deleted_at': None, 'deleted_by': None, 'content_text': '',
                    'external_url': '', 'file_name': '', 'file_url': '', 'file_path': '', 'topic': ''},
    'assignment_subjects': {'active': True, 'sort_order': 0},
}


def now_iso():
    return time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime()) + '.000000+00:00'


def b64url(data):
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b'=').decode()


class FakeSupabase:
    def __init__(self, admin_email, admin_password):
        snap = json.loads((ROOT / 'public-content.json').read_text(encoding='utf-8'))
        self.calls = []          # (method, path) mọi request đã xử lý
        self.writes = []         # (method, table/bucket, body)
        self.unexpected = []
        self.fail_functions = set()
        self.users = {}
        self.tokens = {}
        admin = self.add_user(admin_email, admin_password, 'Quản trị thử', role='admin')
        self.admin_id = admin['id']
        self.db = {
            'projects': [dict(DEFAULTS['projects'], **{k: v for k, v in p.items() if k != 'remote_image_url'})
                         for p in snap['projects']],
            'assignments': [dict(DEFAULTS['assignments'], **a) for a in snap['assignments']],
            'assignment_subjects': [dict(s, active=True) for s in snap['subjects']],
            'comments': [{'id': str(uuid.uuid4()), 'assignment_id': snap['assignments'][0]['id'],
                          'user_id': None, 'name': 'Người nhận xét thử', 'role': 'Giảng viên',
                          'body': 'Nhận xét thử nghiệm.', 'created_at': now_iso(),
                          'assignment_title': snap['assignments'][0]['title'],
                          'assignment_date': snap['assignments'][0]['assignment_date'],
                          'assignment_number': 1, 'assignment_subject': 'Địa vật lý ứng dụng'}],
            'academic_chat_messages': [{'id': str(uuid.uuid4()), 'user_id': None, 'name': 'Khách thử',
                                        'role': 'Người xem', 'body': 'Tin nhắn thử.', 'created_at': now_iso()}],
            'messages': [{'id': str(uuid.uuid4()), 'name': 'Khách thử', 'email': 'guest@example.test',
                          'topic': 'Khác', 'message': 'Lời nhắn thử nghiệm.', 'created_at': now_iso()}],
            'site_settings': [],
            'admin_notification_state': [],
            'profiles': [],
        }
        for u in self.users.values():
            self.db['profiles'].append({'id': u['id'], 'name': u['name'], 'role': u['role'],
                                        'created_at': now_iso()})
        self.storage = {}

    # ---------- người dùng ----------
    def add_user(self, email, password, name, role='user', confirmed=True):
        user = {'id': str(uuid.uuid4()), 'email': email.lower(), 'password': password, 'name': name,
                'role': role, 'confirmed': confirmed, 'created_at': now_iso()}
        self.users[user['email']] = user
        if hasattr(self, 'db'):
            self.db['profiles'].append({'id': user['id'], 'name': name, 'role': role, 'created_at': now_iso()})
        return user

    def user_json(self, u):
        return {'id': u['id'], 'aud': 'authenticated', 'role': 'authenticated', 'email': u['email'],
                'email_confirmed_at': now_iso() if u['confirmed'] else None, 'app_metadata': {'provider': 'email'},
                'user_metadata': {'name': u['name']}, 'created_at': u['created_at'], 'updated_at': now_iso()}

    def session_for(self, u):
        exp = int(time.time()) + 3600
        token = '.'.join([b64url({'alg': 'HS256', 'typ': 'JWT'}),
                          b64url({'sub': u['id'], 'role': 'authenticated', 'email': u['email'], 'exp': exp,
                                  'aud': 'authenticated', 'session_id': str(uuid.uuid4())}),
                          'kiemthu'])
        self.tokens[token] = u['email']
        return {'access_token': token, 'token_type': 'bearer', 'expires_in': 3600, 'expires_at': exp,
                'refresh_token': uuid.uuid4().hex, 'user': self.user_json(u)}

    def user_from_request(self, request):
        auth = request.headers.get('authorization', '')
        token = auth[7:] if auth.lower().startswith('bearer ') else ''
        email = self.tokens.get(token)
        return self.users.get(email) if email else None

    # ---------- định tuyến ----------
    @staticmethod
    def cors():
        return {'access-control-allow-origin': '*', 'access-control-allow-headers': '*',
                'access-control-allow-methods': '*', 'access-control-expose-headers': '*'}

    def respond(self, route, status=200, body=None, headers=None):
        h = dict(self.cors(), **{'content-type': 'application/json'}, **(headers or {}))
        payload = '' if body is None else (body if isinstance(body, str) else json.dumps(body))
        route.fulfill(status=status, body=payload, headers=h)

    def handle(self, route):
        req = route.request
        url = urlsplit(req.url)
        if req.method == 'OPTIONS':
            return route.fulfill(status=204, headers=self.cors())
        self.calls.append((req.method, url.path))
        try:
            if url.path.startswith('/auth/v1/'):
                return self.auth(route, req, url)
            if url.path.startswith('/rest/v1/'):
                return self.rest(route, req, url)
            if url.path.startswith('/storage/v1/'):
                return self.storage_api(route, req, url)
            if url.path.startswith('/functions/v1/'):
                return self.functions(route, req, url)
        except Exception as exc:  # lỗi trong backend giả lập phải hiện rõ
            self.unexpected.append(f'{req.method} {url.path}: {exc!r}')
            return self.respond(route, 500, {'message': str(exc)})
        self.unexpected.append(f'{req.method} {url.path}')
        return route.abort()

    # ---------- Auth ----------
    def auth(self, route, req, url):
        path = url.path[len('/auth/v1/'):]
        q = dict(parse_qsl(url.query))
        if path == 'token' and q.get('grant_type') == 'password':
            body = json.loads(req.post_data or '{}')
            u = self.users.get(str(body.get('email', '')).lower())
            if not u or u['password'] != body.get('password'):
                return self.respond(route, 400, {'code': 400, 'error_code': 'invalid_credentials',
                                                 'msg': 'Invalid login credentials'})
            return self.respond(route, 200, self.session_for(u))
        if path == 'user':
            u = self.user_from_request(req)
            return self.respond(route, 200, self.user_json(u)) if u else \
                self.respond(route, 401, {'code': 401, 'msg': 'invalid JWT'})
        if path == 'logout':
            return route.fulfill(status=204, headers=self.cors())
        self.unexpected.append(f'auth {req.method} {path}')
        return self.respond(route, 404, {'msg': 'not found'})

    # ---------- REST (PostgREST rút gọn) ----------
    @staticmethod
    def _match(row, key, raw):
        neg = raw.startswith('not.')
        if neg:
            raw = raw[4:]
        op, _, val = raw.partition('.')
        cell = row.get(key)
        if op == 'is':
            ok = cell is None if val == 'null' else str(cell).lower() == val
        elif op == 'eq':
            ok = cell is not None and str(cell).lower() == unquote(val).lower()
        elif op == 'neq':
            ok = cell is None or str(cell).lower() != unquote(val).lower()
        elif op == 'in':
            items = [v.strip().strip('"') for v in unquote(val).strip('()').split(',')]
            ok = cell is not None and str(cell) in items
        elif op == 'gte':
            ok = cell is not None and str(cell) >= unquote(val)
        elif op == 'lt':
            ok = cell is not None and str(cell) < unquote(val)
        else:
            raise ValueError(f'toán tử chưa hỗ trợ: {op}')
        return not ok if neg else ok

    def _filter(self, rows, params):
        out = []
        for row in rows:
            if all(self._match(row, k, v) for k, v in params if k not in
                   ('select', 'order', 'limit', 'offset', 'on_conflict', 'columns')):
                out.append(row)
        return out

    def rest(self, route, req, url):
        table = url.path[len('/rest/v1/'):]
        params = parse_qsl(url.query, keep_blank_values=True)
        if table not in self.db:
            self.unexpected.append(f'rest bảng lạ {table}')
            return self.respond(route, 404, {'message': f'relation {table} does not exist'})
        rows = self.db[table]
        accept = req.headers.get('accept', '')
        prefer = req.headers.get('prefer', '')
        want_object = 'vnd.pgrst.object' in accept
        want_repr = 'return=representation' in prefer or req.method == 'GET'
        user = self.user_from_request(req)
        is_admin = bool(user and any(p['id'] == user['id'] and p['role'] == 'admin' for p in self.db['profiles']))

        if req.method == 'GET':
            result = self._filter(rows, params)
            if table == 'profiles':  # RLS tối thiểu: chỉ đọc hồ sơ của mình (admin đọc tất cả)
                result = [r for r in result if is_admin or (user and r['id'] == user['id'])]
            if table == 'comments' and not is_admin:
                result = [r for r in result if user and r.get('user_id') == user['id']]
            order = dict(params).get('order')
            if order:
                for part in reversed(order.split(',')):
                    col, _, direction = part.partition('.')
                    rev = direction.startswith('desc')
                    result = sorted(result, key=lambda r: (r.get(col) is None, str(r.get(col) or '')), reverse=rev)
            limit = dict(params).get('limit')
            if limit:
                result = result[:int(limit)]
            return self._reply_rows(route, copy.deepcopy(result), want_object)

        if req.method in ('POST', 'PATCH', 'DELETE') and table not in ('comments', 'messages',
                                                                         'academic_chat_messages', 'profiles') \
                and not is_admin:
            return self.respond(route, 401, {'code': '42501', 'message': 'permission denied (kiểm thử)'})

        body = json.loads(req.post_data or 'null')
        self.writes.append((req.method, table, body))
        if req.method == 'POST':
            items = body if isinstance(body, list) else [body]
            key = KEYS.get(table)
            upsert = 'resolution=' in prefer
            ignore = 'ignore-duplicates' in prefer
            saved = []
            for item in items:
                new = dict(DEFAULTS.get(table, {}), **item)
                if table in UUID_TABLES and not new.get('id'):
                    new['id'] = str(uuid.uuid4())
                new.setdefault('created_at', now_iso())
                existing = next((r for r in rows if key and r.get(key) == new.get(key)), None)
                if existing:
                    if not upsert:
                        return self.respond(route, 409, {'code': '23505', 'message': 'duplicate key value'})
                    if not ignore:
                        existing.update(item)
                    saved.append(existing)
                    continue
                if table == 'assignments' and any(
                        r.get('deleted_at') is None and str(r.get('assignment_date')) == str(new.get('assignment_date'))
                        and int(r.get('assignment_number') or 0) == int(new.get('assignment_number') or 0) for r in rows):
                    return self.respond(route, 409, {'code': '23505',
                                                     'message': 'duplicate key value violates unique constraint '
                                                                '"assignments_date_assignment_number_uidx"'})
                rows.append(new)
                saved.append(new)
            return self._reply_rows(route, copy.deepcopy(saved), want_object, 201, want_repr)
        if req.method == 'PATCH':
            if table == 'comments' and not is_admin:
                return self.respond(route, 401, {'code': '42501', 'message': 'permission denied'})
            matched = self._filter(rows, params)
            for r in matched:
                r.update(body or {})
            return self._reply_rows(route, copy.deepcopy(matched), want_object, 200, want_repr)
        if req.method == 'DELETE':
            matched = self._filter(rows, params)
            self.db[table] = [r for r in rows if r not in matched]
            return self._reply_rows(route, copy.deepcopy(matched), want_object, 200, want_repr)
        return self.respond(route, 405, {'message': 'method'})

    def _reply_rows(self, route, rows, want_object, status=200, want_repr=True):
        if not want_repr:
            return route.fulfill(status=204, headers=self.cors())
        if want_object:
            if len(rows) != 1:
                return self.respond(route, 406, {'code': 'PGRST116', 'details': f'{len(rows)} rows',
                                                 'message': 'JSON object requested, multiple (or no) rows returned'})
            return self.respond(route, status, rows[0])
        return self.respond(route, status, rows, {'content-range': f'0-{max(len(rows) - 1, 0)}/{len(rows)}'})

    # ---------- Storage ----------
    def storage_api(self, route, req, url):
        path = unquote(url.path[len('/storage/v1/'):])
        if path.startswith('object/sign/'):
            bucket, _, key = path[len('object/sign/'):].partition('/')
            return self.respond(route, 200, {'signedURL': f'/object/sign/{bucket}/{key}?token=kiemthu'})
        if path.startswith('object/public/') and req.method == 'GET':
            bucket, _, key = path[len('object/public/'):].partition('/')
            if (bucket, key) in self.storage:  # file vừa tải lên trong lúc kiểm thử
                return route.fulfill(status=200, body=self.storage[(bucket, key)][1],
                                     headers=dict(self.cors(), **{'content-type': self.storage[(bucket, key)][0]}))
            return route.fulfill(status=404, headers=self.cors())  # file của dữ liệu thật: không tải
        if path.startswith('object/') and req.method in ('POST', 'PUT'):
            bucket, _, key = path[len('object/'):].partition('/')
            self.storage[(bucket, key)] = (req.headers.get('content-type', 'application/octet-stream'),
                                           req.post_data_buffer or b'')
            self.writes.append(('UPLOAD', bucket, key))
            return self.respond(route, 200, {'Key': f'{bucket}/{key}', 'Id': str(uuid.uuid4())})
        if path.startswith('object/') and req.method == 'DELETE':
            bucket = path[len('object/'):].strip('/')
            prefixes = (json.loads(req.post_data or '{}') or {}).get('prefixes', [])
            for k in prefixes:
                self.storage.pop((bucket, k), None)
            self.writes.append(('REMOVE', bucket, prefixes))
            return self.respond(route, 200, [{'name': k} for k in prefixes])
        self.unexpected.append(f'storage {req.method} {path}')
        return self.respond(route, 404, {'message': 'not found'})

    # ---------- Edge Functions ----------
    def functions(self, route, req, url):
        name = url.path[len('/functions/v1/'):]
        body = json.loads(req.post_data or '{}')
        if name in self.fail_functions:
            return self.respond(route, 500, {'error': 'lỗi giả lập'})
        if name == 'geo-ai':
            return self.respond(route, 200, {'answer': f'Trả lời giả lập cho: {body.get("message", "")}',
                                             'mode': 'site', 'sources': ['Dữ liệu kiểm thử']})
        if name == 'signup-no-confirm':
            email = str(body.get('email', '')).lower()
            if email in self.users:
                return self.respond(route, 400, {'error': 'Email này đã được đăng ký.'})
            u = self.add_user(email, body.get('password', ''), body.get('name', ''))
            self.writes.append(('SIGNUP', 'auth.users', email))
            return self.respond(route, 201, {'ok': True, 'user_id': u['id']})
        if name == 'admin-user-management':
            u = self.user_from_request(req)
            if not u or u['role'] != 'admin':
                return self.respond(route, 403, {'error': 'Bạn không có quyền quản trị tài khoản.'})
            action = body.get('action', 'list')
            if action == 'list':
                return self.respond(route, 200, {'users': [
                    {'id': x['id'], 'email': x['email'], 'name': x['name'], 'role': x['role'],
                     'emailConfirmed': x['confirmed'], 'createdAt': x['created_at'], 'lastSignInAt': None,
                     'isCurrentAdmin': x['id'] == u['id']} for x in self.users.values()]})
            target = next((x for x in self.users.values() if x['id'] == body.get('userId')), None)
            if not target:
                return self.respond(route, 400, {'error': 'Thiếu tài khoản cần xử lý.'})
            self.writes.append(('ACCOUNT', action, target['email']))
            if action == 'confirm':
                target['confirmed'] = True
                return self.respond(route, 200, {'ok': True})
            if action == 'delete':
                if target['role'] == 'admin':
                    return self.respond(route, 403, {'error': 'Tài khoản Admin được bảo vệ.'})
                del self.users[target['email']]
                return self.respond(route, 200, {'ok': True})
        self.unexpected.append(f'function {name}')
        return self.respond(route, 404, {'error': 'not found'})
