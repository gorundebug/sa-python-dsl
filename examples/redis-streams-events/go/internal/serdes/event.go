package serdes

import "example.com/redis-streams-events/eventprocessor/internal/types"

type EventSerde struct{ RecordSerde[types.Event] }
