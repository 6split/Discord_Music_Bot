from .credentials import (
    get_spotify_client_id,
    get_spotify_client_secret,
    get_discord_application_id,
    get_discord_application_token
)

def get_application_id():
    """Get Discord application ID"""
    return get_discord_application_id()

def get_application_token():
    """Get Discord application token"""
    return get_discord_application_token()

def get_spotify_credentials():
    """Get Spotify credentials"""
    return {
        'client_id': get_spotify_client_id(),
        'client_secret': get_spotify_client_secret()
    }