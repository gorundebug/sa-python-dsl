from sa_dsl import (
    DataConnectorImplementation,
    KafkaSaslMechanism,
    KafkaCluster,
    KafkaSecurity,
    KafkaSecurityProtocol,
)

from processorder.project.processorder import project

connector_order_events = project.kafka_connector(
    'Order Events',
    go_implementation=DataConnectorImplementation.IBM_SARAMA,
    cpp_userver_implementation=DataConnectorImplementation.USERVER_KAFKA,
    cpp_boost_implementation=DataConnectorImplementation.LIBRDKAFKA,
    python_implementation=DataConnectorImplementation.AIOKAFKA,
    rust_implementation=DataConnectorImplementation.RUST_RDKAFKA,
    type_script_implementation=DataConnectorImplementation.CONFLUENT_KAFKA_JAVASCRIPT,
    cluster=KafkaCluster(brokers='redpanda:9092', version='2.8.0', dial_timeout=5000),
    security=KafkaSecurity(protocol=KafkaSecurityProtocol.PLAINTEXT, mechanism=KafkaSaslMechanism.SCRAM_SHA_512, username='', password=''),
)
