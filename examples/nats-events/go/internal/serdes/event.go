package serdes

import "example.com/nats-events/eventprocessor/internal/types"

type EventSerde struct{ RecordSerde[types.Event] }
