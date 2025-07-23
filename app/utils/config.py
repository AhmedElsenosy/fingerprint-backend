from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    MONGO_URI: str
    DATABASE_NAME: str
    JWT_SECRET: str
    JWT_ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    HOST_REMOTE_URL: str

    class Config:
        env_file = ".env"
        validate_assignment = True  

settings = Settings()