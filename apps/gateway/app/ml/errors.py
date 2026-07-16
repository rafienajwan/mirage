"""Shared validation errors for model dataset adapters."""


class DatasetValidationError(ValueError):
    """Raised when source data cannot be converted into trainable rows."""
