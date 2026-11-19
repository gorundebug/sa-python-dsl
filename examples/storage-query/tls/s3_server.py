"""Disposable TLS endpoint for native S3 HeadObject certificate checks only.

This is not an S3 emulator: operation/authorization tests use real MinIO.
"""
import http.server
import ssl


class Handler(http.server.BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200 if self.path == '/bucket/key' or (self.path == '/key' and self.headers.get('Host') == 'bucket.localhost:9443') else 404)
        self.send_header('Content-Length', '0')
        self.end_headers()


server = http.server.ThreadingHTTPServer(('0.0.0.0', 9443), Handler)
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain('/fixtures/server.pem', '/fixtures/key.pem')
server.socket = context.wrap_socket(server.socket, server_side=True)
server.serve_forever()
