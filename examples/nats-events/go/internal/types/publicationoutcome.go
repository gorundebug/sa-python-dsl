package types

// Publication outcome: EventID string, Accepted bool, Reason string. Accepted means local client admission for Core and
// server PubAck for JetStream; neither means downstream business processing completed.
type PublicationOutcome struct {
	EventID  string
	Accepted bool
	Reason   string
}
