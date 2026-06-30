from fastapi import status

from app.core.exceptions import AppError


class EmailAlreadyRegisteredError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        )


class RegistrationEmailFailedError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not send verification email",
        )


class InvalidOrExpiredCodeError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code",
        )


class InvalidCredentialsError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )


class InvalidRefreshTokenError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )


class RefreshTokenCookieMissingError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token cookie missing",
        )
