from minim import tidal, spotify
import json
import time
import requests
import re

# look for access_token in browser networking tab while using tidal web app
tidal_access_token = '<TODO>'

client_tidal = tidal.PrivateAPI(scopes=["r_usr", "w_usr", "w_sub"], access_token=tidal_access_token, flow='pkce' )

# initial call to get the total number of tracks
favorite_tracks = client_tidal.get_favorite_tracks(order_direction="ASC", order="NAME", offset=0, limit=1)

number_of_tracks = favorite_tracks['totalNumberOfItems']

# avoid duplicate songs ( some songs are repeated in the favorite tracks)
unique_tracks = set()
unique_lines = []
tidal_songs_file = 'tidal_tracks.txt'

# Open a file in write mode
with open(tidal_songs_file, 'w', encoding='utf-8') as file:
    index = 0
    count = 0
    while index < number_of_tracks:
        favorite_tracks = client_tidal.get_favorite_tracks(order_direction="ASC", order="NAME", offset=index, limit=50)
        index += 50
        for track in favorite_tracks['items']:
            item = track['item']
            count += 1
            title = item['title']
            artists = item['artists']
            artist_names = [artist['name'] for artist in artists]
            
            # Create a dictionary with the title and artists
            track_info = {
                'title': title,
                'artists': artist_names
            }
            
            # Convert the dictionary to a JSON string
            track_info_json = json.dumps(track_info, ensure_ascii=False)
            
            # Check for duplicates
            track_tuple = (title, tuple(artist_names))
            if track_tuple not in unique_tracks:
                unique_tracks.add(track_tuple)
                unique_lines.append(track_info_json)

    # Write the unique lines back to the file
    for line in unique_lines:
        file.write(line + '\n')


# generate with spotify app or use already existing credentials drom your spotify app
# https://developer.spotify.com/dashboard/
spotify_client_id='<TODO>'
spotify_client_secret='<TODO>'

# filter for access_token in networking while using spotify web app
spotify_access_token = '<TODO>'
spotifyClient = spotify.WebAPI(client_id=spotify_client_id, client_secret=spotify_client_secret, access_token=spotify_access_token, flow="authorization_code", scopes=['user-library-modify', 'user-read-private'])

track_ids = []
last_processed = ''
last_count = 0
count_found = 0
count_not_found = 0
count_found_after_modification = 0

# Retry mechanism delays
max_retries = 3
retry_delay = 5  # seconds

# Read the file and collect lines
with open(tidal_songs_file, 'r', encoding='utf-8') as file:
    lines = file.readlines()

not_found_tracks_file = 'not_found_tracks.txt'
modified_titles_file = 'modified_titles.txt'

# Open the not found file in write mode
with open(not_found_tracks_file, 'w', encoding='utf-8') as not_found_file, \
    open(modified_titles_file, 'w', encoding='utf-8') as modified_titles_file:
    processed_lines = []
    for line in lines:
        # Parse the JSON object from the line
        track_info = json.loads(line.strip())
        
        # Extract the title and artists, limit to the first 5 artists if there are more than 5
        title = track_info['title']
        artists = track_info['artists'][:5]
        last_processed = track_info
        last_count += 1
        # Retry mechanism
        for attempt in range(max_retries):
            try:
                # Find the song in Spotify
                search_response = spotifyClient.search(type='track', limit=1, market='US', q=f'artist:{artists}, track:{title}')
                
                # Check if the search was successful
                total = search_response['total']
                if total == 0:
                    not_found_file.write(line.strip() + '\n')

                    # Modify the title by removing specific content within brackets
                    modified_title = re.sub(r'\s*\(.*?(feat\.|Remastered|Album|Remix).*?\)\s*', '', title)
                    modified_title = re.sub(r'\s*\[.*?(feat\.|Remastered|Album|Remix).*?\]\s*', '', modified_title)
                    
                    # Retry search with modified title
                    search_response = spotifyClient.search(type='track', limit=1, market='US', q=f'artist:{artists}, track:{title}')
                    total = search_response['total']
                    if total == 0:
                        print("No track found")
                        count_not_found += 1
                    elif total > 0:
                        
                        # Track found with modified title
                        count_found_after_modification += 1
                        track_id = search_response['tracks']['items'][0]['id']
                        track_ids.append(track_id)
                        processed_lines.append(line.strip())
                        modified_titles_file.write(f'{title} - {modified_title} - {", ".join(artists)}\n')
                        break  # Exit the retry loop if successful

                else:
                    count_found += 1
                    # Extract the track ID
                    track_id = search_response['items'][0]['id']
                    track_ids.append(track_id)
                    processed_lines.append(line.strip())

                break  # Exit the retry loop if successful
            except requests.exceptions.RequestException as e:
                print(f"Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    print("Max retries reached. Skipping this track.")
                    not_found_file.write(line.strip() + '\n')
        
        # Save tracks in batches of 50 (maximum allowed by Spotify)
        if len(track_ids) == 50:
            print(f'Last processed tidal track: {last_processed}')
            print(f'Reached {last_count} tracks')
            spotifyClient.save_tracks(track_ids)
            track_ids = []  

    # Save any remaining track IDs
    if track_ids:
        print(f'Last processed tidal track: {last_processed}')
        print(f'Reached {last_count} tracks')
        spotifyClient.save_tracks(track_ids)

print(f"Total tracks processed: {last_count}, total tracks found {count_found}, total tracks found after slight modification {count_found_after_modification}, total tracks not found {count_not_found}")


