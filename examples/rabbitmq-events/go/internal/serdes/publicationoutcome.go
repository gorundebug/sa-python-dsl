package serdes

import "example.com/rabbitmq-events/eventprocessor/internal/types"

type PublicationOutcomeSerde struct {
	RecordSerde[types.PublicationOutcome]
}
