package types

// Event record: ID string, Value string. Preserve ID across processing and publication.
type Event struct {
	ID    string `json:"ID"`
	Value string `json:"Value"`
}
