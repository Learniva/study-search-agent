"""
Secret Key Validator

Validates SECRET_KEY and other security-critical configuration
to prevent running in production with weak/default values.
"""

import os
from typing import List, Tuple


class SecretKeyValidator:
    """Validates secret keys and security configuration."""
    
    # Known weak/default secret keys that should never be used
    WEAK_SECRETS = {
        "your-secret-key-change-in-production",
        "your-secret-key-change-this-in-production",
        "secret",
        "SECRET",
        "changeme",
        "CHANGEME",
        "test",
        "TEST",
        "development",
        "DEVELOPMENT"
    }
    
    MIN_SECRET_LENGTH = 32  # Minimum 32 characters for production
    
    @classmethod
    def validate_secret_key(cls, secret_key: str, is_production: bool = False) -> Tuple[bool, List[str]]:
        """
        Validate SECRET_KEY strength.
        
        Args:
            secret_key: The secret key to validate
            is_production: Whether running in production mode
            
        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []
        
        if not secret_key:
            errors.append("SECRET_KEY is not set")
            return (False, errors)
        
        # Check if using a known weak/default value
        if secret_key in cls.WEAK_SECRETS:
            errors.append(
                f"CRITICAL: SECRET_KEY is set to a default/weak value: '{secret_key}'. "
                "This is a SECURITY RISK! Generate a strong random key."
            )
        
        # Check minimum length
        if len(secret_key) < cls.MIN_SECRET_LENGTH:
            errors.append(
                f"SECRET_KEY is too short ({len(secret_key)} chars). "
                f"Minimum {cls.MIN_SECRET_LENGTH} characters required for security."
            )
        
        # In production, be extra strict
        if is_production and len(errors) > 0:
            errors.insert(0, "⚠️  PRODUCTION MODE: Cannot start with weak SECRET_KEY!")
        
        return (len(errors) == 0, errors)
    
    @classmethod
    def validate_or_fail(cls, secret_key: str, is_production: bool = False) -> None:
        """
        Validate SECRET_KEY and raise exception if invalid.
        
        Args:
            secret_key: The secret key to validate
            is_production: Whether running in production mode
            
        Raises:
            ValueError: If SECRET_KEY is invalid
        """
        is_valid, errors = cls.validate_secret_key(secret_key, is_production)
        
        if not is_valid:
            error_msg = "\n".join([
                "="*70,
                "❌ SECURITY VALIDATION FAILED",
                "="*70,
                *errors,
                "",
                "💡 To fix:",
                "1. Generate a strong random key:",
                "   python -c 'import secrets; print(secrets.token_urlsafe(32))'",
                "",
                "2. Set it in your .env file:",
                "   SECRET_KEY=<your-generated-key>",
                "",
                "3. Restart the application",
                "="*70
            ])
            raise ValueError(error_msg)
    
    @classmethod
    def generate_secure_key(cls) -> str:
        """
        Generate a cryptographically secure random key.
        
        Returns:
            A URL-safe random string suitable for use as SECRET_KEY
        """
        import secrets
        return secrets.token_urlsafe(32)


def validate_production_secrets(debug: bool = False) -> None:
    """
    Validate all security-critical secrets before starting the application.
    
    This should be called during application startup (in lifespan).
    
    Args:
        debug: Whether running in debug mode (less strict validation)
        
    Raises:
        ValueError: If any critical secret is invalid
    """
    is_production = not debug
    
    # Validate SECRET_KEY
    secret_key = os.getenv("SECRET_KEY", "")
    SecretKeyValidator.validate_or_fail(secret_key, is_production)
    
    # Add validation for other critical secrets here
    # For example: JWT_SECRET_KEY, DATABASE_ENCRYPTION_KEY, etc.
    
    if is_production:
        # Additional production-specific validations
        stripe_secret = os.getenv("STRIPE_SECRET_KEY", "")
        if stripe_secret and stripe_secret.endswith("_here"):
            raise ValueError(
                "CRITICAL: STRIPE_SECRET_KEY is still set to placeholder value! "
                "Update it with your actual Stripe secret key."
            )


if __name__ == "__main__":
    # Example usage and testing
    print("Secret Key Validator - Testing")
    print("="*50)
    
    # Test weak keys
    weak_keys = [
        "secret",
        "test",
        "your-secret-key-change-in-production",
        "short"
    ]
    
    for key in weak_keys:
        is_valid, errors = SecretKeyValidator.validate_secret_key(key, is_production=True)
        print(f"\nKey: '{key}'")
        print(f"Valid: {is_valid}")
        if errors:
            print(f"Errors: {errors}")
    
    # Generate a secure key
    print("\n" + "="*50)
    print("Generated secure key:")
    print(SecretKeyValidator.generate_secure_key())

