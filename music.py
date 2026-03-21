import discord
import random
#Thread safe queue implementation
import queue

from ollama import chat, ChatResponse
from dataclasses import dataclass
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from difflib import get_close_matches
import time
from sensitive_data import get_spotify_client_secret, get_spotify_client_id
from youtube import search_youtube, download_from_url
from autoplay import song_reccomendations
from settings.settings import get_all_settings, modify_setting, populate_settings_json

SPOTIFY_CLIENT_ID = get_spotify_client_id()
SPOTIFY_CLIENT_SECRET = get_spotify_client_secret()
#Create the spotify client
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET
))

@dataclass
class Song:
    name : str
    filename : str
    url : str

class Music_Manager:
    song_history = []
    potential_autoplay = None
    current_song = None
    set_presence = None
    def __init__(self, voice_client : discord.VoiceClient):
        self.current_queue = queue.Queue()
        self.voice_client = voice_client
    
    def update_set_presence_function(self, set_presence_func):
        self.set_presence = set_presence_func

    def update_voice_client(self, new_voice_client : discord.VoiceClient):
        self.voice_client = new_voice_client

    def request_song(self, song_name : str):
        requested_song = song_from_youtube(song_name + " song")
        self.current_queue.put(requested_song)
        self.current_queue.task_done()
        if not self.voice_client.is_playing() and not self.voice_client.is_paused():
            self.play_next()
        return
    
    def retreieve_current_song(self):
        """Returns the currently playing song, or a message indicating that no song is currently playing."""
        if self.current_song:
            return f"Currently playing: {self.current_song}"
        else:
            return "No song is currently playing."

    def retreieve_queue(self):
        """Returns a list of the songs currently in the queue."""
        return list(self.current_queue.queue)
    
    def pause(self):
        self.voice_client.pause()

    def resume(self):
        self.voice_client.resume()
    
    def skip_song(self):
        self.voice_client.stop()

    def _play_song(self, song : Song):
        audio_source = discord.FFmpegPCMAudio(song.filename, executable='C:\\ffmpeg\\bin\\ffmpeg.exe', options=f"-b:a 256")
        self.voice_client.play(audio_source, bitrate=256, signal_type='music', after=self.play_next)
        self.song_history.append(song.name)
        if self.voice_client.is_playing() and self.set_presence is not None:
            self.set_presence(f"Playing: {song.name[0:len(song.name)-5]}")  #Set presence to the song name, removing the " song" at the end
    def _create_autoplay_song(self):
            #Set up the next autoplay song
            print("Picking Autoplay song")
            try:
                spotify_song_reccomendations = spotify_reccomendation(self.current_song.name, self.song_history)
                if len(spotify_song_reccomendations) < 1:
                    raise Exception("No autoplay options")
            except Exception as e:
                print(f"Error getting spotify reccomendations: {str(e)}")
                print("Now using local reccomendations")
                assert self.current_song is not None, "Current song is None, cannot get reccomendations"
                srecc = chatbot_reccomendation(self.current_song.name, self.song_history)
                if srecc:
                    spotify_song_reccomendations = [srecc]
                else:
                    spotify_song_reccomendations = song_reccomendations(self.current_song.name, autoplayed_songs=self.song_history)
            
            print(f"Autoplay options: {spotify_song_reccomendations}")
            autoplay_song = song_from_youtube(random.choice(spotify_song_reccomendations))
            self.potential_autoplay = autoplay_song
            print(f"Set potential autoplay song to: {self.potential_autoplay.name}")

    def play_next(self, Error=None):
        """
        Called when a song ends or when requesting a song to then either play the next song in the queue, or autoplay a song
        
        :param self: Description
        """
        print("play_next in music queue")
        self.current_queue.join()

        if not self.voice_client.is_connected():
            return

        #If for some reason we are already playing audio wait until we are not.
        while self.voice_client.is_playing() or self.voice_client.is_paused():
            print("Waiting for current song to finish/for voice client to be free...")
            time.sleep(1)
            
        if self.current_queue.empty() and self.current_song:

            #If we have an autoplay song ready
            if self.potential_autoplay:
                assert isinstance(self.potential_autoplay, Song)
                self.current_song = self.potential_autoplay
                self._play_song(self.current_song)
                self.potential_autoplay = None
                self._create_autoplay_song()
        
        if not self.current_queue.empty():
            self.current_song = self.current_queue.get()

            self._play_song(self.current_song)

            self.current_queue.join()
        if self.current_queue.empty() and get_all_settings()["autoplay"]:
            self._create_autoplay_song()
            if not self.voice_client.is_playing() and not self.voice_client.is_paused() and self.potential_autoplay:
                assert isinstance(self.potential_autoplay, Song)
                self.current_song = self.potential_autoplay
                self._play_song(self.current_song)
                self.potential_autoplay = None

def song_from_youtube(search_query):
    result = search_youtube(search_query + " song", 1)[0]
    file = download_from_url(result)
    song = Song(search_query, file, result)
    return song

def spotify_reccomendation(song, autoplayed_songs=[]):
    results = sp.search(q=song, type="playlist", limit=5)
    song_names = []
    playlists = results.get('playlists', {}).get('items', [])
    count = 0
    for playlist in playlists:
        if len(song_names) > 10:
            break
        print(playlist)
        playlist_id = playlist['id']
        tracks = sp.playlist_tracks(playlist_id)
        for item in tracks.get('items', []):
            track = item.get('track')
            if track and track.get('name') and track.get('artists'):
                song_name = f"{track['name']} by {track['artists'][0]['name']}"
                song_names.append(song_name)
        count += 1
    filtered_songs = get_close_matches(song, song_names, 20, cutoff=0.8)
    remaining_songs = [s for s in song_names if s not in filtered_songs and s not in autoplayed_songs]
    random.shuffle(remaining_songs)
    return remaining_songs

def chatbot_reccomendation(song, autoplayed_songs=[]):
    messages = [{'role': 'system', 'content': "You are an advanced AI autoplay system which responds with a singular song_name by artist name when asked for a reccomendation"},]
    messages.extend([{'role': 'user', 'content': f"Reccomend a song similar to {song}"}])
    most_recent_message = ""

    for i in range(10):  # Limit to 10 iterations to avoid infinite loops
        response: ChatResponse = chat(
            model='qwen3:8b',
            messages=messages,
            think=True,
        )
        if response.message.thinking:
            print(f"Think: {response.message.thinking}")
        if response.message.content:
            return response.message.content
        messages.append(response.message)
        if response.message.thinking:
            continue
    return None

if __name__ == "__main__":
    song_name = "Sustain/Decay Drivealone"
    # print(spotify_reccomendation("Get Lucky Daft Punk"))
    print(song_reccomendations(song_name))
    print(f"Response: {chatbot_reccomendation(song_name)}")