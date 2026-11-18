// Test peer only. The generated service uses its native SDK endpoints.
#include <iostream>
#include <openssl/evp.h>
#include <pulsar/Client.h>
#include <stdexcept>
#include <string>
void check(pulsar::Result result) {
  if (result != pulsar::ResultOk)
    throw std::runtime_error(pulsar::strResult(result));
}
std::string encode(const pulsar::MessageId &id) {
  std::string bytes;
  id.serialize(bytes);
  std::string value(4 * ((bytes.size() + 2) / 3), '\0');
  EVP_EncodeBlock(reinterpret_cast<unsigned char *>(value.data()),
                  reinterpret_cast<const unsigned char *>(bytes.data()),
                  static_cast<int>(bytes.size()));
  return value;
}
int main(int argc, char **argv) {
  try {
    if (argc != 4)
      throw std::runtime_error("url incoming outgoing required");
    pulsar::ClientConfiguration config;
    config.setOperationTimeoutMs(3000);
    pulsar::Client client(argv[1], config);
    pulsar::Producer producer;
    pulsar::ProducerConfiguration pc;
    pc.setBatchingEnabled(false);
    check(client.createProducer(argv[2], pc, producer));
    pulsar::Consumer consumer;
    pulsar::ConsumerConfiguration cc;
    cc.setConsumerType(pulsar::ConsumerShared);
    cc.setAckReceiptEnabled(true);
    cc.setAckGroupingTimeMs(0);
    check(client.subscribe(argv[3], "canonical_observer", cc, consumer));
    for (int i = 0; i < 3; ++i) {
      std::string id = "event-" + std::to_string(i);
      check(producer.send(
          pulsar::MessageBuilder()
              .setContent("{\"ID\":\"" + id + "\",\"Value\":\" hello \"}")
              .setPartitionKey(id)
              .setProperty("x-stream-id", "source-" + id)
              .build()));
    }
    for (int i = 0; i < 3; ++i) {
      pulsar::Message message;
      check(consumer.receive(message, 5000));
      if (message.getProperty("example") != "pulsar-events")
        throw std::runtime_error("caller property lost");
      if (message.getProperty("x-stream-id") !=
          "source-" + message.getPartitionKey())
        throw std::runtime_error("context correlation lost");
      std::cout << "{\"payload\":" << message.getDataAsString() << ",\"key\":\""
                << message.getPartitionKey() << "\",\"MessageID\":\""
                << encode(message.getMessageId()) << "\"}" << std::endl;
      check(consumer.acknowledge(message));
    }
    check(consumer.close());
    check(producer.close());
    check(client.close());
    return 0;
  } catch (const std::exception &e) {
    std::cerr << e.what() << '\n';
    return 1;
  }
}
