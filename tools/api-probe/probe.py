"""Run the HTTP requests listed in plan.json against the Potravinator backend
and write every response (status, headers, body) to docs/api-snapshot/<run>/.

Exists because the development container cannot reach *.potravinator.cz; the
GitHub Actions runner can. Requests are executed in order, and a step may
reference values captured from earlier responses as {{name}}.
"""
import json, os, re, sys, time, urllib.error, urllib.request

plan = json.load(open(os.path.join(os.path.dirname(__file__), 'plan.json')))
run = plan.get('run', 'run')
out = os.path.join('docs', 'api-snapshot', run)
os.makedirs(out, exist_ok=True)
vars_ = dict(plan.get('vars', {}))
index = []

def fill(s):
    return re.sub(r'\{\{(\w+)\}\}', lambda m: str(vars_.get(m.group(1), m.group(0))), s) if isinstance(s, str) else s

def dig(obj, path):
    for p in path.split('.'):
        if isinstance(obj, list):
            obj = obj[int(p)] if p.isdigit() and int(p) < len(obj) else None
        elif isinstance(obj, dict):
            obj = obj.get(p)
        else:
            return None
    return obj

for i, step in enumerate(plan['steps']):
    name = step['name']
    url = fill(step['url'] if step['url'].startswith('http') else plan['base'] + step['url'])
    method = step.get('method', 'GET')
    headers = {k: fill(v) for k, v in {**plan.get('headers', {}), **step.get('headers', {})}.items()}
    data = None
    if 'json' in step:
        data = json.dumps(json.loads(fill(json.dumps(step['json'])))).encode()
        headers.setdefault('Content-Type', 'application/json')
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            status, rh, body = r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        status, rh, body = e.code, dict(e.headers), e.read()
    except Exception as e:
        status, rh, body = 0, {}, repr(e).encode()
    ms = int((time.time() - t) * 1000)
    base = f'{i:02d}_{name}'
    open(os.path.join(out, base + '.body'), 'wb').write(body)
    parsed = None
    try:
        parsed = json.loads(body)
    except Exception:
        pass
    for var, path in step.get('capture', {}).items():
        v = dig(parsed, path) if parsed is not None else None
        if v is not None:
            vars_[var] = v
    if 'capture_header' in step:
        for var, h in step['capture_header'].items():
            for k, v in rh.items():
                if k.lower() == h.lower():
                    vars_[var] = v
    index.append({'i': i, 'name': name, 'method': method, 'url': url,
                  'req_headers': headers, 'req_body': data.decode() if data else None,
                  'status': status, 'ms': ms, 'bytes': len(body),
                  'content_type': rh.get('Content-Type') or rh.get('content-type'),
                  'resp_headers': rh})
    print(f'{i:02d} {method:6} {status} {len(body):>8}B {ms:>5}ms  {name:28} {url}')

json.dump({'vars': vars_, 'requests': index}, open(os.path.join(out, '_index.json'), 'w'),
          indent=2, ensure_ascii=False)
