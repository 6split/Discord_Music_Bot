"""
Wrapper module for YouTube functionality that provides a clean interface
to the improved YouTube download and search capabilities.
"""

from youtube_improved import (
    download_from_url as _download_from_url,
    search_youtube as _search_youtube,
    song_from_youtube as _song_from_youtube
)
from youtube import download_audio_wav as _download_audio_wav
from youtube import list_formats as _list_formats


def download_from_url(url):
    """
    Downloads audio from a YouTube URL and returns the path to the downloaded file.

    Args:
        url (str): The YouTube video URL to download

    Returns:
        str: Path to the downloaded MP3 file or None if download fails
    """
    return _download_from_url(url)


def search_youtube(query, num_results=5):
    """
    Search for videos on YouTube with error handling.

    Args:
        query (str): Search query
        num_results (int): Number of results to return (default: 5)

    Returns:
        list: List of YouTube URLs or empty list if search fails
    """
    return _search_youtube(query, num_results)


def song_from_youtube(search_query):
    """
    Get song from YouTube with error handling.

    Args:
        search_query (str): Song name to search for

    Returns:
        Song object or None if download fails
    """
    return _song_from_youtube(search_query)


def download_audio_wav(url, output_dir="music"):
    """
    Downloads high-quality audio from YouTube and converts to WAV format.

    Args:
        url (str): YouTube video URL
        output_dir (str): Directory to save the WAV file (default: "music")

    Returns:
        str: Path to the downloaded WAV file or None if download fails
    """
    try:
        return _download_audio_wav(url, output_dir)
    except Exception as e:
        print(f"Error downloading WAV file: {str(e)}")
        return None


def list_formats(url):
    """
    Lists all available formats for a given YouTube URL.

    Args:
        url (str): YouTube video URL
    """
    try:
        _list_formats(url)
    except Exception as e:
        print(f"Error listing formats: {str(e)}")


# Alias for backward compatibility
from youtube_improved import Song