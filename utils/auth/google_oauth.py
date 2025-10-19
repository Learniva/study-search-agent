"""Google OAuth 2.0 authentication handler."""

import os
from typing import Dict, Any, Optional
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config

# Load configuration
config = Config(environ=os.environ)

# OAuth configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8000/auth/google/callback")


class GoogleOAuth:
    """Google OAuth handler."""
    
    def __init__(self):
        """Initialize OAuth client."""
        self.oauth = OAuth()
        self.oauth.register(
            name='google',
            client_id=GOOGLE_CLIENT_ID,
            client_secret=GOOGLE_CLIENT_SECRET,
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={
                'scope': 'openid email profile'
            }
        )
    
    def get_client(self):
        """Get the OAuth client."""
        return self.oauth.google
    
    @staticmethod
    def get_authorization_url(redirect_uri: Optional[str] = None) -> str:
        """
        Get the Google OAuth authorization URL.
        
        Args:
            redirect_uri: Optional custom redirect URI
            
        Returns:
            Authorization URL
        """
        from urllib.parse import urlencode
        
        redirect = redirect_uri or GOOGLE_REDIRECT_URI
        params = {
            'client_id': GOOGLE_CLIENT_ID,
            'redirect_uri': redirect,
            'response_type': 'code',
            'scope': 'openid email profile',
            'access_type': 'offline',
            'prompt': 'consent',
        }
        
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    
    async def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verify a Google OAuth token and get user info.
        
        Args:
            token: OAuth token
            
        Returns:
            User information dict
        """
        # This would verify the token with Google
        # For now, we'll assume the token is valid from the callback
        pass
    
    @staticmethod
    def extract_user_info(user_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Extract relevant user information from Google OAuth response.
        
        Args:
            user_data: Raw user data from Google
            
        Returns:
            Cleaned user info dict
        """
        return {
            "email": user_data.get("email", ""),
            "name": user_data.get("name", ""),
            "picture": user_data.get("picture", ""),
            "google_id": user_data.get("sub", ""),
            "email_verified": user_data.get("email_verified", False),
        }


# Global instance
google_oauth = GoogleOAuth()

