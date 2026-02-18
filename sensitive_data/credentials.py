import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

def validate_environment():
    """Validate that all required environment variables are set"""
    required_vars = [
        'SPOTIFY_CLIENT_ID',
        'SPOTIFY_CLIENT_SECRET',
        'DISCORD_APPLICATION_ID',
        'DISCORD_APPLICATION_TOKEN'
    ]

    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        error_msg = f"Missing required environment variables: {', '.join(missing_vars)}\
"
        error_msg += "Please set these variables in your .env file or environment."
        raise ValueError(error_msg)

def get_spotify_client_id():
    """Get Spotify client ID from environment variables"""
    validate_environment()
    return os.getenv('SPOTIFY_CLIENT_ID')

def get_spotify_client_secret():
    """Get Spotify client secret from environment variables"""
    validate_environment()
    return os.getenv('SPOTIFY_CLIENT_SECRET')

def get_discord_application_id():
    """Get Discord application ID from environment variables"""
    validate_environment()
    return os.getenv('DISCORD_APPLICATION_ID')

def get_discord_application_token():
    """Get Discord application token from environment variables"""
    validate_environment()
    return os.getenv('DISCORD_APPLICATION_TOKEN')
