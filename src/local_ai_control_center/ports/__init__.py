"""What the core needs the world to satisfy: an abstract class and the contracts crossing it.

A port earns its place when there are two real implementations. Provider has Ollama and a
mock, Converter has PDF and Word, Notifier has ntfy and its test double. Audit, workspace
and profiling have one each, so they stay concrete and live elsewhere (ADR-029).
"""
