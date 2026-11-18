package serdes

import "example.com/pulsar-events/eventprocessor/internal/types"

type EventSerde struct{ RecordSerde[types.Event] }
