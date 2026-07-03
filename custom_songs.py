import json
import os
from os import listdir
from os.path import isfile, join
from message_history import save_message_history, load_message_history

def create_custom_song_json(song_dir='custom_songs', output_file='custom_songs.json'):
    songs = []
    for file in listdir(song_dir):
        if isfile(join(song_dir, file)):
            songs.append(create_custom_song(join(song_dir, file)))

    for song in songs:
        try:
            s = song['command']
        except KeyError:
            song['command'] = "TODO: add command"

        print(f"Added custom song: {song}")

    save_message_history(songs, output_file)

def create_custom_song(song_file_path):
    """Creates a custom song entry from a file path.

    Args:
        song_file_path (str): The path to the song file.
    """
    song_name = os.path.splitext(os.path.basename(song_file_path))[0]
    return {"name": song_name, "file": song_file_path, "url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ"}

def is_song_command(message):
    """Checks if a message is a command for a custom song.

    Args:
        message (str): The message to check.
    Returns:
        bool: True if the message is a command for a custom song, False otherwise.
    """
    custom_songs = load_message_history('custom_songs.json')
    for song in custom_songs:
        if 'command' in song and message.strip().lower() == song['command'].strip().lower():
            return True
    return False

def get_song_by_command(command):
    """Retrieves a custom song entry based on a command.

    Args:
        command (str): The command to look for.
    Returns:
        dict: The custom song entry that matches the command, or None if not found.
    """
    custom_songs = load_message_history('custom_songs.json')
    for song in custom_songs:
        if 'command' in song and command.strip().lower() == song['command'].strip().lower():
            return song
    return None


#Creates a json based on the files in custom_songs
if __name__ == "__main__":
    create_custom_song_json()
    print(is_song_command("!hansolo_s"))