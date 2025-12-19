import discord
import random
#Thread safe queue implementation
import queue

from dataclasses import dataclass
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from difflib import get_close_matches
from sklearn.metrics.pairwise import cosine_similarity
import time
from sensitive_data.spotify_data import spotify_secret, spotify_client_id
from youtube import search_youtube, download_from_url

SPOTIFY_CLIENT_ID = spotify_client_id()
SPOTIFY_CLIENT_SECRET = spotify_secret()
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
    def __init__(self, voice_client : discord.VoiceClient):
        self.current_queue = queue.Queue()
        self.voice_client = voice_client
    
    def update_voice_client(self, new_voice_client : discord.VoiceClient):
        self.voice_client = new_voice_client

    def request_song(self, song_name : str):
        requested_song = song_from_youtube(song_name)
        self.current_queue.put(requested_song)
        if not self.voice_client.is_playing() and not self.voice_client.is_paused():
            self.play_next()
        return
    
    def pause(self):
        self.voice_client.pause()

    def resume(self):
        self.voice_client.resume()
    
    def _play_song(self, song : Song):
        audio_source = discord.FFmpegPCMAudio(song.filename, executable='C:\\ffmpeg\\bin\\ffmpeg.exe', options=f"-b:a 256")
        self.voice_client.play(audio_source, bitrate=256, signal_type='music')
        self.song_history.append(song.name)

    def _create_autoplay_song(self):
            #Set up the next autoplay song
            print("Picking Autoplay song")
            spotify_song_reccomendations = spotify_reccomendation(self.current_song.name, self.song_history)
            print(f"Autoplay options: {spotify_song_reccomendations}")
            autoplay_song = song_from_youtube(random.choice(spotify_song_reccomendations))
            self.potential_autoplay = autoplay_song

    def play_next(self):
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
            if self.current_queue.empty():
                self._create_autoplay_song()


            


def song_from_youtube(search_query):
    result = search_youtube(search_query + " song", 1)[0]
    file = download_from_url(result)
    song = Song(search_query, file, result)
    return song


def spotify_reccomendation(song, autoplayed_songs=[]):
    results = sp.search(q=song, type="playlist", limit=20)
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
    filtered_songs = get_close_matches(song, song_names, 20, cutoff=0.6)
    remaining_songs = [s for s in song_names if s not in filtered_songs and s not in autoplayed_songs]
    random.shuffle(remaining_songs)
    return remaining_songs

if __name__ == "__main__":
    print(spotify_reccomendation("Get Lucky Daft Punk"))