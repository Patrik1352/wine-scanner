#!/usr/bin/env python3
"""Password-protected reverse proxy for the public wine scanner."""

import base64
import http.client
import io
import os
import uuid
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8766"))
UPSTREAM_HOST = os.environ.get("UPSTREAM_HOST", "127.0.0.1")
UPSTREAM_PORT = int(os.environ.get("UPSTREAM_PORT", "3001"))
LABELER_PORT = int(os.environ.get("LABELER_PORT", "8767"))
USER = os.environ.get("LABELER_USER", "")
PASSWORD = os.environ.get("LABELER_PASSWORD", "")

HOP_BY_HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers", "transfer-encoding", "upgrade"}


class Proxy(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _authorized(self):
        if not USER and not PASSWORD:
            return True
        expected = "Basic " + base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()
        return self.headers.get("Authorization") == expected

    def _reject(self):
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Wine labeler"')
        self.send_header("Content-Length", "0")
        self.end_headers()

    @staticmethod
    def _request_upstream(method, path, body, headers, port=UPSTREAM_PORT):
        connection = http.client.HTTPConnection(UPSTREAM_HOST, port, timeout=90)
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            return response.status, response.reason, response.getheaders(), response.read()
        finally:
            connection.close()

    @staticmethod
    def _jpeg_multipart(content_type, body):
        """Convert the `image` field of a rejected HEIF upload to JPEG."""
        if not content_type.startswith('multipart/form-data'):
            return None
        try:
            from PIL import Image
            import pillow_heif

            message = BytesParser(policy=policy.default).parsebytes(
                f'Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n'.encode() + body
            )
            image_part = next(
                part for part in message.iter_parts()
                if part.get_param('name', header='content-disposition') == 'image'
            )
            source = image_part.get_payload(decode=True)
            pillow_heif.register_heif_opener()
            with Image.open(io.BytesIO(source)) as image:
                if image.mode not in ('RGB', 'L'):
                    image = image.convert('RGB')
                output = io.BytesIO()
                image.save(output, format='JPEG', quality=90, optimize=True)
            original_name = image_part.get_filename() or 'photo'
            base = os.path.splitext(os.path.basename(original_name))[0] or 'photo'
            boundary = f'----WineScanner{uuid.uuid4().hex}'
            payload = output.getvalue()
            rebuilt = (
                f'--{boundary}\r\n'
                f'Content-Disposition: form-data; name="image"; filename="{base}.jpg"\r\n'
                'Content-Type: image/jpeg\r\n\r\n'
            ).encode() + payload + f'\r\n--{boundary}--\r\n'.encode()
            return f'multipart/form-data; boundary={boundary}', rebuilt
        except Exception as error:
            print(f'HEIF fallback conversion skipped: {error}', flush=True)
            return None

    def _forward(self):
        if not self._authorized():
            self._reject()
            return
        if self.path in ('/label-new', '/label-models', '/label-disputes'):
            self.send_response(308)
            self.send_header('Location', self.path + '/')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        prefix = next((p for p in ('/label-new', '/label-models', '/label-disputes') if self.path.startswith(p + '/')), None)
        port = 8769 if prefix == '/label-disputes' else 8768 if prefix == '/label-models' else LABELER_PORT if prefix else UPSTREAM_PORT
        target_path = self.path[len(prefix):] if prefix else self.path
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else None
        headers = {key: value for key, value in self.headers.items() if key.lower() not in HOP_BY_HOP | {"host"}}
        headers["Host"] = f"{UPSTREAM_HOST}:{port}"
        status, reason, response_headers, payload = self._request_upstream(self.command, target_path, body, headers, port)
        if status in (415, 422) and target_path.startswith('/v1/recognize'):
            converted = self._jpeg_multipart(headers.get('Content-Type', ''), body or b'')
            if converted:
                headers['Content-Type'], body = converted
                headers['Content-Length'] = str(len(body))
                status, reason, response_headers, payload = self._request_upstream(self.command, target_path, body, headers, port)
        self.send_response(status, reason)
        for key, value in response_headers:
            if key.lower() not in HOP_BY_HOP | {"content-length"}:
                self.send_header(key, value)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    do_GET = _forward
    do_POST = _forward
    do_PUT = _forward
    do_PATCH = _forward
    do_DELETE = _forward
    do_OPTIONS = _forward

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)


if __name__ == "__main__":
    print(f"Proxying http://{HOST}:{PORT} to http://{UPSTREAM_HOST}:{UPSTREAM_PORT}", flush=True)
    ThreadingHTTPServer((HOST, PORT), Proxy).serve_forever()
