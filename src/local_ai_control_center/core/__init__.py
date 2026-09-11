"""The rules: what is allowed, what a plan is, what a claim check concludes.

Nothing here reaches a model, a network or a document format. `workspace` resolves real
paths, which is the one exception and is deliberate: "nothing outside the workspace is
touched" is a rule in PRINCIPLES, and resolving a path is how that rule is checked rather
than an effect it governs (ADR-029).
"""
