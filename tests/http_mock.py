"""Mock of HTTP responses returned by urllib.request.urlopen, used to test API clients.

Usage is similar to the responses library::

    @http_mock.activate
    def test_api():
        http_mock.add(http_mock.GET, url, json={'key': 'value'})
        ...
        assert http_mock.calls[0].request.body == 'expected body'

Responses are matched by method and URL without query string. When several responses are
registered for the same request, they are returned in order and the last one is repeated.
"""

import functools
import io
import json as json_module
import urllib.error
import urllib.parse
from dataclasses import dataclass
from email.message import Message
from typing import Any, List, Optional
from unittest.mock import patch

GET = 'GET'
POST = 'POST'


@dataclass
class Request:
    method: str
    url: str
    body: Optional[str]
    headers: dict


@dataclass
class Call:
    request: Request
    timeout: float


@dataclass
class _Response:
    method: str
    url: str
    status: int
    body: str


class _UrlopenResponse(io.BytesIO):
    def __init__(self, status: int, body: str):
        super().__init__(body.encode())
        self.status = status


_responses: List[_Response] = []
calls: List[Call] = []


def add(
    method: str,
    url: str,
    json: Any = None,
    body: str = '',
    status: int = 200,
    content_type: Optional[str] = None,  # accepted for compatibility, not used
) -> None:
    if json is not None:
        body = json_module.dumps(json)
    _responses.append(_Response(method, url, status, body))


def _urlopen(request, timeout):
    body = request.data.decode() if request.data is not None else None
    headers = {name.lower(): value for name, value in request.header_items()}
    calls.append(Call(Request(request.get_method(), request.full_url, body, headers), timeout))
    url = urllib.parse.urlsplit(request.full_url)._replace(query='').geturl()
    matches = [r for r in _responses if r.method == request.get_method() and r.url == url]
    if not matches:
        raise urllib.error.URLError(f'Connection refused by http_mock: {request.full_url}')
    response = matches[0]
    if len(matches) > 1:
        _responses.remove(response)
    if response.status >= 400:
        raise urllib.error.HTTPError(
            request.full_url,
            response.status,
            'Error',
            Message(),
            io.BytesIO(response.body.encode()),
        )
    return _UrlopenResponse(response.status, response.body)


def activate(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        _responses.clear()
        calls.clear()
        try:
            with patch('urllib.request.urlopen', _urlopen):
                return func(*args, **kwargs)
        finally:
            _responses.clear()
            calls.clear()

    return wrapper
