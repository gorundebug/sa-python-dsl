package types

// Accepted means broker acceptance, not downstream business completion.
type PublicationOutcome struct {
	EventID  string
	Accepted bool
	Reason   string
}
