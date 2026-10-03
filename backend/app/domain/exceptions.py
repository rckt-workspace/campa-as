"""Domain exceptions for Instagram provider"""


class InstagramProviderException(Exception):
    """Base exception for Instagram provider errors"""
    pass


class TooManyRequestsException(InstagramProviderException):
    """Raised when Instagram returns HTTP 429"""
    pass


class LoginRequiredException(InstagramProviderException):
    """Raised when Instagram requires authentication"""
    pass


class ProfileNotFoundException(InstagramProviderException):
    """Raised when the Instagram profile doesn't exist"""
    pass


class PrivateProfileException(InstagramProviderException):
    """Raised when accessing a private profile that can't be followed"""
    pass


class InvalidSessionException(InstagramProviderException):
    """Raised when session file is invalid or expired"""
    pass


class ConnectionException(InstagramProviderException):
    """Raised for network-related errors"""
    pass
