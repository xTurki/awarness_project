"""Settings, read from the environment only.

No default here embeds a credential. A missing secret is a startup failure,
not a silently weak default (FR-033).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    mysql_database: str
    mysql_user: str
    mysql_password: str
    mysql_host: str = "db"
    mysql_port: int = 3306

    # Application
    session_secret: str

    # Email
    smtp_user: str
    smtp_app_password: str
    smtp_from: str
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_timeout_seconds: int = 10

    # Uploads. One number feeds both the application limit and the one nginx
    # enforces, so the two cannot drift apart and produce a blank 413 the
    # application never sees (research R4).
    upload_max_mb: int = 5
    upload_dir: str = "/data/uploads"

    # Timings and limits
    code_ttl_minutes: int = 10
    session_hours: int = 12
    login_rate_limit: int = 5
    login_rate_window_minutes: int = 5

    # Checked by extension only. A renamed executable will be accepted and stored;
    # it lands in a directory nginx serves as static content and does not run.
    allowed_image_extensions: tuple[str, ...] = (".png", ".jpg", ".jpeg", ".gif", ".webp")

    @property
    def upload_max_bytes(self) -> int:
        return self.upload_max_mb * 1024 * 1024

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            f"?charset=utf8mb4"
        )


settings = Settings()
