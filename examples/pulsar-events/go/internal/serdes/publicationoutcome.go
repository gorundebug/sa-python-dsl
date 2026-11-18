package serdes

import "example.com/pulsar-events/eventprocessor/internal/types"

type PublicationOutcomeSerde struct {
	RecordSerde[types.PublicationOutcome]
}
