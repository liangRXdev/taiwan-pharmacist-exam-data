"""HTTP 存取與結果分類（spec §5.2）。每次請求獨立、不帶 cookie，避免站方 session 狀態跨請求沿用。"""

import time
from dataclasses import dataclass

import requests

from ..config import REQUEST_INTERVAL_S, REQUEST_TIMEOUT_S, RETRIES, USER_AGENT


class Retryable(RuntimeError):
    """重試後仍失敗：本次 run 必須中止且不得修改 manifest。"""


class Unusable(RuntimeError):
    """回應可取得但內容不可用：對應科目 parked。"""


@dataclass
class Response:
    url: str
    status: int
    final_url: str
    content_type: str
    content: bytes


_last_request = 0.0


def _throttle() -> None:
    global _last_request
    wait = _last_request + REQUEST_INTERVAL_S - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()


def get(url: str) -> Response:
    """不跟隨 redirect：站方以 302 表示檔案不存在，redirect 本身即為證據。"""
    last_err: Exception | None = None
    for attempt in range(RETRIES):
        _throttle()
        try:
            r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT_S, allow_redirects=False)
        except requests.RequestException as e:
            last_err = e
        else:
            if r.status_code == 429 or r.status_code >= 500:
                last_err = RuntimeError(f"HTTP {r.status_code}")
            else:
                return Response(url, r.status_code, r.headers.get("Location") or url, r.headers.get("Content-Type", ""), r.content)
        time.sleep(2 ** attempt * 5)
    raise Retryable(f"{url}：重試 {RETRIES} 次仍失敗（{last_err}）")


def get_pdf(url: str) -> bytes:
    r = get(url)
    if r.status != 200:
        raise Unusable(f"{url}：HTTP {r.status}（Location={r.final_url}）")
    if "pdf" not in r.content_type.lower():
        raise Unusable(f"{url}：Content-Type={r.content_type!r}")
    if not r.content.startswith(b"%PDF-") or b"%%EOF" not in r.content[-2048:]:
        raise Unusable(f"{url}：非完整 PDF（{len(r.content)} bytes）")
    return r.content
