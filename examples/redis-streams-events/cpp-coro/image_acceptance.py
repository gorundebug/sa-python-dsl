"""Host-orchestrated generated runtime image acceptance; no app/config mounts."""

import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path


def main():
    project = Path(sys.argv[1]).resolve()
    image = os.environ.get(
        "REDIS_STREAMS_RUNTIME_IMAGE", "sa-redis-coro-canonical:arm64"
    )
    platform = os.environ.get("REDIS_STREAMS_RUNTIME_PLATFORM", "linux/arm64")
    peer_image = os.environ.get(
        "REDIS_STREAMS_PEER_IMAGE", "cppcoroservicelib-build:latest"
    )
    peer_platform = os.environ.get("REDIS_STREAMS_PEER_PLATFORM", "linux/arm64")
    prefix = Path(os.environ["HIREDIS_NATIVE_PREFIX"]).resolve()
    probe = Path(
        os.environ.get("REDIS_STREAMS_NATIVE_PROBE", project / "build/canonical-probe")
    ).resolve()
    assert probe.is_file() and (prefix / "lib").is_dir(), (
        "compiled official hiredis peer required"
    )
    broker = os.environ.get(
        "REDIS_STREAMS_BROKER_CONTAINER", "servicelib-redis-streams-acceptance"
    )
    native_port = os.environ.get("REDIS_STREAMS_CONTAINER_PORT", "6379")
    password = os.environ.get("REDIS_STREAMS_TEST_PASSWORD", "adapter-test")
    docker_env = dict(
        os.environ, REDIS_STREAMS_TEST_PASSWORD=password, EVENTS_PASSWORD=password
    )

    def docker(*args, timeout=10):
        result = subprocess.run(
            ["docker", *args],
            env=docker_env,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
        )
        if result.returncode:
            # Never include Docker arguments/environment in diagnostics.
            raise RuntimeError(
                f"docker {args[0]} failed: {result.stderr.replace(password, '[redacted]') if password else result.stderr}"
            )
        return result.stdout.strip()

    inspected = json.loads(docker("image", "inspect", image))[0]
    image_id = inspected["Id"]
    assert inspected["Os"] + "/" + inspected["Architecture"] == platform
    assert json.loads(docker("inspect", broker))[0]["State"]["Running"]
    identity = uuid.uuid4().hex
    runtime, peer = "redis-coro-runtime-" + identity, "redis-coro-peer-" + identity
    incoming, outgoing = (
        f"canonical:coro:image:{identity}:in",
        f"canonical:coro:image:{identity}:out",
    )
    artifact_name = "image-acceptance." + platform.split("/")[-1]
    peer_started = runtime_started = False

    def logs():
        result = subprocess.run(
            ["docker", "logs", runtime],
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
        value = result.stdout + result.stderr
        assert not password or password not in value, (
            "credential appeared in runtime logs"
        )
        (project / (artifact_name + ".service.log")).write_text(value)
        return value

    def inspect(mode):
        return docker("exec", peer, "/probe", mode, incoming, outgoing, timeout=5)

    def until(check):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            state = json.loads(docker("inspect", runtime))[0]["State"]
            assert state["Running"], logs()
            value = check()
            if value:
                return value
            time.sleep(0.1)
        raise TimeoutError(logs())

    def ready():
        try:
            return inspect("ready") == ""
        except RuntimeError:
            return False

    def records():
        rows = []
        for line in inspect("observe").splitlines():
            cells = [bytes.fromhex(cell).decode() for cell in line.split("\t")]
            rows.append((cells[0], list(zip(cells[1::2], cells[2::2]))))
        return rows if len(rows) == 3 else None

    def outcomes():
        rows = []
        for line in logs().splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict) and "EventID" in row:
                rows.append(row)
        return rows if len(rows) == 3 else None

    try:
        docker(
            "run",
            "--detach",
            "--name",
            peer,
            "--platform",
            peer_platform,
            "--network",
            "container:" + broker,
            "--mount",
            f"type=bind,src={probe},dst=/probe,readonly",
            "--mount",
            f"type=bind,src={prefix},dst=/hiredis,readonly",
            "--env",
            "LD_LIBRARY_PATH=/hiredis/lib",
            "--env",
            "PEER_HOST=127.0.0.1",
            "--env",
            "PEER_PORT=" + native_port,
            "--env",
            "REDIS_STREAMS_TEST_PASSWORD",
            "--entrypoint",
            "sleep",
            peer_image,
            "infinity",
        )
        peer_started = True
        env = {
            "EVENTS_SERVERS": "redis://127.0.0.1:" + native_port,
            "EVENTS_USERNAME": "",
            "RECEIVE_EVENT_STREAM_KEY": incoming,
            "PUBLISH_EVENT_STREAM_KEY": outgoing,
            "EVENT_PROCESSOR_HTTP_PORT": "0",
            "EVENT_PROCESSOR_GRPC_PORT": "0",
            "SERVICELIB_NOOP_LOGS": "1",
            "SERVICELIB_NOOP_METRICS": "1",
            "SERVICELIB_NOOP_TRACING": "1",
        }
        args = [
            "run",
            "--detach",
            "--name",
            runtime,
            "--platform",
            platform,
            "--network",
            "container:" + broker,
            "--env",
            "EVENTS_PASSWORD",
        ]
        for key, value in env.items():
            args += ["--env", key + "=" + value]
        # No mounts and no entrypoint override: test the actual installed application.
        docker(*args, image_id)
        runtime_started = True
        until(ready)
        inspect("seed")
        entries = until(records)
        results = until(outcomes)
        by_event = {}
        for entry_id, fields in entries:
            data = dict(fields)
            assert len([key for key, _ in fields if key == "ID"]) == 1
            assert (
                data["Value"] == "HELLO"
                and data["x-stream-id"] == "source-" + data["ID"]
            ), fields
            assert data["ID"] not in by_event
            by_event[data["ID"]] = entry_id
        assert set(by_event) == {f"event-{i}" for i in range(3)}
        assert {result["EventID"] for result in results} == set(by_event)
        for result in results:
            assert result == {
                "EventID": result["EventID"],
                "EntryID": by_event[result["EventID"]],
                "Accepted": True,
                "Reason": "",
            }, result
        until(lambda: inspect("pending") == "0")
        started = time.monotonic()
        docker("kill", "--signal", "TERM", runtime, timeout=3)
        exit_code = int(
            docker("wait", runtime, timeout=max(0.1, 8 - (time.monotonic() - started)))
        )
        elapsed = time.monotonic() - started
        assert exit_code == 0 and elapsed <= 8, (exit_code, elapsed, logs())
        logs()
        (project / (artifact_name + ".results.json")).write_text(
            json.dumps(
                {
                    "image": image,
                    "imageId": image_id,
                    "platform": platform,
                    "peerImage": peer_image,
                    "peerPlatform": peer_platform,
                    "records": entries,
                    "outcomes": results,
                    "pending": 0,
                    "exitCode": exit_code,
                    "stopSeconds": elapsed,
                },
                indent=2,
            )
            + "\n"
        )
        print(
            "PASS: generated RedisStreams Coro runtime image: 3 normalized records, entry ID correlation, explicit ACK, clean SIGTERM"
        )
    except BaseException:
        if runtime_started:
            try:
                print(logs(), file=sys.stderr)
            except (OSError, subprocess.SubprocessError, AssertionError):
                print(
                    "Runtime diagnostic capture unavailable; preserving original failure",
                    file=sys.stderr,
                )
        raise
    finally:
        # Stop only the test-owned runtime before deleting keys; never restart broker.
        try:
            if runtime_started:
                docker("rm", "--force", runtime)
        finally:
            try:
                if peer_started:
                    inspect("clean")
            finally:
                if peer_started:
                    docker("rm", "--force", peer)


if __name__ == "__main__":
    main()
