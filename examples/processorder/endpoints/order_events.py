from processorder.connectors.order_events import order_events

from processorder.packages.endpoint import endpoint_package

from sa_dsl import Function

endpoint_order_processed = order_events.topic(
    "Order Processed",
    function=Function(
        name="OrderProcessedEndpoint",
        package=endpoint_package,
        public=False,
        description="Exchange OrderProcessed events keyed by order ID.\n"
        "Producers include the final status, processing time, total and confirmed item counts, "
        "and a failure reason for unsuccessful orders.\n"
        "Consumers decode the event and mark its Kafka message processed only after the pipeline "
        "handles it successfully.\n",
    ),
    enabled=True,
    create_topic=True,
    topic="order-processed",
    partitions=1,
    consumer_group="analytics-service",
    replication_factor=1,
    use_partitioner=False,
)
