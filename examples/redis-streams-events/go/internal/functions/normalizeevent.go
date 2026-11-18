package functions

import (
	"context"
	"strings"

	"example.com/redis-streams-events/eventprocessor/internal/types"

	"github.com/gorundebug/servicelib/runtime"
	"github.com/gorundebug/servicelib/runtime/environment"
	"github.com/gorundebug/servicelib/transformation"
)

var _ transformation.MapFunction[types.Event, types.Event] = (*NormalizeEvent)(nil)

// NormalizeEvent
type NormalizeEvent struct{}

func (f *NormalizeEvent) Map(ctx context.Context, _ runtime.Stream, value types.Event, out runtime.Collect[types.Event]) {
	value.Value = strings.ToUpper(strings.TrimSpace(value.Value))
	out.Out(ctx, value)
}

// MakeNormalizeEvent is instantiated once at application startup via its maker function.
// Fields of this struct are not protected by any synchronization — do not use
// shared mutable state here without external synchronization.
func MakeNormalizeEvent(ctx context.Context, env environment.ServiceEnvironment) (*NormalizeEvent, error) {
	return &NormalizeEvent{}, nil
}
