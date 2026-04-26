"""Environment-based configuration classes."""
import os


class BaseConfig:
    SECRET_KEY = os.getenv('SECRET_KEY', '')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB hard cap (Flask-level)

    REQUEST_TIMEOUT = 10            # seconds — outbound HTTP calls
    GEMINI_TIMEOUT = 15             # seconds — Gemini generate_content calls
    MAX_RESUME_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB soft cap for resumes
    MAX_RESUME_PAGES = 10
    PDF_EXTRACTION_TIMEOUT = 20     # seconds — for PyMuPDF page reads
    ASSEMBLYAI_TOKEN_TTL = 55       # seconds — short-lived realtime tokens


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    TESTING = False


class ProductionConfig(BaseConfig):
    DEBUG = False
    TESTING = False


class TestingConfig(BaseConfig):
    DEBUG = True
    TESTING = True


config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
}
