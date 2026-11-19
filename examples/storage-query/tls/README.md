Public test-only CA and server certificate/key for disposable TLS acceptance. Never deploy these credentials. server.pem/key.pem serve localhost/127.0.0.1; ca.pem signs the server leaf; untrusted-ca.pem is unrelated and must be rejected. The CA private key is not needed or stored here.

`s3_server.py` serves a minimal HTTPS HeadObject response at `/bucket/key`
(port 9443) for native certificate-verification tests. It is not an S3 emulator;
use the real MinIO fixture for operation and authorization checks. Rust's native
TLS roots accept `SSL_CERT_FILE`; run trusted/untrusted cases in separate
processes so certificate caches cannot hide a configuration error.
