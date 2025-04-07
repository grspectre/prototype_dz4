import os
from pydantic_settings import BaseSettings
from pydantic import ConfigDict

PROJECT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))

class Settings(BaseSettings):
    PROJECT_NAME: str = "FastAPI App"
    PROJECT_VERSION: str = "0.1.0"
    DEBUG: bool = False
    
    DATABASE_URL: str
    
    model_config = ConfigDict(env_file=os.path.join(PROJECT_PATH, ".env"))

settings = Settings()
