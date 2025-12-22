"""Конфигурация приложения"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Telegram Bot
    BOT_TOKEN: str
    CHANNEL_ID: str
    
    # Database
    DB_HOST: str = ""
    DB_PORT: int = ""
    DB_USER: str = ""
    DB_PASSWORD: str = ""
    DB_NAME: str = ""
    
    # Payment Systems
    PAYME_MERCHANT_ID: str = ""
    PAYME_SECRET_KEY: str = ""
    CLICK_MERCHANT_ID: str = ""
    CLICK_SECRET_KEY: str = ""
    CLICK_SERVICE_ID: str = ""
    
    # Admin
    ADMIN_USER_IDS: str = ""
    PUBLICATION_PRICE: int = 30000
    
    # FastAPI
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # Auction Settings
    # Базовая длительность аукциона (в часах). По умолчанию 2 часа.
    # Можно переопределить через переменную окружения AUCTION_DURATION_HOURS
    AUCTION_DURATION_HOURS: float = 2.0
    
    @property
    def admin_ids_list(self) -> List[int]:
        """Список ID администраторов"""
        if not self.ADMIN_USER_IDS:
            return []
        return [int(uid.strip()) for uid in self.ADMIN_USER_IDS.split(",") if uid.strip()]
    
    @property
    def database_url(self) -> str:
        """URL подключения к базе данных"""
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

