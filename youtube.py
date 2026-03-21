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
    """
    yt = YouTube(url)
    video = yt.streams.filter(only_audio=True).first()
    # download the file
    new_file = 'voice'
    try:
        out_file = video.download(".\\music")

        # save the file
        base, ext = os.path.splitext(out_file)
        new_file = base + '.mp3'
        os.rename(out_file, new_file)
    except:
        return new_file
    return new_file
    # result of success

def search_youtube(query, num_results=5):
    results = YoutubeSearch(query, max_results=num_results).to_dict()
    
    # Extract URLs
    urls = [f"https://www.youtube.com{video['url_suffix']}" for video in results]
    
    return urls

# def search_youtube(query, num_results=5):
#     ydl_opts = {"quiet": False, "default_search": "ytsearch{}".format(num_results), 'cookiefile': 'cookies.txt'}
#     with yt_dlp.YoutubeDL(ydl_opts) as ydl:
#         search_results = ydl.extract_info(query, process=True, download=False, force_generic_extractor=True)
#         webpages = []
#         for entry in search_results["entries"]:
#             webpages.append(entry["webpage_url"])
#         return webpages

def speed_test():
    start = time.time()
    result = search_youtube("back in black", 1)[0]
    file = download_from_url(result)
    finish_time = time.time() - start
    print("Test finished in", finish_time, "for file", file)
    return finish_time

def download_audio_wav(url, output_dir="C:\\Users\\sharo\\AI_Chatbots\\music"):
    """Downloads high-quality audio from YouTube and converts to WAV."""
    
    # First, let's list available formats
    ydl_opts = {
        'quiet': False,
        'cookiefile': 'cookies.txt',
    }
    
    try:
        # List available formats
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])
            # Filter for audio-only formats
            audio_formats = [f for f in formats if f.get('acodec') != 'none' and f.get('vcodec') == 'none']
            
            if not audio_formats:
                print("No audio-only formats found, using format with video")
                audio_formats = formats
            
            # Select best audio format
            selected_format = audio_formats[-1]['format_id']
            print(f"Selected format: {selected_format}")
            
        # Now download with selected format
        ydl_opts.update({
            'format': selected_format,
            'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
                'preferredquality': '192',
            }],
            'prefer_ffmpeg': True,
            'keepvideo': False,
            'extract_audio': True,
        })
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            title = info_dict.get('title', 'audio')
            output_path = os.path.join(output_dir, f"{title}.wav")
            print(f"Successfully downloaded: {title}")
            return output_path
            
    except Exception as e:
        print(f"Error: {str(e)}")
        raise

# Add a helper function to list available formats
def list_formats(url):
    """Lists all available formats for a given URL"""
    ydl_opts = {
        'quiet': False,
        'cookiefile': 'cookies.txt',
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        formats = info.get('formats', [])
        
        print("\nAvailable formats:")
        for f in formats:
            format_note = f.get('format_note', 'N/A')
            ext = f.get('ext', 'N/A')
            filesize = f.get('filesize', 'N/A')
            acodec = f.get('acodec', 'N/A')
            
            print(f"ID: {f['format_id']}, "
                  f"Format: {format_note}, "
                  f"Extension: {ext}, "
                  f"Audio codec: {acodec}, "
                  f"Filesize: {filesize}")

if __name__ == "__main__":
    urls = search_youtube("hey ya!")
    download_from_url(urls[0])
    print(urls)