from pydantic import BaseModel, EmailStr, Field


class RegistrationCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class EmailVerificationCreate(BaseModel):
    email: EmailStr
    otp: str = Field(pattern=r"^\d{6}$")


class RefreshTokenCreate(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class VerificationResponse(BaseModel):
    success: bool

