"""
Centralized configuration management using Pydantic Settings.

All environment variables and configuration in one place.
Type-safe with validation.
"""

from typing import Optional, Literal
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # ==================== LLM Configuration ====================
    google_api_key: str = Field(..., description="Google Gemini API key")
    llm_provider: str = Field(default="gemini", description="LLM provider")
    default_model: str = Field(default="gemini-2.5-flash", description="Default LLM model")
    fallback_model: str = Field(default="gemini-2.5-pro", description="Fallback LLM model")
    
    # LLM Temperature settings
    temp_study: float = Field(default=0.7, ge=0.0, le=1.0, description="Study agent temperature")
    temp_grading: float = Field(default=0.3, ge=0.0, le=1.0, description="Grading agent temperature")
    temp_routing: float = Field(default=0.0, ge=0.0, le=1.0, description="Routing temperature")
    temp_creative: float = Field(default=0.9, ge=0.0, le=1.0, description="Creative temperature")
    
    # ==================== Database Configuration ====================
    database_url: str = Field(
        default="postgresql://localhost/grading_system",
        description="PostgreSQL connection string"
    )
    db_pool_size: int = Field(default=20, ge=1, le=100, description="Database pool size")
    db_max_overflow: int = Field(default=30, ge=0, le=200, description="Max overflow connections")
    db_pool_recycle: int = Field(default=1800, ge=300, description="Pool recycle time (seconds)")
    db_pool_pre_ping: bool = Field(default=True, description="Enable pool pre-ping")
    db_pool_timeout: int = Field(default=30, ge=1, le=120, description="Pool timeout (seconds)")
    db_command_timeout: int = Field(default=60, ge=1, le=300, description="Command timeout (seconds)")
    db_echo: bool = Field(default=False, description="Echo SQL queries")
    db_statement_timeout: int = Field(default=30000, ge=1000, description="Statement timeout (ms)")
    db_connection_retries: int = Field(default=3, ge=0, le=10, description="Connection retry attempts")
    db_retry_backoff: float = Field(default=0.5, ge=0.1, description="Retry backoff factor (seconds)")
    
    # ==================== Cache Configuration ====================
    cache_enabled: bool = Field(default=True, description="Enable result caching")
    cache_ttl: int = Field(default=300, ge=0, description="Cache TTL in seconds")
    cache_max_size: int = Field(default=1000, ge=10, description="Max cache entries")
    redis_url: Optional[str] = Field(
        default="redis://localhost:6379/0",
        description="Redis URL for distributed cache and token storage"
    )
    redis_enabled: bool = Field(default=False, description="Enable Redis (falls back to in-memory if unavailable)")
    
    # ==================== API Configuration ====================
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, ge=1024, le=65535, description="API port")
    api_workers: int = Field(default=1, ge=1, le=16, description="Number of API workers")
    api_reload: bool = Field(default=False, description="Enable auto-reload")
    
    # Rate limiting
    rate_limit_enabled: bool = Field(default=True, description="Enable rate limiting")
    rate_limit_per_minute: int = Field(default=60, ge=1, description="Requests per minute")
    rate_limit_per_hour: int = Field(default=1000, ge=1, description="Requests per hour")
    
    # ==================== Performance Configuration ====================
    max_concurrent_requests: int = Field(default=100, ge=1, description="Max concurrent requests")
    request_timeout: int = Field(default=60, ge=5, description="Request timeout (seconds)")
    max_context_tokens: int = Field(default=500, ge=50, description="Max context tokens")
    max_agent_iterations: int = Field(default=5, ge=1, le=10, description="Max agent iterations")
    max_grading_iterations: int = Field(default=3, ge=1, le=5, description="Max grading iterations")
    
    # ==================== Document Processing ====================
    documents_dir: str = Field(default="documents", description="Documents directory")
    max_document_size_mb: int = Field(default=50, ge=1, description="Max document size (MB)")
    chunk_size: int = Field(default=1000, ge=100, description="Document chunk size")
    chunk_overlap: int = Field(default=200, ge=0, description="Document chunk overlap")
    
    # ==================== Search Configuration ====================
    google_search_api_key: Optional[str] = Field(default=None, description="Google Custom Search API key")
    google_search_engine_id: Optional[str] = Field(default=None, description="Google Custom Search Engine ID")
    tavily_api_key: Optional[str] = Field(default=None, description="Tavily API key for web search (fallback)")
    search_max_results: int = Field(default=5, ge=1, le=10, description="Max search results")
    
    # ==================== Google Classroom Configuration ====================
    google_classroom_credentials_file: Optional[str] = Field(
        default="credentials.json",
        description="Path to Google Classroom OAuth2 credentials JSON file"
    )
    google_classroom_token_file: Optional[str] = Field(
        default="token.json",
        description="Path to store Google Classroom access token"
    )
    google_classroom_scopes: list[str] = Field(
        default=[
            "https://www.googleapis.com/auth/classroom.courses.readonly",
            "https://www.googleapis.com/auth/classroom.coursework.students",
            "https://www.googleapis.com/auth/classroom.courseworkmaterials.readonly",
            "https://www.googleapis.com/auth/classroom.rosters.readonly",
            "https://www.googleapis.com/auth/classroom.student-submissions.students.readonly",
            "https://www.googleapis.com/auth/classroom.student-submissions.me.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ],
        description="Google Classroom API scopes"
    )
    enable_google_classroom: bool = Field(
        default=True,
        description="Enable Google Classroom integration"
    )
    
    # ==================== Feature Flags ====================
    enable_ml_features: bool = Field(default=True, description="Enable ML/adaptive features")
    enable_performance_routing: bool = Field(default=True, description="Enable performance-based routing")
    enable_streaming: bool = Field(default=True, description="Enable SSE streaming")
    enable_manim: bool = Field(default=False, description="Enable Manim animations")
    
    # ==================== Monitoring & Logging ====================
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Logging level"
    )
    enable_metrics: bool = Field(default=True, description="Enable Prometheus metrics")
    enable_tracing: bool = Field(default=False, description="Enable distributed tracing")
    sentry_dsn: Optional[str] = Field(default=None, description="Sentry DSN for error tracking")
    
    # ==================== Security ====================
    secret_key: str = Field(
        ...,  # Required field - no default
        min_length=32,
        description="Secret key for JWT tokens (must be at least 32 characters)"
    )
    
    # OAuth Configuration
    google_client_id: Optional[str] = Field(
        default=None,
        description="Google OAuth Client ID"
    )
    google_client_secret: Optional[str] = Field(
        default=None,
        description="Google OAuth Client Secret"
    )
    google_redirect_uri: str = Field(
        default="http://localhost:8000/auth/google/callback",
        description="Google OAuth redirect URI"
    )
    access_token_expire_minutes: int = Field(
        default=30,
        ge=1,
        description="Access token expiry (minutes)"
    )
    token_expire_hours: int = Field(
        default=24,
        ge=1,
        description="Auth token expiry (hours)"
    )
    
    # Enhanced Security Settings
    enable_account_lockout: bool = Field(
        default=True,
        description="Enable account lockout after failed login attempts"
    )
    max_login_attempts: int = Field(
        default=5,
        ge=3,
        le=10,
        description="Maximum login attempts before lockout"
    )
    lockout_duration_minutes: int = Field(
        default=15,
        ge=5,
        le=60,
        description="Account lockout duration in minutes"
    )
    
    # Password Policy Settings
    password_min_length: int = Field(
        default=12,
        ge=8,
        le=128,
        description="Minimum password length"
    )
    password_require_uppercase: bool = Field(
        default=True,
        description="Require uppercase letters in passwords"
    )
    password_require_lowercase: bool = Field(
        default=True,
        description="Require lowercase letters in passwords"
    )
    password_require_digits: bool = Field(
        default=True,
        description="Require digits in passwords"
    )
    password_require_special_chars: bool = Field(
        default=True,
        description="Require special characters in passwords"
    )
    password_min_special_chars: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Minimum number of special characters required"
    )
    password_history_count: int = Field(
        default=12,
        ge=5,
        le=24,
        description="Number of previous passwords to prevent reuse"
    )
    
    # Session Security
    enable_session_fingerprinting: bool = Field(
        default=True,
        description="Enable session fingerprinting for device tracking"
    )
    max_concurrent_sessions: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum concurrent sessions per user"
    )
    session_timeout_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Session timeout in hours"
    )
    
    # Security Headers
    enable_security_headers: bool = Field(
        default=True,
        description="Enable comprehensive security headers"
    )
    hsts_max_age: int = Field(
        default=31536000,  # 1 year
        ge=0,
        description="HSTS max-age in seconds"
    )
    enable_csp: bool = Field(
        default=True,
        description="Enable Content Security Policy"
    )
    csp_report_uri: Optional[str] = Field(
        default=None,
        description="CSP violation reporting endpoint"
    )
    
    # Rate Limiting (Enhanced)
    rate_limit_login_attempts: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Login attempts per minute"
    )
    rate_limit_auth_endpoints: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Auth endpoint requests per minute"
    )
    
    # ==================== Stripe Payment Configuration ====================
    stripe_secret_key: Optional[str] = Field(
        default=None,
        description="Stripe secret key for payment processing"
    )
    stripe_publishable_key: Optional[str] = Field(
        default=None,
        description="Stripe publishable key for frontend"
    )
    stripe_webhook_secret: Optional[str] = Field(
        default=None,
        description="Stripe webhook signing secret"
    )
    stripe_price_id: Optional[str] = Field(
        default=None,
        description="Default Stripe Price ID for subscriptions"
    )
    stripe_success_url: str = Field(
        default="http://localhost:3000/payment/success",
        description="Payment success redirect URL"
    )
    stripe_cancel_url: str = Field(
        default="http://localhost:3000/payment/cancel",
        description="Payment cancel redirect URL"
    )
    
    # ==================== Frontend/Backend URLs ====================
    frontend_url: str = Field(
        default="http://localhost:3000",
        description="Frontend application URL"
    )
    backend_url: str = Field(
        default="http://localhost:8000",
        description="Backend API URL"
    )
    
    # ==================== Email Configuration ====================
    email_enabled: bool = Field(default=False, description="Enable email sending")
    email_backend: str = Field(default="smtp", description="Email backend (smtp or console)")
    email_host: str = Field(default="smtp.gmail.com", description="SMTP host")
    email_port: int = Field(default=587, ge=1, le=65535, description="SMTP port")
    email_use_tls: bool = Field(default=True, description="Use TLS for email")
    email_use_ssl: bool = Field(default=False, description="Use SSL for email")
    email_host_user: Optional[str] = Field(default=None, description="Email account username")
    email_host_password: Optional[str] = Field(default=None, description="Email account password or app password")
    email_from_address: str = Field(
        default="noreply@learniva.ai",
        description="Default FROM email address"
    )
    email_from_name: str = Field(
        default="LearnivaAI",
        description="Default FROM name"
    )
    password_reset_url: str = Field(
        default="http://localhost:3000/reset-password",
        description="Frontend password reset page URL"
    )
    password_reset_token_expire_hours: int = Field(
        default=1,
        ge=1,
        le=24,
        description="Password reset token expiry (hours)"
    )
    
    # ==================== Development ====================
    debug: bool = Field(default=False, description="Debug mode")
    testing: bool = Field(default=False, description="Testing mode")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"
    
    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Ensure database URL is valid."""
        if not v.startswith(("postgresql://", "postgresql+asyncpg://")):
            raise ValueError("Database URL must use PostgreSQL")
        return v
    
    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Validate secret key for production use."""
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long")
        if v in ["your-super-secret-jwt-key-minimum-32-characters-long-replace-in-production", 
                 "change-me-in-production", "development-key-not-secure"]:
            raise ValueError("SECRET_KEY must be changed from default value in production")
        return v
    
    @property
    def async_database_url(self) -> str:
        """Get async database URL for SQLAlchemy."""
        if "asyncpg" in self.database_url:
            return self.database_url
        return self.database_url.replace("postgresql://", "postgresql+asyncpg://")
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.debug or self.testing
    
    @property
    def is_production_ready(self) -> bool:
        """Check if configuration is production-ready."""
        production_checks = [
            len(self.secret_key) >= 32,
            not self.secret_key.startswith("your-super-secret"),
            not "localhost" in self.database_url if not self.is_development else True,
            self.google_client_id is not None if self.google_client_secret else True,
            self.google_client_secret is not None if self.google_client_id else True,
        ]
        return all(production_checks)
    
    def validate_production_config(self) -> list[str]:
        """Get list of production configuration issues."""
        issues = []
        
        if len(self.secret_key) < 32:
            issues.append("SECRET_KEY must be at least 32 characters")
        
        if self.secret_key.startswith("your-super-secret"):
            issues.append("SECRET_KEY must be changed from default value")
            
        if not self.is_development and "localhost" in self.database_url:
            issues.append("DATABASE_URL should not use localhost in production")
            
        if self.google_client_id and not self.google_client_secret:
            issues.append("GOOGLE_CLIENT_SECRET required when GOOGLE_CLIENT_ID is set")
            
        if self.google_client_secret and not self.google_client_id:
            issues.append("GOOGLE_CLIENT_ID required when GOOGLE_CLIENT_SECRET is set")
            
        return issues
    
    @property
    def temperature_settings(self) -> dict[str, float]:
        """Get temperature settings for different use cases."""
        return {
            "study": self.temp_study,
            "grading": self.temp_grading,
            "routing": self.temp_routing,
            "creative": self.temp_creative,
            "precise": 0.0,
        }


# Global settings instance
settings = Settings()

