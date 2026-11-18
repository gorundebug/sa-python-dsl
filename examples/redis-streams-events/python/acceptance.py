"""Regenerated Python graph acceptance; only unique test keys are removed."""

import json
import os
import subprocess
import sys
import tempfile
import time
import uuid

from redis import Redis
from redis.backoff import NoBackoff
from redis.retry import Retry


def main():
    address = os.environ["REDIS_STREAMS_TEST_URL"]
    password = os.environ.get("REDIS_STREAMS_TEST_PASSWORD", "adapter-test")
    prefix = "sa-python-canonical-" + uuid.uuid4().hex
    incoming, outgoing = prefix + "-in", prefix + "-out"
    env = dict(
        os.environ,
        EVENTS_SERVERS=address,
        EVENTS_PASSWORD=password,
        EVENTS_USERNAME="",
        RECEIVE_EVENT_STREAM_KEY=incoming,
        PUBLISH_EVENT_STREAM_KEY=outgoing,
        EVENT_PROCESSOR_HTTP_PORT="0",
        SERVICELIB_NOOP_METRICS="1",
        SERVICELIB_NOOP_LOGS="1",
        SERVICELIB_NOOP_TRACING="1",
        PYTHONDONTWRITEBYTECODE="1",
    )
    # Exercise generated defaults and environment binding, without replacement config.
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import os
from event_processor.internal.config import Config
from pyservicelib_gorundebug.runtime.config import RedisStreamsDataConnectorConfig, RedisStreamsEndpointConfig
c = Config.from_dict({})
dc = c.named.data_connectors.events
source, sink = c.named.endpoints.receive_event, c.named.endpoints.publish_event
assert isinstance(dc, RedisStreamsDataConnectorConfig) and dc.type.value == 10
assert dc.servers == [os.environ['EVENTS_SERVERS']]
assert dc.password == os.environ['EVENTS_PASSWORD'] and dc.redis_database == 0
assert isinstance(source, RedisStreamsEndpointConfig) and isinstance(sink, RedisStreamsEndpointConfig)
assert source.stream_key == os.environ['RECEIVE_EVENT_STREAM_KEY']
assert sink.stream_key == os.environ['PUBLISH_EVENT_STREAM_KEY']
assert source.create_consumer_group is True and source.group_start_id == '0-0'
assert source.read_count == 16 and source.create_stream is None
assert sink.create_stream is True and sink.publisher_max_in_flight == 16
assert sink.consumer_group is None and sink.create_consumer_group is None
source.validate_role(True)
sink.validate_role(False)
""",
        ],
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert probe.returncode == 0, probe.stdout + probe.stderr
    admin = Redis.from_url(
        address,
        password=password,
        socket_connect_timeout=2,
        socket_timeout=2,
        retry=Retry(NoBackoff(), 0),
    )
    service = None
    with tempfile.TemporaryFile(mode="w+") as log:

        def logs():
            log.seek(0)
            return log.read()

        deadline = time.monotonic() + 25

        def wait(predicate):
            while not predicate():
                assert service.poll() is None, logs()
                assert time.monotonic() < deadline, logs()
                time.sleep(0.025)

        try:
            service = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "event_processor.main",
                    "--config",
                    "config/config.yaml",
                    "--values",
                    "config/overrides.yaml",
                ],
                env=env,
                stdout=log,
                stderr=log,
            )
            # Sinks start before source admission; group creation is in source startup.
            wait(lambda: admin.exists(incoming) == 1)
            for i in range(3):
                admin.xadd(incoming, {"ID": f"event-{i}", "Value": " hello "})
            wait(
                lambda: (
                    admin.xlen(outgoing) == 3
                    and admin.xpending(incoming, "event_processors")["pending"] == 0
                )
            )
            records = admin.xrange(outgoing)
            for i, (_, fields) in enumerate(records):
                assert (
                    fields[b"ID"] == f"event-{i}".encode()
                    and fields[b"Value"] == b"HELLO"
                )

            def outcomes():
                return [
                    json.loads(line)
                    for line in logs().splitlines()
                    if line.startswith("{") and '"Accepted"' in line
                ]

            wait(lambda: len(outcomes()) == 3)
            for i, outcome in enumerate(outcomes()):
                assert outcome == {
                    "EventID": f"event-{i}",
                    "EntryID": records[i][0].decode(),
                    "Accepted": True,
                    "Reason": "",
                }
            assert admin.xlen(incoming) == 3  # XACK does not delete stream entries.
            service.terminate()
            assert service.wait(timeout=8) == 0, logs()
            print(
                "PASS: generated Redis Python: 3 native normalized outputs, correlated XADD IDs, explicit XACK, environment overrides and clean shutdown"
            )
        except BaseException:
            print(logs(), file=sys.stderr)
            raise
        finally:
            if service and service.poll() is None:
                service.kill()
                service.wait(timeout=5)
            admin.delete(incoming, outgoing)
            admin.close()


if __name__ == "__main__":
    main()
