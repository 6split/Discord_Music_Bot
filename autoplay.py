import csv
from rapidfuzz import fuzz
import re
import math
tracks = []
FEATURE_KEYS = [
    "danceability", "energy",
    "liveness", "valence",
    "acousticness", "instrumentalness",
    "speechiness",
]
def load_tracks_from_csv(file_path = "spotify_songs.csv"):
    with open(file_path, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            tracks.append(row)

def normalize(text):
    text = text.lower()
    text = re.sub(r"\(.*?\)", "", text)  # remove parentheses
    text = re.sub(r"[^a-z0-9\s]", "", text)  # remove punctuation
    return text.strip()

def compute_distance(track1, track2):
    return math.sqrt(
        sum(
            (float(track1[k]) - float(track2[k])) ** 2
            for k in FEATURE_KEYS
        )
    )

def find_most_similar_track(query):
    best_match = None
    best_score = 0

    query_clean = normalize(query)
    query_words = set(query_clean.split())

    for track in tracks:
        title_clean = normalize(track["track_name"])
        title_words = set(title_clean.split())

        # Base fuzzy score
        fuzzy_score = fuzz.token_set_ratio(query_clean, title_clean)

        # Word overlap score
        overlap = len(query_words & title_words)
        overlap_score = overlap * 15  # weight overlap strongly

        # Penalize very short titles
        length_penalty = abs(len(title_words) - len(query_words)) * 0.5

        final_score = fuzzy_score + overlap_score - length_penalty
        artist_clean = normalize(track["track_artist"])
        if artist_clean in query_clean:
            final_score += 20

        if final_score > best_score:
            best_score = final_score
            best_match = track

    return best_match, best_score

def song_reccomendations(song_name, top_n=5, popularity_threshold=25, autoplayed_songs=[]):

    #Automatically load tracks from csv
    if len(tracks) < 1:
        load_tracks_from_csv()
    
    current_track = find_most_similar_track(song_name)[0]
    for track in tracks:
        track["similarity_score"] = compute_distance(current_track, track)
    tracks_sorted = sorted(tracks, key=lambda x: x["similarity_score"], reverse=False)
    num_tracks = 0
    reccomendations = []
    for track in tracks_sorted:
        if track["track_name"] in autoplayed_songs or f"{track['track_name']} by {track['track_artist']}" in autoplayed_songs:
            continue
        if track in reccomendations:
            continue
        if track["playlist_id"] == current_track["playlist_id"]:
            num_tracks += 1
            reccomendations.append(f"{track['track_name']} by {track['track_artist']}")
        if int(track["track_popularity"]) >= popularity_threshold and track["track_name"] != current_track["track_name"]:
            num_tracks += 1
            reccomendations.append(f"{track['track_name']} by {track['track_artist']}")
            if num_tracks >= top_n:
                break

    return reccomendations

if __name__ == "__main__":
    import random
    load_tracks_from_csv()
    current_song = "Get Lucky Daft Punk"
    played_songs = []
    # print(tracks[:5])  # Print the first 5 tracks to verify they were loaded correctly
    for i in range(25):
        similar_track = find_most_similar_track(current_song)
        #print(f"Most similar track: {similar_track[0]['track_name']} by {similar_track[0]['track_artist']} with score {similar_track[1]} and genre {similar_track[0]['playlist_genre']}")
        reccomendations = song_reccomendations(current_song, top_n=10, popularity_threshold=45, autoplayed_songs=played_songs)
        current_song = random.choice(reccomendations)
        played_songs.append(current_song)
        print(f"Next song: {current_song}")