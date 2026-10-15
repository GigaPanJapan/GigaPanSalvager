"""Bounded, retrying downloads from GigaPan's public hosts only."""
import email.utils
import re
import threading
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
import requests

ORIGINS = ('https://gigapan.com', 'http://gigapan.com', 'https://www.gigapan.com', 'http://www.gigapan.com')


def allowed_url(url):
    u = urlparse(url)
    return (u.scheme in ('http','https') and u.port in (None,80,443) and not u.username and not u.password
            and re.fullmatch(r'(?:www\.|static\.|tile[0-9]+\.)?gigapan\.(?:com|org)', u.hostname or '') is not None)


class Client:
    def __init__(self, attempts=3):
        self.attempts = attempts
        self.local = threading.local()
        self.cooldown = 0.0
        self.lock = threading.Lock()

    def session(self):
        if not hasattr(self.local, 'session'):
            self.local.session = requests.Session()
            self.local.session.headers['User-Agent'] = 'GigaPanSalvager/0.1 (public panorama preservation)'
        return self.local.session

    def get(self, url, attempts=None, limit=5_000_000):
        if not allowed_url(url):
            raise ValueError('許可されていない取得先です。')
        error = 'No response'
        for attempt in range(attempts or self.attempts):
            wait = self.cooldown - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            try:
                target = url
                for _ in range(4):
                    if not allowed_url(target):
                        raise ValueError('GigaPan 外へのリダイレクトを拒否しました。')
                    with self.session().get(target, timeout=(4,20), allow_redirects=False, stream=True) as response:
                        if response.status_code in (301,302,303,307,308):
                            target = urljoin(target,response.headers.get('Location',''))
                            continue
                        if response.status_code in (429,503):
                            value = response.headers.get('Retry-After','')
                            try:
                                delay = float(value)
                            except ValueError:
                                try:
                                    delay = (email.utils.parsedate_to_datetime(value)-datetime.now(timezone.utc)).total_seconds()
                                except (ValueError,TypeError):
                                    delay = min(30,2**(attempt+1))
                            # Honor bounded waits; a very long Retry-After ends this request.
                            if delay > 120:
                                raise RuntimeError(f'HTTP {response.status_code}; Retry-After={value}')
                            with self.lock:
                                self.cooldown = max(self.cooldown,time.monotonic()+max(0,delay))
                        response.raise_for_status()
                        chunks, size = [], 0
                        for part in response.iter_content(65536):
                            size += len(part)
                            if size > limit:
                                raise ValueError('レスポンスがサイズ上限を超えました。')
                            chunks.append(part)
                        return b''.join(chunks), {'url':target,'content_type':response.headers.get('Content-Type',''),
                              'last_modified':response.headers.get('Last-Modified'), 'etag':response.headers.get('ETag')}
                raise ValueError('リダイレクト回数が上限を超えました。')
            except requests.HTTPError as exc:
                error = str(exc)
                if exc.response is not None and exc.response.status_code in (401,403,404):
                    break
            except requests.RequestException as exc:
                error = str(exc)
            if attempt+1 < (attempts or self.attempts):
                time.sleep(min(8,2**attempt))
        raise RuntimeError(error)
