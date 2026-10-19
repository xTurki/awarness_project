"""App settings, loaded from environment variables / .env.

Secrets have no defaults, so a missing one fails at startup.
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

    # Currently unused (sessions and CSRF tokens are random, not signed).
    # Kept so existing .env files still load.
    session_secret: str

    # Email
    smtp_user: str
    smtp_app_password: str
    smtp_from: str
    smtp_host: str = "smtp-relay.brevo.com"
    smtp_port: int = 587
    smtp_timeout_seconds: int = 10

    # Uploads. The same value is used for the nginx body size limit.
    upload_max_mb: int = 5
    upload_dir: str = "/data/uploads"

    # Scheduling. Overdue notices are sent once, not repeated.
    due_soon_lead_days: int = 14
    scheduler_hour_utc: int = 6

    # Development only: show the login code on the verify page.
    # Must be false in production (see app/development.py).
    show_login_code: bool = False

    # Study assistant (Gemini). Disabled when the key is empty.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.1-flash-lite"
    gemini_timeout_seconds: int = 25
    # Max characters of page text sent as context.
    gemini_context_chars: int = 6000
    # Questions per user per rate-limit window.
    ask_rate_limit: int = 20

    # Timings and limits
    code_ttl_minutes: int = 10
    session_hours: int = 12
    login_rate_limit: int = 5
    login_rate_window_minutes: int = 2

    # Checked by extension only. Uploads are served as static files, never executed.
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
