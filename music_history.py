import json
import os
from os import listdir
from os.path import isfile, join
from message_history import save_message_history, load_message_history

#load music history from json file/create json if not there
def load_music_history():
    """Loads the music history from a JSON file. If the file does not exist, creates an empty list.

    Returns:
        list: A list of music history entries.
    """
    return load_message_history('music_history.json')

def save_new_music_entry(query : str, file_path : str, url : str):
    """Saves a new music entry to the music history JSON file.

    Args:
        query (str): The search query for the music entry.
        file_path (str): The file path for the music entry.
        url (str): The URL for the music entry.
    """
    music_history = load_music_history()
    #First check if the entry already exists in the history
    for entry in music_history:
        if entry['file_path'] == file_path:
            if url: #Only update the URL if one was provided, so a cached play doesn't wipe the known URL
                entry['url'] = url #Update the URL to the most recent one
            if query not in entry['queries']:
                entry['queries'].append(query)
            entry['plays'] = entry.get('plays', 0) + 1 #The song has been played again
            save_message_history(music_history, 'music_history.json')
            return

    # If the entry doesn't exist, create a new one
    new_entry = {
        "file_path": file_path,
        "url": url,
        "queries": [query],
        "plays": 1
    }
    music_history.append(new_entry)
    save_message_history(music_history, 'music_history.json')
    return

def file_from_query(query : str, count_play : bool = True):
    """Retrieves the file path for a given search query from the music history.

    Args:
        query (str): The search query to look for.
        count_play (bool): Whether to count this lookup as a play of the song. Defaults to True.
    Returns:
        str: The file path associated with the search query, or None if not found.
    """
    music_history = load_music_history()
    for entry in music_history:
        if query in entry['queries']:
            if count_play:
                entry['plays'] = entry.get('plays', 0) + 1
                save_message_history(music_history, 'music_history.json')
            return entry['file_path']
    return None

def get_top_songs(num_songs : int = 5):
    """Returns the most played songs from the music history, ordered from most played to least played.

    Args:
        num_songs (int): The maximum number of songs to return. Defaults to 5.
    Returns:
        list: A list of the most played music history entries, sorted by plays in descending order.
    """
    music_history = load_music_history()
    sorted_songs = sorted(music_history, key=lambda entry: entry.get('plays', 0), reverse=True)
    return sorted_songs[:num_songs]

if __name__ == "__main__":
    # Testing
    from youtube import search_youtube, download_from_url
    music_history = load_music_history()
    print(music_history)
    save_new_music_entry("Mamma Mia ABBA song", "test.mp3", "example.com")
    print(f"File from query: {file_from_query('Mamma Mia ABBA')}")
    print(load_music_history())