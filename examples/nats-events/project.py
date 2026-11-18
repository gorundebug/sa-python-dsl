"""Native NATS Core and JetStream event processing; generated handlers are contracts.

Each input owns a separate pipeline. The publication outcome returns to that
input; transport acknowledgment is an explicit endpoint implementation decision.
"""
from sa_dsl import Function, Golang, LOCAL_MODULE, Project, ServiceModule, TypeDefinitionFormat


def build_project():
    project = Project("NATSEvents", repo_path="example.com/nats-events")
    event = project.struct_type(
        "Event",
        description="Event record: ID string, Value string. Preserve ID across processing and publication.",
        transfer_by_value=True, definition_format=TypeDefinitionFormat.NATIVE,
    )
    outcome = project.struct_type(
        "PublicationOutcome",
        description=("Publication outcome: EventID string, Accepted bool, Reason string. "
                     "Accepted means local client admission for Core and server PubAck for JetStream; "
                     "neither means downstream business processing completed."),
        transfer_by_value=True, definition_format=TypeDefinitionFormat.NATIVE,
    )
    service = project.service(
        "EventProcessor", language=Golang(version="1.26.4"),
        module=ServiceModule("example.com/nats-events/eventprocessor"),
    )
    core = project.nats_connector("Core events", servers=["nats://localhost:4222"])
    durable = project.jetstream_connector("Durable events", servers=["nats://localhost:4222"])
    for mode, connector in (("Core", core), ("Durable", durable)):
        is_durable = mode == "Durable"
        ingress = connector.subject(
            f"Receive {mode} event", subject=f"example.{mode.lower()}.incoming",
            function=Function(
                f"Receive{mode}Event", module=LOCAL_MODULE,
                description=("Decode Event from native message bytes. Register the result callback before "
                             "Collect; keep the supplied context and correlate by Event.ID. On outcome, "
                             + ("ACK only a confirmed successful publication; NAK publication failures. "
                                "A missing ACK can cause redelivery; processing must be idempotent. "
                                if is_durable else
                                "record local publication acceptance or failure; Core has no ACK or replay. ")
                             + "Call Done after handling the outcome. Done itself never ACKs."),
            ),
            **({"stream_name": "EXAMPLE_IN", "durable_name": "event_processor",
                "create_stream": True, "create_consumer": True}
               if is_durable else {"queue_group": "event_processors"}),
        )
        egress = connector.subject(
            f"Publish {mode} event", subject=f"example.{mode.lower()}.processed",
            function=Function(
                f"Publish{mode}Event", module=LOCAL_MODULE,
                description=("Encode Event and publish through the native endpoint. Emit exactly one "
                             "PublicationOutcome for each event, preserving EventID and the caller context. "
                             "Use asynchronous publication with its callback; represent failed or unknown "
                             "delivery as Accepted=false with a reason. Do not open a second broker client."),
            ),
            **({"stream_name": "EXAMPLE_OUT", "create_stream": True} if is_durable else {}),
        )
        pipeline = service.pipeline(f"Process {mode} events")
        incoming = pipeline.input(f"Receive {mode} event", endpoint=ingress, value_type=event)
        normalized = pipeline.map(
            f"Normalize {mode} event", source=incoming, value_type=event,
            function=Function(
                "NormalizeEvent", module=LOCAL_MODULE,
                description="Preserve Event.ID and normalize Event.Value. One input produces one event; no broker I/O.",
            ),
        )
        published = pipeline.sink(
            f"Publish {mode} event", endpoint=egress, source=normalized, value_type=outcome,
        )
        published >> incoming
    return project


project = build_project()
