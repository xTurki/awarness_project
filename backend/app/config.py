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

    # Scheduling. There is deliberately no overdue-reminder interval: an overdue
    # test is announced once and never repeated. What persists is the state on
    # the dashboard, not the messaging (FR-014).
    due_soon_lead_days: int = 14
    scheduler_hour_utc: int = 6

    # Development only. Shows the sign-in code on the page that asks for it,
    # so building does not stop when the mail provider refuses to send. Set it
    # to false for production; see app/development.py for removing it entirely.
    show_login_code: bool = False

    # The study assistant. Empty key means the feature is simply absent: no
    # panel is rendered and no route answers, so the platform runs unchanged
    # without one.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.1-flash-lite"
    gemini_timeout_seconds: int = 25
    #: Characters of page text sent as context. A page longer than this is cut,
    #: and the trainee is told the answer covers the part they can see.
    gemini_context_chars: int = 6000
    #: Questions per person per rate-limit window.
    ask_rate_limit: int = 20

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
