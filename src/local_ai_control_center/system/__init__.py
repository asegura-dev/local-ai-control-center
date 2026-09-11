"""Machine-facing code that is not behind a port, and says so by living here.

An audit trail and a hardware profile each have one implementation. Putting them under
`adapters` would imply a port that does not exist and invite someone to add one for
symmetry (ADR-029).
"""
