package serdes

import "example.com/redis-streams-events/eventprocessor/internal/types"

type PublicationOutcomeSerde struct {
	RecordSerde[types.PublicationOutcome]
}
