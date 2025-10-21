"""Configuration validator for authentication."""

import os
from typing import Dict, List, Tuple
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class AuthConfigValidator:
    """Validate authentication configuration."""
    
    @staticmethod
    def validate_google_oauth() -> Tuple[bool, List[str]]:
        """
        Validate Google OAuth configuration.
        
        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []
        
        # Check required environment variables
        client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
        redirect_uri = os.getenv("GOOGLE_OAUTH_REDIRECT_URI")
        
        if not client_id:
            errors.append("GOOGLE_OAUTH_CLIENT_ID is not set")
        elif not client_id.endswith(".apps.googleusercontent.com"):
            errors.append("GOOGLE_OAUTH_CLIENT_ID should end with .apps.googleusercontent.com")
        
        if not client_secret:
            errors.append("GOOGLE_OAUTH_CLIENT_SECRET is not set")
        
        if not redirect_uri:
            errors.append("GOOGLE_OAUTH_REDIRECT_URI is not set")
        elif not redirect_uri.endswith("/auth/google/callback"):
            errors.append("GOOGLE_OAUTH_REDIRECT_URI should end with /auth/google/callback")
        
        return (len(errors) == 0, errors)
    
    @staticmethod
    def validate_jwt_config() -> Tuple[bool, List[str]]:
        """
        Validate JWT configuration.
        
        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []
        
        secret_key = os.getenv("SECRET_KEY")
        
        if not secret_key:
            errors.append("SECRET_KEY is not set")
        elif len(secret_key) < 32:
            errors.append("SECRET_KEY should be at least 32 characters long")
        elif secret_key == "your-secret-key-change-in-production":
            errors.append("SECRET_KEY is still set to the default value - change it!")
        
        return (len(errors) == 0, errors)
    
    @staticmethod
    def validate_stripe_config() -> Tuple[bool, List[str]]:
        """
        Validate Stripe configuration.
        
        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []
        
        secret_key = os.getenv("STRIPE_SECRET_KEY")
        publishable_key = os.getenv("STRIPE_PUBLISHABLE_KEY")
        price_id = os.getenv("STRIPE_PRICE_ID")
        
        if not secret_key:
            errors.append("STRIPE_SECRET_KEY is not set")
        elif not (secret_key.startswith("sk_test_") or secret_key.startswith("sk_live_")):
            errors.append("STRIPE_SECRET_KEY should start with sk_test_ or sk_live_")
        elif secret_key.endswith("_here"):
            errors.append("STRIPE_SECRET_KEY is still set to placeholder value")
        
        if not publishable_key:
            errors.append("STRIPE_PUBLISHABLE_KEY is not set")
        elif not (publishable_key.startswith("pk_test_") or publishable_key.startswith("pk_live_")):
            errors.append("STRIPE_PUBLISHABLE_KEY should start with pk_test_ or pk_live_")
        
        if not price_id:
            errors.append("STRIPE_PRICE_ID is not set")
        elif not price_id.startswith("price_"):
            errors.append("STRIPE_PRICE_ID should start with price_")
        
        return (len(errors) == 0, errors)
    
    @staticmethod
    def validate_all() -> Dict[str, Tuple[bool, List[str]]]:
        """
        Validate all authentication and payment configurations.
        
        Returns:
            Dictionary with validation results for each component
        """
        return {
            "google_oauth": AuthConfigValidator.validate_google_oauth(),
            "jwt": AuthConfigValidator.validate_jwt_config(),
            "stripe": AuthConfigValidator.validate_stripe_config(),
        }
    
    @staticmethod
    def print_validation_report():
        """Print a formatted validation report."""
        print("\n" + "="*70)
        print("Authentication & Payment Configuration Validation")
        print("="*70 + "\n")
        
        results = AuthConfigValidator.validate_all()
        
        all_valid = True
        
        for component, (is_valid, errors) in results.items():
            status = "✅ VALID" if is_valid else "❌ INVALID"
            print(f"{component.upper().replace('_', ' ')}: {status}")
            
            if not is_valid:
                all_valid = False
                for error in errors:
                    print(f"  ⚠️  {error}")
            
            print()
        
        print("="*70)
        
        if all_valid:
            print("✅ All configurations are valid!")
        else:
            print("❌ Some configurations need attention")
            print("\nPlease update your .env file with the correct values")
        
        print("="*70 + "\n")
        
        return all_valid


if __name__ == "__main__":
    # Run validation when script is executed directly
    AuthConfigValidator.print_validation_report()

