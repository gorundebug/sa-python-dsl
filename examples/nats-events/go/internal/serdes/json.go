package serdes

import (
	"encoding/json"
	"fmt"
)

// RecordSerde is the example's wire encoding, independent of the broker.
type RecordSerde[T any] struct{}

func (*RecordSerde[T]) IsStub() bool { return false }
func (s *RecordSerde[T]) SerializeObj(value interface{}, prefix []byte) ([]byte, error) {
	record, ok := value.(T)
	if !ok {
		return nil, fmt.Errorf("unexpected record type %T", value)
	}
	return s.Serialize(record, prefix)
}
func (s *RecordSerde[T]) DeserializeObj(data []byte) (interface{}, error) { return s.Deserialize(data) }
func (*RecordSerde[T]) Serialize(value T, prefix []byte) ([]byte, error) {
	data, err := json.Marshal(value)
	if err != nil {
		return nil, err
	}
	return append(prefix, data...), nil
}
func (*RecordSerde[T]) Deserialize(data []byte) (T, error) {
	var value T
	err := json.Unmarshal(data, &value)
	return value, err
}
