"""Local-only Ollama transport for BreastCare educational agents.

The URL is deliberately restricted to loopback so case data is never sent to
an external OpenAI endpoint or a remote URL by misconfiguration.
"""
import json
import os
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


def configuration():
    endpoint = os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434').rstrip('/')
    parsed = urlparse(endpoint)
    if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost', '::1') or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
        raise ValueError('OLLAMA_BASE_URL phải là địa chỉ HTTP loopback cục bộ, ví dụ http://127.0.0.1:11434')
    model = os.getenv('OLLAMA_MODEL', 'breastcare-vn:latest').strip()
    if not model or len(model) > 120:
        raise ValueError('OLLAMA_MODEL không hợp lệ')
    return endpoint, model


def chat(messages, max_tokens=1300):
    endpoint, model = configuration()
    body = {'model': model, 'messages': messages, 'stream': False, 'think': False,
            'format': 'json', 'options': {'temperature': 0.2, 'num_predict': max_tokens, 'num_ctx': int(os.getenv('OLLAMA_NUM_CTX', '4096'))}}
    request = Request(endpoint + '/api/chat', data=json.dumps(body, ensure_ascii=False).encode('utf-8'),
                      method='POST', headers={'Content-Type': 'application/json; charset=utf-8'})
    try:
        with urlopen(request, timeout=float(os.getenv('OLLAMA_TIMEOUT', '105'))) as result:
            response = json.load(result)
    except HTTPError as exc:
        raise RuntimeError(f'Ollama trả lỗi HTTP {exc.code}') from None
    except (URLError, TimeoutError) as exc:
        raise RuntimeError('Không kết nối được Ollama cục bộ; kiểm tra Ollama đã chạy và đủ RAM') from exc
    if response.get('done_reason') == 'length':
        raise ValueError('Ollama hết giới hạn token trước khi hoàn thành JSON; thử mô hình Instruct và giảm ngữ cảnh.')
    text = (response.get('message') or {}).get('content') or ''
    if not text.strip():
        raise ValueError('Ollama trả về câu trả lời rỗng')
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError('Ollama không trả về JSON hợp lệ') from exc


def status():
    endpoint, model = configuration()
    request = Request(endpoint + '/api/tags', headers={'Accept': 'application/json'})
    try:
        with urlopen(request, timeout=3) as response:
            names = [m.get('name', '') for m in json.load(response).get('models', [])]
        return model in names or (model + ':latest') in names
    except (OSError, ValueError, KeyError):
        return False
