"""One RabbitMQ delivery -> normalized event -> confirmed publication -> explicit settlement."""
from sa_dsl import Function, Golang, LOCAL_MODULE, Project, ServiceModule, TypeDefinitionFormat


def build_project():
    project = Project("RabbitMQEvents", repo_path="example.com/rabbitmq-events")
    event = project.struct_type("Event", description="Event record: ID string, Value string.",
                                transfer_by_value=True, definition_format=TypeDefinitionFormat.NATIVE)
    outcome = project.struct_type("PublicationOutcome", description="EventID string, Accepted bool, Reason string. Broker acceptance is not downstream processing.",
                                  transfer_by_value=True, definition_format=TypeDefinitionFormat.NATIVE)
    service = project.service("EventProcessor", language=Golang(version="1.26.4"),
                              module=ServiceModule("example.com/rabbitmq-events/eventprocessor"))
    broker = project.rabbitmq_connector("Events", servers=["amqp://localhost:5672"], virtual_host="/")
    ingress = broker.endpoint("Receive event", queue_name="example.incoming", create_queue=True,
        queue_type="quorum", consumer_credits=16, function=Function("ReceiveEvent", module=LOCAL_MODULE,
        description="Decode Event, register callback before Collect, preserve correlation. Accept only confirmed output; release failures. Done never settles. Processing must be idempotent under redelivery."))
    egress = broker.endpoint("Publish event", queue_name="example.processed", exchange_name="example.events",
        routing_key="processed", queue_type="quorum", exchange_type="direct", create_queue=True,
        create_exchange=True, create_binding=True, publisher_max_in_flight=16,
        function=Function("PublishEvent", module=LOCAL_MODULE,
        description="Encode Event and use native async Send. Return one correlated PublicationOutcome. Preserve native failure distinctions in Reason. Callbacks may outlive EndRequest; no extra broker client."))
    pipeline = service.pipeline("Process events")
    incoming = pipeline.input("Receive event", endpoint=ingress, value_type=event)
    normalized = pipeline.map("Normalize event", source=incoming, value_type=event,
        function=Function("NormalizeEvent", module=LOCAL_MODULE, description="Preserve ID; trim and uppercase Value. No broker IO."))
    published = pipeline.sink("Publish event", endpoint=egress, source=normalized, value_type=outcome)
    published >> incoming
    return project


project = build_project()
