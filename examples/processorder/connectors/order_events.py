from processorder.project.processorder import project

from sa_dsl import (
    KafkaSaslMechanism,
    KafkaSecurityProtocol,
)

order_events = project.kafka_connector(
    "Order Events",
    brokers="redpanda:9092",
    security_protocol=KafkaSecurityProtocol.PLAINTEXT,
    version="2.8.0",
    dial_timeout=5000,
    sasl_mechanism=KafkaSaslMechanism.SCRAM_SHA_512,
    username="",
    password="",
)
