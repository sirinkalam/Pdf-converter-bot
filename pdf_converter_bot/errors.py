class ConversionError(Exception):
    """Base conversion error."""


class UnsupportedFileError(ConversionError):
    pass


class FileTooLargeError(ConversionError):
    pass


class ProviderTimeoutError(ConversionError):
    pass


class ProviderExecutionError(ConversionError):
    pass
