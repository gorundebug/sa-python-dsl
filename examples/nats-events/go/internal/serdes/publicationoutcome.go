package serdes

import "example.com/nats-events/eventprocessor/internal/types"

type PublicationOutcomeSerde struct {
	RecordSerde[types.PublicationOutcome]
}
