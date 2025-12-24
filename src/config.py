from authx import AuthX, AuthXConfig
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Base configuration
    base_url: str = "http://localhost:8000"
    max_firmware_size: int = 5 * 1024 * 1024  # 5MB

    class Config:
        env_file = ".env"
        extra = "ignore"


auth_config = AuthXConfig(
        JWT_ALGORITHM = "HS256",
        JWT_SECRET_KEY = "4c0458b57f668d6059b261822b9c299240c8e1c4d86e70842ffeb0df42fab8b61cd67001b630394d4676808e0c841c76d14f838b06f59ed0a66b65172f56fa01883b2147a0d1153c35bdd3d6755ac1e9300619f5c469c2dcc9ec8366226e42f8f0d54b2da9ca1b2e129cd5c757f4459b9365f939c4af84ba039e95c47968cef5fca378fcfaed6d9fd3bb27948195171c9429eeb60f06ecbc03a29ba3cad8bfee4623328267043d7cb681f4127586fbef9c167e0c649d1056642a80208bdc20f5c00bf42b0fa8ff06571b34e2399c16d4b7c19c6d099c9c1698226abdcd49e5ec43e64cfd668e595368475d0675d92a1810edb978eb1bbd5f146d0b7512544b26",
        JWT_TOKEN_LOCATION = ["headers"],
    )

auth = AuthX(config=auth_config)


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get application settings.

    Returns:
        Settings instance
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings