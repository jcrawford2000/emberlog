from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseSettings):
    # database_url: str
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str = "password"
    postgres_db: str = "emberlog"
    postgres_pool_min_size: int = 1
    postgres_pool_max_size: int = 5

    log_level: str = "INFO"
    enable_file_logging: bool = False
    
    notifier_base_url: str = "http://localhost:8090"
    mqtt_host: str = "mosquitto.pi-rack.com"
    mqtt_port: int = 1883
    mqtt_topic_prefix: str = "emberlog/trunkrecorder"
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    mqtt_tls: bool = False

    max_decoderate: float = 40.0
    rates_topic_suffix: str = "rates"
    recorders_topic_suffix: str = "recorders"
    calls_active_topic_suffix: str = "calls_active"

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        
    )


settings = Settings()  # type: ignore[call-arg]
