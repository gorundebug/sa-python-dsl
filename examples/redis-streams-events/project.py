"""Redis group delivery -> normalization -> XADD result -> explicit input XACK."""
from sa_dsl import Function, Golang, LOCAL_MODULE, Project, ServiceModule, TypeDefinitionFormat


def build_project():
    project = Project('RedisStreamsEvents', repo_path='example.com/redis-streams-events')
    event = project.struct_type('Event', description='ID string, Value string. Stable business identity survives duplicate delivery.', transfer_by_value=True, definition_format=TypeDefinitionFormat.NATIVE)
    outcome = project.struct_type('PublicationOutcome', description='EventID string, EntryID string, Accepted bool, Reason string. EntryID is the Redis XADD result, not proof of downstream processing or replica durability.', transfer_by_value=True, definition_format=TypeDefinitionFormat.NATIVE)
    service = project.service('EventProcessor', language=Golang(version='1.26.4'), module=ServiceModule('example.com/redis-streams-events/eventprocessor'))
    broker = project.redis_streams_connector('Events', servers=['redis://localhost:6379'], redis_database=0)
    ingress = broker.endpoint('Receive event', stream_key='example.incoming', consumer_group='event_processors', create_consumer_group=True, group_start_id='0-0', read_count=16, read_block_ms=100, claim_idle_ms=60000, claim_interval_ms=1000,
        function=Function('ReceiveEvent', module=LOCAL_MODULE, description='Decode Event from native fields; register callback before Collect. Preserve business ID and received context. XACK only after correlated Accepted output; leave failures pending. Done does not ACK. Reclaim may duplicate processing and does not fence old workers. No extra Redis client.'))
    egress = broker.endpoint('Publish event', stream_key='example.processed', create_stream=True, publisher_max_in_flight=16,
        function=Function('PublishEvent', module=LOCAL_MODULE, description='Encode Event as native stream fields and send asynchronously via the endpoint. Emit one PublicationOutcome preserving EventID and the returned Redis entry ID. Unknown outcome is not retried automatically. Callbacks may outlive EndRequest; do not capture invalid state.'))
    pipeline = service.pipeline('Process events')
    incoming = pipeline.input('Receive event', endpoint=ingress, value_type=event)
    normalized = pipeline.map('Normalize event', source=incoming, value_type=event,
        function=Function('NormalizeEvent', module=LOCAL_MODULE, description='Preserve ID, trim and uppercase Value. Pure business transformation without broker IO.'))
    published = pipeline.sink('Publish event', endpoint=egress, source=normalized, value_type=outcome)
    published >> incoming
    return project


project = build_project()
