"""Host-driven acceptance of an already-built generated runtime image.

Only test-owned containers/topics are removed. No Docker socket is mounted, and
neither the shared broker nor its configuration is changed.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def docker(*args, timeout=15):
    result = subprocess.run(
        ["docker", *args], capture_output=True, text=True, timeout=timeout
    )
    if result.returncode:
        raise RuntimeError(f"docker {args[0]} failed: {result.stderr}")
    return result.stdout.strip()


def main():
    project = Path(sys.argv[1]).resolve()
    image = os.environ.get("PULSAR_RUNTIME_IMAGE", "sa-pulsar-coro-canonical:arm64")
    platform = os.environ.get("PULSAR_RUNTIME_PLATFORM", "linux/arm64")
    peer_image = os.environ.get("PULSAR_PEER_IMAGE", "cppcoroservicelib-build:latest")
    peer_platform = os.environ.get("PULSAR_PEER_PLATFORM", platform)
    prefix = Path(os.environ["PULSAR_NATIVE_PREFIX"]).resolve()
    probe = Path(
        os.environ.get("PULSAR_NATIVE_PROBE", project / "build/canonical-probe")
    ).resolve()
    assert probe.is_file() and (prefix / "lib").is_dir(), (
        "prebuilt native peer and official libraries required"
    )
    broker = os.environ.get("PULSAR_BROKER_CONTAINER", "servicelib-pulsar-acceptance")
    admin_url = os.environ.get(
        "PULSAR_TEST_ADMIN_URL", "http://127.0.0.1:18080"
    ).rstrip("/")
    native_url = os.environ.get("PULSAR_CONTAINER_URL", "pulsar://127.0.0.1:16650")
    container_admin = os.environ.get(
        "PULSAR_CONTAINER_ADMIN_URL", "http://127.0.0.1:18080"
    )
    inspected = json.loads(docker("image", "inspect", image))[0]
    image_id = inspected["Id"]
    assert inspected["Os"] + "/" + inspected["Architecture"] == platform, (
        "runtime image architecture mismatch"
    )
    assert json.loads(docker("inspect", broker))[0]["State"]["Running"], (
        "shared broker must already be running"
    )
    identity = uuid.uuid4().hex
    namespace = "public/coro-image-" + identity
    runtime, peer = "coro-runtime-" + identity, "coro-peer-" + identity
    incoming, outgoing = [
        f"persistent://{namespace}/{name}" for name in ("incoming", "processed")
    ]
    log_path = project / "image-acceptance.service.log"

    def admin(method, path, body=None):
        request = Request(
            admin_url + path,
            method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=5) as response:
                data = response.read()
                return json.loads(data) if data else None
        except HTTPError as error:
            if method == "DELETE" and error.code == 404:
                return None
            raise

    def state():
        return json.loads(docker("inspect", runtime))[0]["State"]

    def logs():
        # Capture both streams: native logging may use stderr.
        result = subprocess.run(
            ["docker", "logs", runtime], capture_output=True, text=True, timeout=5
        )
        text = result.stdout + result.stderr
        log_path.write_text(text)
        return text

    def until(predicate):
        deadline = time.monotonic() + 30
        while not predicate():
            assert state()["Running"], logs()
            if time.monotonic() >= deadline:
                raise TimeoutError(logs())
            time.sleep(0.1)

    def ready():
        try:
            source = admin("GET", f"/admin/v2/persistent/{namespace}/incoming/stats")
            sink = admin("GET", f"/admin/v2/persistent/{namespace}/processed/stats")
            return (
                source["subscriptions"].get("event_processors", {}).get("consumers")
                and sink["publishers"]
            )
        except HTTPError as error:
            if error.code == 404:
                return False
            raise

    created = False
    try:
        admin("PUT", "/admin/v2/namespaces/" + namespace, {})
        created = True
        for policy, field in [
            ("autoTopicCreation", "allowAutoTopicCreation"),
            ("autoSubscriptionCreation", "allowAutoSubscriptionCreation"),
        ]:
            admin("POST", f"/admin/v2/namespaces/{namespace}/{policy}", {field: False})
        env = dict(
            EVENTS_SERVERS=native_url,
            EVENTS_ADMIN_URL=container_admin,
            RECEIVE_EVENT_TOPIC=incoming,
            PUBLISH_EVENT_TOPIC=outgoing,
            EVENT_PROCESSOR_HTTP_PORT="0",
            EVENT_PROCESSOR_GRPC_PORT="0",
            SERVICELIB_NOOP_LOGS="1",
            SERVICELIB_NOOP_METRICS="1",
            SERVICELIB_NOOP_TRACING="1",
        )
        args = [
            "run",
            "--detach",
            "--name",
            runtime,
            "--platform",
            platform,
            "--network",
            "container:" + broker,
        ]
        for key, value in env.items():
            args.extend(["--env", key + "=" + value])
        # Run the image's own ENTRYPOINT/config/libs, with no source/binary mounts.
        docker(*args, image_id)
        until(ready)
        admin(
            "PUT",
            f"/admin/v2/persistent/{namespace}/processed/subscription/canonical_observer",
            {"ledgerId": -1, "entryId": -1},
        )
        output = docker(
            "run",
            "--name",
            peer,
            "--platform",
            peer_platform,
            "--network",
            "container:" + broker,
            "--mount",
            f"type=bind,src={probe},dst=/probe,readonly",
            "--mount",
            f"type=bind,src={prefix},dst=/pulsar,readonly",
            "--env",
            "LD_LIBRARY_PATH=/pulsar/lib",
            "--entrypoint",
            "/probe",
            peer_image,
            native_url,
            incoming,
            outgoing,
            timeout=25,
        )
        (project / "image-acceptance.peer.log").write_text(output + "\n")
        records = [
            json.loads(line) for line in output.splitlines() if line.startswith("{")
        ]
        assert len(records) == 3, records
        by_id = {record["payload"]["ID"]: record for record in records}
        assert set(by_id) == {f"event-{i}" for i in range(3)}, records
        for key, record in by_id.items():
            assert record["payload"] == {"ID": key, "Value": "HELLO"}, record
            assert record["key"] == key and record["MessageID"], record

        def outcomes():
            return [
                json.loads(line)
                for line in logs().splitlines()
                if line.startswith("{") and '"Accepted"' in line
            ]

        until(lambda: len(outcomes()) == 3)
        observed = outcomes()
        assert {value["EventID"] for value in observed} == set(by_id), observed
        for value in observed:
            assert value == dict(
                EventID=value["EventID"],
                MessageID=by_id[value["EventID"]]["MessageID"],
                Accepted=True,
                Reason="",
            ), value

        def settled():
            stats = admin("GET", f"/admin/v2/persistent/{namespace}/incoming/stats")[
                "subscriptions"
            ]["event_processors"]
            return stats["msgBacklog"] == 0 and stats["unackedMessages"] == 0

        until(settled)
        started = time.monotonic()
        docker("kill", "--signal", "TERM", runtime, timeout=3)
        exit_code = int(
            docker("wait", runtime, timeout=max(0.1, 8 - (time.monotonic() - started)))
        )
        elapsed = time.monotonic() - started
        assert exit_code == 0 and elapsed <= 8, (exit_code, elapsed, logs())
        logs()
        (project / "image-acceptance.results.json").write_text(
            json.dumps(
                dict(
                    image=image,
                    imageId=image_id,
                    platform=platform,
                    peerImage=peer_image,
                    peerPlatform=peer_platform,
                    records=records,
                    outcomes=observed,
                    sourceAcked=True,
                    exitCode=exit_code,
                    stopSeconds=elapsed,
                ),
                indent=2,
            )
        )
        print(
            "PASS: generated Pulsar Coro runtime image: three normalized outputs, native MessageId correlation, explicit ACK and clean SIGTERM"
        )
    except BaseException:
        try:
            print(logs(), file=sys.stderr)
        except Exception:
            pass  # Preserve the original failure if the container never started.
        raise
    finally:
        # Failure cleanup is not counted as graceful stop; never targets broker.
        for name in (peer, runtime):
            subprocess.run(
                ["docker", "rm", "--force", name], capture_output=True, timeout=10
            )
        if created:
            for topic in ("incoming", "processed"):
                admin("DELETE", f"/admin/v2/persistent/{namespace}/{topic}?force=true")
            admin("DELETE", "/admin/v2/namespaces/" + namespace)


if __name__ == "__main__":
    main()
