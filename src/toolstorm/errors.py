"""Portable tool errors: retry decisions belong to the application."""


class ToolstormError(Exception):
    """Base for ToolStorm configuration and runtime errors."""


class ConfigurationError(ToolstormError, ValueError):
    """An invalid rule, option, or serialized document."""


class ToolError(ToolstormError):
    """A simulated tool-boundary failure."""


class ToolTimeout(ToolError, TimeoutError):
    """The tool was not invoked. This is a synthetic pre-call timeout."""


class ResponseLost(ToolError, TimeoutError):
    """The tool returned successfully, then its acknowledgement was lost.

    A real timeout rarely tells a caller whether a commit occurred. This distinct
    type lets tests describe that ambiguity; it does not detect live commits.
    """


class RateLimited(ToolError):
    """A synthetic rate limit; retry_after is in seconds."""

    def __init__(self, retry_after: float = 1.0) -> None:
        import math

        try:
            valid = (
                type(retry_after) in (int, float)
                and math.isfinite(retry_after)
                and retry_after >= 0
            )
        except OverflowError:
            valid = False
        if not valid:
            raise ConfigurationError("retry_after must be finite and nonnegative")
        self.retry_after = float(retry_after)
        super().__init__(f"Tool rate limited; retry after {retry_after:g}s")


class ToolUnavailable(ToolError):
    """A synthetic pre-call service outage."""


class BudgetExceeded(ToolstormError):
    """The boundary refused a call after the configured call budget."""


class ReplayMismatch(ToolstormError, AssertionError):
    """Offline replay diverged from the recorded call sequence."""


class RecordedToolError(ToolError):
    """A safe stand-in for an unknown exception type in a recording."""

    def __init__(self, original_type: str) -> None:
        self.original_type = original_type
        super().__init__(f"Recorded tool raised {original_type} (message omitted)")
