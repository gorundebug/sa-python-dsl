"""Pulsar transport constraints shared by authoring and imported models."""
from urllib.parse import urlsplit
import unicodedata

SOURCE_FIELDS = {
    "subscriptionName", "subscriptionType", "subscriptionInitialPosition",
    "createSubscription", "receiverQueueSize", "negativeAckRedeliveryDelayMs",
}


def _control(value):
    return any(unicodedata.category(c) == "Cc" for c in value)


def _url(value, schemes):
    if not isinstance(value, str) or any(c.isspace() for c in value) or _control(value):
        return None
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in schemes or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.path or "?" in value or "#" in value
                or parsed.netloc.endswith(":") or (parsed.port is not None and not 1 <= parsed.port <= 65535)):
            return None
        return parsed
    except ValueError:
        return None


def validate_connector(connector, invalid):
    p = connector.properties
    if connector.type != "Pulsar":
        if "adminUrl" in p:
            invalid("adminUrl", "adminUrl requires Pulsar")
        return
    servers = p.get("servers")
    service = _url(servers[0], {"pulsar", "pulsar+ssl"}) if isinstance(servers, list) and len(servers) == 1 else None
    admin = _url(p.get("adminUrl"), {"http", "https"})
    if service is None:
        invalid("servers", "Pulsar requires one binary URL without inline credentials, path or query")
    if admin is None:
        invalid("adminUrl", "Pulsar requires a valid HTTP(S) administration URL")
    if service and service.scheme == "pulsar+ssl" and admin and admin.scheme != "https":
        invalid("adminUrl", "Pulsar TLS transport requires HTTPS administration")
    for key in ("connectTimeoutMs", "operationTimeoutMs"):
        if key in p and (type(p[key]) is not int or not 1 <= p[key] <= 2147483647):
            invalid(key, "Pulsar timeout must be an integer between 1 and 2147483647 milliseconds")
    for key in ("token", "username", "password", "credentialsFile", "tlsServerName", "tlsEnabled", "brokers", "version", "dialTimeout", "securityProtocol", "saslMechanism", "async", "usePartitioner"):
        if key in p:
            invalid(key, "Unsupported topology field; Pulsar credentials belong in runtime overrides")
    if ("tlsCertFile" in p) != ("tlsKeyFile" in p):
        invalid("tlsCertFile", "Certificate and key must be supplied together")
    for key in ("tlsCaFile", "tlsCertFile", "tlsKeyFile"):
        if key in p:
            if not isinstance(p[key], str) or not p[key].strip():
                invalid(key, "TLS path must be nonempty")
            if service and service.scheme != "pulsar+ssl":
                invalid(key, "TLS settings require pulsar+ssl and HTTPS URLs")


def validate_endpoint(endpoint, source, invalid):
    p = endpoint.properties
    if endpoint.connector.type != "Pulsar":
        for key in SOURCE_FIELDS.intersection(p):
            invalid(key, "Field requires Pulsar")
        return
    topic = p.get("topic")
    parts = topic.removeprefix("persistent://").split("/") if isinstance(topic, str) else []
    if (not isinstance(topic, str) or not topic.startswith("persistent://") or len(parts) != 3
            or any(not part or _control(part) or any(c.isspace() or c in "%?#\\" for c in part) for part in parts)):
        invalid("topic", "Expected persistent://tenant/namespace/topic")
    for key, maximum in (("partitions", 1000), ("receiverQueueSize", 4096), ("negativeAckRedeliveryDelayMs", 2147483647), ("publisherMaxInFlight", 4096)):
        if key in p and (type(p[key]) is not int or not 1 <= p[key] <= maximum):
            invalid(key, f"Must be an integer between 1 and {maximum}")
    for key in ("createTopic", "createSubscription"):
        if key in p and type(p[key]) is not bool:
            invalid(key, "Must be boolean")
    if "partitions" in p and p.get("createTopic") is not True:
        invalid("partitions", "Partitions require explicit topic creation")
    if "subscriptionType" in p and p["subscriptionType"] not in ("Shared", "Exclusive", "Failover"):
        invalid("subscriptionType", "Unsupported Pulsar subscription mode")
    if "subscriptionInitialPosition" in p and (p["subscriptionInitialPosition"] not in ("Earliest", "Latest") or p.get("createSubscription") is not True):
        invalid("subscriptionInitialPosition", "Earliest or Latest requires explicit subscription creation")
    if source is True or "subscriptionName" in p:
        name = p.get("subscriptionName")
        if not isinstance(name, str) or not name or _control(name) or any(c in "/%?#\\" for c in name):
            invalid("subscriptionName", "A valid durable subscription name is required")
    for key in ("replicationFactor", "consumerGroup"):
        if key in p:
            invalid(key, "Pulsar uses subscriptions and namespace replication policy")
    if source is True and "publisherMaxInFlight" in p:
        invalid("publisherMaxInFlight", "Applies only to sinks")
    if source is False:
        for key in SOURCE_FIELDS.intersection(p):
            invalid(key, "Applies only to sources")
