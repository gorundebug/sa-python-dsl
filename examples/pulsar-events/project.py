"""Pulsar delivery -> normalization -> publication result -> explicit individual ACK."""
from sa_dsl import Function, Golang, LOCAL_MODULE, Project, ServiceModule, TypeDefinitionFormat


def build_project():
    project = Project('PulsarEvents', repo_path='example.com/pulsar-events')
    event = project.struct_type('Event', description='ID string, Value string. Stable business identity survives duplicate delivery.', transfer_by_value=True, definition_format=TypeDefinitionFormat.NATIVE)
    outcome = project.struct_type('PublicationOutcome', description='EventID string, MessageID string, Accepted bool, Reason string. MessageID is the Pulsar message ID, not proof of downstream processing.', transfer_by_value=True, definition_format=TypeDefinitionFormat.NATIVE)
    service = project.service('EventProcessor', language=Golang(version='1.26.4'), module=ServiceModule('example.com/pulsar-events/eventprocessor'))
    broker = project.pulsar_connector('Events', servers=['pulsar://localhost:6650'], admin_url='http://localhost:8080')
    ingress = broker.endpoint('Receive event', topic='persistent://public/events/incoming', subscription_name='event_processors', subscription_type='Shared', create_topic=True, create_subscription=True, subscription_initial_position='Earliest', receiver_queue_size=16,
        function=Function('ReceiveEvent', module=LOCAL_MODULE, description='Decode Event from payload JSON; register callback before Collect. Preserve business ID and context. Individually ACK only after correlated Accepted publication with a native MessageID. Done does not ACK; failed outputs remain unacknowledged. No extra broker client.'))
    egress = broker.endpoint('Publish event', topic='persistent://public/events/processed', create_topic=True, publisher_max_in_flight=16,
        function=Function('PublishEvent', module=LOCAL_MODULE, description='Encode Event as payload JSON, set business ID as key and publish asynchronously through the endpoint. Return PublicationOutcome with EventID and native MessageID. Do not retry Unknown outcomes. Callback captures immutable request data.'))
    pipeline = service.pipeline('Process events')
    incoming = pipeline.input('Receive event', endpoint=ingress, value_type=event)
    normalized = pipeline.map('Normalize event', source=incoming, value_type=event,
        function=Function('NormalizeEvent', module=LOCAL_MODULE, description='Preserve ID, trim and uppercase Value. Pure business transformation without broker IO.'))
    published = pipeline.sink('Publish event', endpoint=egress, source=normalized, value_type=outcome)
    published >> incoming
    return project


project = build_project()
