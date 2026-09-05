from processorder.project.processorder import project

from sa_dsl import (
    KafkaCluster,
    KafkaSecurity,
    KafkaSaslMechanism,
    KafkaSecurityProtocol,
)

order_events = project.kafka_connector(
    "Order Events",
    cluster=KafkaCluster(brokers="redpanda:9092", version="2.8.0", dial_timeout=5000),
    security=KafkaSecurity(protocol=KafkaSecurityProtocol.PLAINTEXT, mechanism=KafkaSaslMechanism.SCRAM_SHA_512, username="", password=""),
)
