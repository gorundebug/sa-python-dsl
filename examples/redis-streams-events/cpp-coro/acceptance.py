"""Run the generated graph; use official hiredis solely for broker inspection."""

import json
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

root = Path(sys.argv[1]).resolve()
url = os.environ.get("REDIS_STREAMS_TEST_URL", "redis://host.docker.internal:16379")
parsed = urlsplit(url)
assert parsed.scheme == "redis" and not parsed.username and not parsed.password
if parsed.hostname in ("localhost", "127.0.0.1"):
    url = urlunsplit(
        ("redis", "host.docker.internal:" + str(parsed.port or 6379), "", "", "")
    )
    parsed = urlsplit(url)
suffix = uuid.uuid4().hex
incoming, outgoing = f"canonical:coro:{suffix}:in", f"canonical:coro:{suffix}:out"
env = dict(os.environ, PEER_HOST=parsed.hostname, PEER_PORT=str(parsed.port or 6379))
env.update(
    EVENTS_SERVERS=url,
    EVENTS_PASSWORD=env.get("REDIS_STREAMS_TEST_PASSWORD", "adapter-test"),
    EVENTS_USERNAME="",
    RECEIVE_EVENT_STREAM_KEY=incoming,
    PUBLISH_EVENT_STREAM_KEY=outgoing,
    EVENT_PROCESSOR_HTTP_PORT="0",
    EVENT_PROCESSOR_GRPC_PORT="0",
    SERVICELIB_NOOP_METRICS="1",
    SERVICELIB_NOOP_LOGS="1",
    SERVICELIB_NOOP_TRACING="1",
)
peer = root / "build/canonical-probe"
log = root / "service.log"


def inspect(mode):
    return subprocess.run(
        [str(peer), mode, incoming, outgoing],
        env=env,
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    ).stdout


def wait_for(check, seconds=30):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        assert process.poll() is None, f"service exited: {log.read_text()}"
        try:
            value = check()
            if value:
                return value
        except subprocess.CalledProcessError:
            pass
        time.sleep(0.05)
    raise AssertionError(f"acceptance timed out: {log.read_text()}")


def records():
    rows = []
    for line in inspect("observe").splitlines():
        cells = [bytes.fromhex(cell).decode() for cell in line.split("\t")]
        rows.append((cells[0], list(zip(cells[1::2], cells[2::2]))))
    return rows if len(rows) == 3 else None


def outcomes():
    rows = []
    for line in log.read_text().splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and "EventID" in row:
            rows.append(row)
    return rows if len(rows) == 3 else None


process = None
try:
    with log.open("w") as output:
        binary = root / "build/eventprocessor/redis_streams_events_event_processor"
        if not binary.exists():
            candidates = list(
                (root / "build").rglob("redis_streams_events_event_processor")
            )
            assert len(candidates) == 1, candidates
            binary = candidates[0]
        process = subprocess.Popen(
            [str(binary)],
            cwd=root / "eventprocessor",
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
        )
        wait_for(lambda: inspect("ready") == "")
        inspect("seed")
        entries = wait_for(records)
        results = wait_for(outcomes)
        expected = {f"event-{i}" for i in range(3)}
        by_event = {}
        for entry_id, fields in entries:
            data = dict(fields)
            assert len([k for k, _ in fields if k == "ID"]) == 1
            assert data["Value"] == "HELLO", fields
            assert data["x-stream-id"] == "source-" + data["ID"], fields
            assert data["ID"] not in by_event
            by_event[data["ID"]] = entry_id
        assert set(by_event) == expected
        assert {r["EventID"] for r in results} == expected
        for result in results:
            assert result["Accepted"] is True and result["Reason"] == "", result
            assert result["EntryID"] == by_event[result["EventID"]], result
        wait_for(lambda: inspect("pending").strip() == "0")
        started = time.monotonic()
        process.send_signal(signal.SIGTERM)
        assert process.wait(timeout=8) == 0, log.read_text()
        evidence = {
            "records": entries,
            "outcomes": results,
            "pending": 0,
            "exit_code": process.returncode,
            "stop_ms": (time.monotonic() - started) * 1000,
            "input_key": incoming,
            "output_key": outgoing,
        }
        (root / "acceptance.results.json").write_text(
            json.dumps(evidence, indent=2) + "\n"
        )
        print(
            "PASS: generated RedisStreams Coro: 3 normalized records, correlated entry IDs, explicit ACK, clean SIGTERM"
        )
finally:
    if process is not None and process.poll() is None:
        process.kill()
        process.wait(timeout=5)
    inspect("clean")
