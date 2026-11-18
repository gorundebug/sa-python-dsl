"""Generated userver process + official native test peer; shared broker never restarted."""

import asyncio
import json
import os
from pathlib import Path
import signal
import sys
import uuid
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlsplit, urlunsplit

sys.path.insert(0, "/workspace/tests/pulsar_native")
from pulsar_proxy import PulsarProxy


def container_url(value):
    parsed = urlsplit(value)
    if parsed.hostname in ("localhost", "127.0.0.1"):
        return urlunsplit(
            (
                parsed.scheme,
                "host.docker.internal:" + str(parsed.port),
                parsed.path,
                parsed.query,
                parsed.fragment,
            )
        )
    return value


async def main():
    project = Path(sys.argv[1]).resolve()
    admin_url = container_url(
        os.environ.get("PULSAR_TEST_ADMIN_URL", "http://host.docker.internal:18080")
    )
    remote = container_url(
        os.environ.get("PULSAR_TEST_URL", "pulsar://host.docker.internal:16650")
    )
    namespace = "public/userver-canonical-" + uuid.uuid4().hex
    incoming, outgoing = [
        f"persistent://{namespace}/{name}" for name in ("incoming", "processed")
    ]

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

    admin("PUT", "/admin/v2/namespaces/" + namespace, {})
    service = peer = None
    log_path = project / "acceptance.service.log"
    try:
        for policy, field in [
            ("autoTopicCreation", "allowAutoTopicCreation"),
            ("autoSubscriptionCreation", "allowAutoSubscriptionCreation"),
        ]:
            admin("POST", f"/admin/v2/namespaces/{namespace}/{policy}", {field: False})
        async with PulsarProxy(remote) as proxy:
            env = dict(
                os.environ,
                EVENTS_SERVERS=proxy.url,
                EVENTS_ADMIN_URL=admin_url,
                RECEIVE_EVENT_TOPIC=incoming,
                PUBLISH_EVENT_TOPIC=outgoing,
                EVENT_PROCESSOR_HTTP_PORT="0",
                EVENT_PROCESSOR_GRPC_PORT="0",
                SERVICELIB_NOOP_LOGS="1",
                SERVICELIB_NOOP_METRICS="1",
                SERVICELIB_NOOP_TRACING="1",
            )
            with log_path.open("w") as log:
                service = await asyncio.create_subprocess_exec(
                    str(project / "build/eventprocessor/pulsar_events_event_processor"),
                    "--config", "static_config.yaml",
                    "--config_vars", "config/config_vars.yaml",
                    cwd=project / "eventprocessor",
                    env=env,
                    stdout=log,
                    stderr=log,
                )

                async def until(predicate):
                    async with asyncio.timeout(30):
                        while not predicate():
                            assert service.returncode is None, log_path.read_text()
                            await asyncio.sleep(0.025)

                def ready():
                    try:
                        sub = admin(
                            "GET", f"/admin/v2/persistent/{namespace}/incoming/stats"
                        )["subscriptions"].get("event_processors", {})
                        pub = admin(
                            "GET", f"/admin/v2/persistent/{namespace}/processed/stats"
                        )["publishers"]
                        return bool(sub.get("consumers")) and bool(pub)
                    except HTTPError as error:
                        if error.code == 404:
                            return False
                        raise

                await until(ready)
                admin(
                    "PUT",
                    f"/admin/v2/persistent/{namespace}/processed/subscription/canonical_observer",
                    {"ledgerId": -1, "entryId": -1},
                )
                peer = await asyncio.create_subprocess_exec(
                    str(project / "build/canonical-probe"),
                    proxy.url,
                    incoming,
                    outgoing,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(peer.communicate(), 20)
                assert peer.returncode == 0, stderr.decode()
                records = [
                    json.loads(line)
                    for line in stdout.decode().splitlines()
                    if line.startswith("{")
                ]
                assert len(records) == 3, records
                by_id = {record["payload"]["ID"]: record for record in records}
                assert set(by_id) == {f"event-{i}" for i in range(3)}, records
                for identity, record in by_id.items():
                    assert record["payload"] == {"ID": identity, "Value": "HELLO"}, (
                        record
                    )
                    assert record["key"] == identity and record["MessageID"], record

                def outcomes():
                    return [
                        json.loads(line)
                        for line in log_path.read_text().splitlines()
                        if line.startswith("{") and '"Accepted"' in line
                    ]

                await until(lambda: len(outcomes()) == 3)
                observed = outcomes()
                assert {v["EventID"] for v in observed} == set(by_id), observed
                for value in observed:
                    assert value == {
                        "EventID": value["EventID"],
                        "MessageID": by_id[value["EventID"]]["MessageID"],
                        "Accepted": True,
                        "Reason": "",
                    }, value

                def settled():
                    stats = admin(
                        "GET", f"/admin/v2/persistent/{namespace}/incoming/stats"
                    )["subscriptions"]["event_processors"]
                    return stats["msgBacklog"] == 0 and stats["unackedMessages"] == 0

                await until(settled)
                service.send_signal(signal.SIGTERM)
                assert await asyncio.wait_for(service.wait(), 8) == 0, (
                    log_path.read_text()
                )
                (project / "acceptance.results.json").write_text(
                    json.dumps(
                        {
                            "records": records,
                            "outcomes": observed,
                            "sourceAcked": True,
                            "exitCode": service.returncode,
                        },
                        indent=2,
                    )
                )
                print(
                    "PASS: generated Pulsar userver: three normalized outputs, native MessageId correlation, explicit ACK and clean SIGTERM"
                )
    except BaseException:
        if log_path.exists():
            print(log_path.read_text(), file=sys.stderr)
        raise
    finally:
        for process in (peer, service):
            if process and process.returncode is None:
                process.kill()
                await process.wait()
        for topic in ("incoming", "processed"):
            admin("DELETE", f"/admin/v2/persistent/{namespace}/{topic}?force=true")
        admin("DELETE", "/admin/v2/namespaces/" + namespace)


asyncio.run(main())
