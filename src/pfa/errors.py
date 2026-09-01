"""Error types.

One rule: an error message must tell the operator what to *do*, not merely what
went wrong. This project is a debugging tool; its own failures should model the
behaviour it is meant to encourage.
"""


class PfaError(Exception):
    """Base class for every error this project raises deliberately."""


class ConfigError(PfaError):
    """The routing policy is missing, unparseable or internally inconsistent."""


class RoutingError(PfaError):
    """A task could not be resolved to a provider/model pair."""


class RuntimeMissingError(PfaError):
    """The Hermes runtime is required for this command but is not installed."""
