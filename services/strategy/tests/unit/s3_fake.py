"""A minimal S3 endpoint on localhost for tests that must reach MinIO from another process.

It answers the calls the `minio` client makes for `get_object` and `put_object` (bucket region,
object GET and PUT) and keeps objects in memory. Authentication is not checked.
"""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import TracebackType
from typing import Self
from urllib.parse import urlsplit

from minio import Minio

_NO_SUCH_KEY = (
    b'<?xml version="1.0" encoding="UTF-8"?><Error><Code>NoSuchKey</Code>'
    b"<Message>The specified key does not exist.</Message></Error>"
)
_LOCATION = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<LocationConstraint xmlns="http://s3.amazonaws.com/doc/2006-03-01/">us-east-1'
    b"</LocationConstraint>"
)


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def endpoint(self) -> str:
        host, port = self._server.server_address[:2]
        return f"{host!s}:{port}"

    def client(self) -> Minio:
        return Minio(self.endpoint, access_key="test", secret_key="test-secret", secure=False)

    def __enter__(self) -> Self:
        self._thread.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._server.shutdown()
        self._server.server_close()

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        objects = self.objects

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                pass

            def _target(self) -> tuple[str, str, str]:
                parts = urlsplit(self.path)
                bucket, _, key = parts.path.lstrip("/").partition("/")
                return bucket, key, parts.query

            def _send(self, status: int, body: bytes = b"") -> None:
                self.send_response(status)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("ETag", '"fake"')
                self.send_header("Content-Type", "application/xml")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:
                bucket, key, query = self._target()
                if not key and "location" in query:
                    self._send(200, _LOCATION)
                elif (bucket, key) in objects:
                    self._send(200, objects[(bucket, key)])
                else:
                    self._send(404, _NO_SUCH_KEY)

            def do_PUT(self) -> None:
                bucket, key, _ = self._target()
                length = int(self.headers.get("Content-Length", "0"))
                objects[(bucket, key)] = self.rfile.read(length)
                self._send(200)

        return Handler


