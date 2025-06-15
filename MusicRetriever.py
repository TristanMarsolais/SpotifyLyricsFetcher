import os
import re
import json
import requests
from bs4 import BeautifulSoup
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv

# ─────────────────────────────────────────────────────────────────────────────
# Configuration & Spotify Setup
# ─────────────────────────────────────────────────────────────────────────────

load_dotenv()
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
    raise ValueError("Spotify credentials not found in .env file")

sp = Spotify(auth_manager=SpotifyClientCredentials(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET
))


# ─────────────────────────────────────────────────────────────────────────────
# Utility Functions
# ─────────────────────────────────────────────────────────────────────────────

def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', "", filename)


def slugify(text):
    text = re.sub(r"[’'`]", "", text)
    text = re.sub(r"[^\w\s-]", "", text)
    text = text.replace("&", "and")
    return re.sub(r"\s+", "-", text.strip().lower())


def format_for_genius_url(artist, title):
    artist_slug = slugify(artist)
    title_slug = slugify(title)
    return f"https://genius.com/{artist_slug}-{title_slug}-lyrics"


# ─────────────────────────────────────────────────────────────────────────────
# Lyrics Processing
# ─────────────────────────────────────────────────────────────────────────────

def scrape_lyrics_from_genius(artist, title):
    url = format_for_genius_url(artist, title)
    headers = {"User-Agent": "Mozilla/5.0"}

    print(f"🔎 Fetching lyrics: {url}")
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"   ❌ Genius page not found ({response.status_code})")
        return None

    soup = BeautifulSoup(response.text, "lxml")
    lyrics_divs = soup.select("div[class^='Lyrics__Container']")
    if not lyrics_divs:
        print("   ❌ No lyrics containers found.")
        return None

    lyrics = "\n".join(div.get_text(separator="\n") for div in lyrics_divs)
    return lyrics.strip()


def parse_lyrics_sections(lyrics_text):
    sections = []
    current_section = {"section": "Intro", "lyrics": []}

    for line in lyrics_text.splitlines():
        line = line.strip()
        if not line:
            continue

        match = re.match(r"\[(.*?)\]", line)
        if match:
            if current_section["lyrics"]:
                sections.append(current_section)
            current_section = {"section": match.group(1), "lyrics": []}
        else:
            current_section["lyrics"].append(line)

    if current_section["lyrics"]:
        sections.append(current_section)

    return sections


# ─────────────────────────────────────────────────────────────────────────────
# Spotify Metadata & Saving
# ─────────────────────────────────────────────────────────────────────────────

def extract_spotify_metadata(spotify_url):
    track_id = spotify_url.split("/")[-1].split("?")[0]
    track = sp.track(track_id)

    return {
        "title": track['name'],
        "artist": track['artists'][0]['name'],
        "album": track['album']['name']
    }


def save_to_directory(metadata, lyrics_text, output_dir="hotvectors_lyrics"):
    os.makedirs(output_dir, exist_ok=True)
    filename = sanitize_filename(f"{metadata['artist']} - {metadata['title']}.json")
    filepath = os.path.join(output_dir, filename)

    lyrics_sections = parse_lyrics_sections(lyrics_text or "")

    data = {
        "title": metadata["title"],
        "artist": metadata["artist"],
        "album": metadata["album"],
        "lyrics": lyrics_sections
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print(f"✅ Saved: {filepath}")


# ─────────────────────────────────────────────────────────────────────────────
# Main Handlers
# ─────────────────────────────────────────────────────────────────────────────

def process_song(spotify_url, output_dir="hotvectors_lyrics"):
    metadata = extract_spotify_metadata(spotify_url)
    print(f"🎵 Processing: {metadata['title']} by {metadata['artist']}")
    lyrics = scrape_lyrics_from_genius(metadata['artist'], metadata['title'])

    if not lyrics:
        print("   ⚠️ Lyrics not found.")
        return

    save_to_directory(metadata, lyrics, output_dir)


def process_playlist(playlist_url, output_dir="hotvectors_lyrics"):
    playlist_id = playlist_url.split("/")[-1].split("?")[0]
    results = sp.playlist_tracks(playlist_id)

    print(f"\n📂 Processing playlist with {len(results['items'])} tracks...\n")

    for idx, item in enumerate(results['items']):
        track = item.get('track')
        if not track:
            print(f"[{idx}] ⚠️ Skipping missing track.")
            continue

        metadata = {
            "title": track['name'],
            "artist": track['artists'][0]['name'],
            "album": track['album']['name']
        }

        print(f"[{idx + 1}] 🎵 {metadata['title']} by {metadata['artist']}")
        lyrics = scrape_lyrics_from_genius(metadata['artist'], metadata['title'])

        if not lyrics:
            print(f"   ❌ Lyrics not found for: {metadata['title']}")
            continue

        save_to_directory(metadata, lyrics, output_dir)


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Example for single track:
    # process_song("https://open.spotify.com/track/3n3Ppam7vgaVa1iaRUc9Lp")

    # Example for playlist:
    process_playlist("https://open.spotify.com/playlist/3p9QX64O6z2mpMy2G6eJbQ?si=IWOVltyvQE6jtRoPbQ84Nw")
