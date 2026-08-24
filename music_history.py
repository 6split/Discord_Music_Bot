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
            entry['queries'].append(query)
            save_message_history(music_history, 'music_history.json')
            return

    # If the entry doesn't exist, create a new one
    new_entry = {
        "file_path": file_path,
        "url": url,
        "queries": [query]
    }
    music_history.append(new_entry)
    save_message_history(music_history, 'music_history.json')
    return

def file_from_query(query : str):
    """Retrieves the file path for a given search query from the music history.

    Args:
        query (str): The search query to look for.
    Returns:
        str: The file path associated with the search query, or None if not found.
    """
    music_history = load_music_history()
    for entry in music_history:
        if query in entry['queries']:
            return entry['file_path']
    return None

if __name__ == "__main__":
    # Example usage
    music_history = load_music_history()
    print(music_history)