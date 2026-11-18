package serdes

import "example.com/rabbitmq-events/eventprocessor/internal/types"

type EventSerde struct{ RecordSerde[types.Event] }
