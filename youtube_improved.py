"""
Improved YouTube download functionality with proper error handling
"""

from pytubefix import YouTube
from youtubesearchpython import VideosSearch
from youtube_search import YoutubeSearch
import os
import yt_dlp
import time

def download_from_url(url):
    """Downloads the audio and returns the name of the mp3 file

    Args:
        url: The video URL to download

    Returns:
        str: Path to the downloaded file or None if download fails
    """
    try:
        # Ensure the music directory exists
        os.makedirs(".\music", exist_ok=True)

        # Download using pytubefix
        yt = YouTube(url)
        video = yt.streams.filter(only_audio=True).first()

        # Download the file
        out_file = video.download(".\music")

        # Save the file as mp3
        base, ext = os.path.splitext(out_file)
        new_file = base + '.mp3'
        os.rename(out_file, new_file)

        return new_file

    except Exception as e:
        print(f"Error downloading from URL {url}: {str(e)}")
        return None

def search_youtube(query, num_results=5):
    """Search for videos on YouTube with error handling

    Args:
        query: Search query
        num_results: Number of results to return

    Returns:
        list: List of YouTube URLs or empty list if search fails
    """
    try:
        results = YoutubeSearch(query, max_results=num_results).to_dict()

        # Extract URLs
        urls = [f"https://www.youtube.com{video['url_suffix']}" for video in results]

        return urls
    except Exception as e:
        print(f"Error searching YouTube for '{query}': {str(e)}")
        return []

def song_from_youtube(search_query):
    """Get song from YouTube with error handling

    Args:
        search_query: Song name to search for

    Returns:
        Song object or None if download fails
    """
    try:
        # Search for the song
        urls = search_youtube(search_query + " song", 1)
        if not urls:
            print(f"No results found for '{search_query}'")
            return None

        # Download the audio
        file_path = download_from_url(urls[0])
        if not file_path:
            print(f"Failed to download audio from {urls[0]}")
            return None

        # Create and return Song object
        from dataclasses import dataclass

        @dataclass
        class Song:
            name: str
            filename: str
            url: str

        return Song(search_query, file_path, urls[0])

    except Exception as e:
        print(f"Error processing song '{search_query}': {str(e)}")
        return None