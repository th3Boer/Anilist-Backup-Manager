from flask import Flask, render_template, request, jsonify, send_file, Response, stream_with_context
import os
import json
import shutil
from datetime import datetime
import threading
import time
import requests
import zipfile
import io
import queue

app = Flask(__name__)
sse_queue = queue.Queue()

# --- Configuration for Persistent Data ---
# These paths are relative to WORKDIR /app in the Docker container.
# docker-compose.yml will map host directories to these container paths.
APP_DATA_DIR = "app_data"  # For config, logs, latest_stats
BACKUP_DIR = "backups"     # For backup ZIP files

# Ensure these directories exist within the container's /app directory
os.makedirs(APP_DATA_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

LOGS_FILE = os.path.join(APP_DATA_DIR, "logs.json")
CONFIG_FILE = os.path.join(APP_DATA_DIR, "config.json")
LATEST_STATS_FILE = os.path.join(APP_DATA_DIR, "latest_stats.json")
MAX_LOGS = 100
# --- End Configuration ---

# Auto-Backup Configuration
auto_backup_thread = None
stop_auto_backup = threading.Event()
auto_backup_config = None # This will be loaded from CONFIG_FILE
backup_lock = threading.Lock()


# GraphQL Query
ANILIST_QUERY = """
query ($username: String) {
    MediaListCollection(userName: $username, type: ANIME) {
        lists {
            entries {
                media {
                    id # This is series_animedb_id
                    title {
                        romaji
                    }
                }
                score # User's raw score
                progress
                status
                repeat # For my_times_watched
            }
        }
    }
    MediaListCollection2: MediaListCollection(userName: $username, type: MANGA) {
        lists {
            entries {
                media {
                    id # This is series_mangadb_id
                    title {
                        romaji
                    }
                }
                score # User's raw score
                progress # For my_read_chapters
                progressVolumes # For my_read_volumes
                status
                repeat # For my_times_read
            }
        }
    }
}
"""

def validate_backup_files(backup_dir_path): # backup_dir_path is the temporary staging dir
    required_files = ['anime.json', 'manga.json', 'animemanga_stats.txt', 
                     'anime.xml', 'manga.xml', 'meta.json']
    for filename in required_files:
        file_path = os.path.join(backup_dir_path, filename)
        if not os.path.exists(file_path):
            raise ValueError(f"Missing required file: {filename}")
        if os.path.getsize(file_path) == 0:
            raise ValueError(f"Empty file detected: {filename}")

def validate_backup_zip(zip_path):
    required_files = ['anime.json', 'manga.json', 'animemanga_stats.txt', 
                     'anime.xml', 'manga.xml', 'meta.json']
    with zipfile.ZipFile(zip_path, 'r') as zipf:
        zip_files = zipf.namelist()
        for req_file in required_files:
            matching_files = [f for f in zip_files if f.endswith(req_file)]
            if not matching_files:
                raise ValueError(f"Missing required file in zip: {req_file}")
            file_info = zipf.getinfo(matching_files[0])
            if file_info.file_size == 0:
                raise ValueError(f"Empty file in zip: {req_file}")
            if req_file.endswith('.json'):
                with zipf.open(matching_files[0]) as f:
                    try:
                        data = json.load(f)
                        if not data: # Check for empty list or dict
                             raise ValueError(f"Empty JSON content in: {req_file}")
                    except json.JSONDecodeError:
                        raise ValueError(f"Invalid JSON in: {req_file}")
    return True

def load_config():
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config_data = json.load(f)
                # Basic validation for essential keys
                if isinstance(config_data, dict) and \
                   'username' in config_data and \
                   'keepLast' in config_data and \
                   'interval' in config_data:
                    return config_data
                else:
                    save_log(f"Config file {CONFIG_FILE} is malformed. Ignoring.", False)
                    return None
        return None
    except json.JSONDecodeError:
        save_log(f"Error decoding JSON from config file {CONFIG_FILE}. Ignoring.", False)
        return None
    except Exception as e:
        save_log(f"Error loading config from {CONFIG_FILE}: {str(e)}", False)
        return None

def save_config(config_to_save):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_to_save, f, indent=2)
        save_log("Configuration saved successfully.", True)
    except Exception as e:
        save_log(f"Error saving config to {CONFIG_FILE}: {str(e)}", False)

def load_latest_stats():
    try:
        if os.path.exists(LATEST_STATS_FILE):
            with open(LATEST_STATS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        save_log(f"Error loading latest stats from {LATEST_STATS_FILE}: {str(e)}", False)
    return None

def save_latest_stats(stats_data):
    try:
        with open(LATEST_STATS_FILE, 'w') as f:
            json.dump(stats_data, f, indent=2)
    except Exception as e:
        save_log(f"Error saving latest stats to {LATEST_STATS_FILE}: {str(e)}", False)

def save_log(message, is_success=False):
    log_entry_data = {
        'timestamp': datetime.now().isoformat(),
        'message': message,
        'is_success': is_success
    }
    try:
        logs = []
        if os.path.exists(LOGS_FILE):
            try:
                with open(LOGS_FILE, 'r') as f:
                    logs = json.load(f)
            except json.JSONDecodeError:
                print(f"Warning: {LOGS_FILE} was corrupted. Starting with empty logs.")
                logs = []
            except Exception as e_read:
                print(f"Error reading {LOGS_FILE}: {e_read}. Starting with empty logs.")
                logs = []

        logs.append(log_entry_data)
        logs = logs[-MAX_LOGS:]
        
        with open(LOGS_FILE, 'w') as f:
            json.dump(logs, f, indent=2)

        sse_queue.put({'type': 'log_updated', 'data': log_entry_data})
            
    except Exception as e:
        print(f"CRITICAL: Failed to save log entry or send SSE. Log: {log_entry_data}, Error: {e}")


def fetch_anilist_data(username):
    url = 'https://graphql.anilist.co'
    response = requests.post(url, json={
        'query': ANILIST_QUERY,
        'variables': {'username': username}
    })
    
    if response.status_code == 404:
        raise Exception(f"User '{username}' not found on AniList.")
    if response.status_code != 200:
        raise Exception(f'Failed to fetch data from AniList (Status: {response.status_code})')
    
    return response.json()

def calculate_stats(data):
    anime_entries = []
    manga_entries = []
    
    anime_status = { 'watching': 0, 'completed': 0, 'planning': 0, 'dropped': 0, 'on_hold': 0 }
    manga_status = { 'reading': 0, 'completed': 0, 'planning': 0, 'dropped': 0, 'on_hold': 0 }
    
    anilist_data_prop = data.get('data', {})

    media_list_collection_anime = anilist_data_prop.get('MediaListCollection')
    if media_list_collection_anime and media_list_collection_anime.get('lists'):
        for list_group in media_list_collection_anime['lists']:
            for entry in list_group.get('entries', []):
                anime_entries.append(entry)
                status_key = (entry.get('status', '') or '').lower()
                if status_key == "current": status_key = "watching"
                if status_key == "paused": status_key = "on_hold"
                if status_key in anime_status:
                    anime_status[status_key] += 1
    
    media_list_collection_manga = anilist_data_prop.get('MediaListCollection2')
    if media_list_collection_manga and media_list_collection_manga.get('lists'):
        for list_group in media_list_collection_manga['lists']:
            for entry in list_group.get('entries', []):
                manga_entries.append(entry)
                status_key = (entry.get('status', '') or '').lower()
                if status_key == "current": status_key = "reading"
                if status_key == "paused": status_key = "on_hold"
                if status_key in manga_status:
                    manga_status[status_key] += 1
    
    anime_scores = [e['score'] for e in anime_entries if e.get('score') and e['score'] > 0]
    manga_scores = [e['score'] for e in manga_entries if e.get('score') and e['score'] > 0]

    anime_stats = {
        'totalEntries': len(anime_entries),
        'episodesWatched': sum(entry.get('progress', 0) or 0 for entry in anime_entries),
        'meanScore': round(sum(anime_scores) / len(anime_scores), 1) if anime_scores else 0,
        'status': anime_status,
        'username': data.get('username', '') 
    }
    
    manga_stats = {
        'totalEntries': len(manga_entries),
        'chaptersRead': sum(entry.get('progress', 0) or 0 for entry in manga_entries),
        'volumesRead': sum(entry.get('progressVolumes', 0) or 0 for entry in manga_entries),
        'meanScore': round(sum(manga_scores) / len(manga_scores), 1) if manga_scores else 0,
        'status': manga_status,
        'username': data.get('username', '') 
    }
    
    return anime_stats, manga_stats

def generate_mal_xml(entries, type='anime'):
    xml_header = """<?xml version="1.0" encoding="UTF-8" ?>
<myanimelist>
"""
    entry_template_anime = """  <anime>
    <series_animedb_id>{media_id}</series_animedb_id>
    <series_title><![CDATA[{title}]]></series_title>
    <my_watched_episodes>{progress}</my_watched_episodes>
    <my_score>{score}</my_score>
    <my_status>{status}</my_status>
    <my_times_watched>{rewatched}</my_times_watched>
    <update_on_import>1</update_on_import>
  </anime>
"""
    entry_template_manga = """  <manga>
    <series_mangadb_id>{media_id}</series_mangadb_id>
    <series_title><![CDATA[{title}]]></series_title>
    <my_read_chapters>{progress}</my_read_chapters>
    <my_read_volumes>{progress_volumes}</my_read_volumes>
    <my_score>{score}</my_score>
    <my_status>{status}</my_status>
    <my_times_read>{rewatched}</my_times_read>
    <update_on_import>1</update_on_import>
  </manga>
"""
    # MAL numeric status codes: 1: Watching/Reading, 2: Completed, 3: On-Hold, 4: Dropped, 6: Plan to Watch/Read
    anilist_to_mal_status_map = {
        'CURRENT': '1',    # Watching / Reading
        'COMPLETED': '2',  # Completed
        'PAUSED': '3',     # On-Hold
        'DROPPED': '4',    # Dropped
        'PLANNING': '6',   # Plan to Watch / Plan to Read
        # AniList REPEATING is like CURRENT but with rewatch counter. For MAL, map to Watching/Reading.
        'REPEATING': '1'
    }
    
    formatted_entries = []
    for entry in entries:
        media = entry.get('media', {})
        title = media.get('title', {}).get('romaji', 'N/A Title')
        media_id = media.get('id', 0)
        
        raw_score = entry.get('score') # Could be None or 0
        mal_score = 0 # Default MAL score (no score)
        if raw_score and raw_score > 0:
            if raw_score > 10: # Assumed 0-100 system from AniList
                mal_score = round(raw_score / 10)
            else: # Assumed 0-10 system from AniList or already converted
                mal_score = int(raw_score)
            mal_score = max(0, min(10, mal_score)) # Ensure score is within MAL's 0-10 range

        progress = entry.get('progress', 0) or 0
        rewatched = entry.get('repeat', 0) or 0 # AniList 'repeat' maps to MAL 'my_times_watched'/'my_times_read'
        
        anilist_status = entry.get('status', 'PLANNING') # Default to PLANNING if status is missing
        mal_status_code = anilist_to_mal_status_map.get(anilist_status, '6') # Default to Plan to Watch/Read

        if type == 'anime':
            formatted_entries.append(entry_template_anime.format(
                media_id=media_id, title=title, score=mal_score, status=mal_status_code, progress=progress, rewatched=rewatched
            ))
        else: # manga
            progress_volumes = entry.get('progressVolumes', 0) or 0
            formatted_entries.append(entry_template_manga.format(
                media_id=media_id, title=title, score=mal_score, status=mal_status_code, progress=progress, progress_volumes=progress_volumes, rewatched=rewatched
            ))
            
    xml_footer = "</myanimelist>"
    return xml_header + '\\n'.join(formatted_entries) + '\\n' + xml_footer

def create_backup(username):
    save_log(f"Attempting to create backup for user: {username}", is_success=True)
    try:
        raw_data = fetch_anilist_data(username)
        raw_data['username'] = username 
        anime_stats, manga_stats = calculate_stats(raw_data)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_id = f"{username}_{timestamp}"
        meta_data = None 
        
        temp_staging_dir_path = os.path.join(BACKUP_DIR, f"_TEMP_{backup_id}")
        os.makedirs(temp_staging_dir_path, exist_ok=True)
        zip_path_final = os.path.join(BACKUP_DIR, f"{backup_id}.zip")

        try:
            anime_data_list = []
            manga_data_list = []
            
            anilist_data_prop = raw_data.get('data', {})
            media_list_collection_anime = anilist_data_prop.get('MediaListCollection')
            if media_list_collection_anime and media_list_collection_anime.get('lists'):
                for list_group in media_list_collection_anime['lists']:
                    anime_data_list.extend(list_group.get('entries', []))
                    
            media_list_collection_manga = anilist_data_prop.get('MediaListCollection2')
            if media_list_collection_manga and media_list_collection_manga.get('lists'):
                for list_group in media_list_collection_manga['lists']:
                    manga_data_list.extend(list_group.get('entries', []))

            with open(os.path.join(temp_staging_dir_path, 'anime.json'), 'w', encoding='utf-8') as f:
                json.dump(anime_data_list, f, ensure_ascii=False, indent=2)
            with open(os.path.join(temp_staging_dir_path, 'manga.json'), 'w', encoding='utf-8') as f:
                json.dump(manga_data_list, f, ensure_ascii=False, indent=2)

            stats_text = f"""Anime & Manga Statistics for {username}
Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{json.dumps({'anime': anime_stats, 'manga': manga_stats}, indent=2)}
"""
            with open(os.path.join(temp_staging_dir_path, 'animemanga_stats.txt'), 'w', encoding='utf-8') as f:
                f.write(stats_text)

            anime_xml = generate_mal_xml(anime_data_list, 'anime')
            manga_xml = generate_mal_xml(manga_data_list, 'manga')
            with open(os.path.join(temp_staging_dir_path, 'anime.xml'), 'w', encoding='utf-8') as f: f.write(anime_xml)
            with open(os.path.join(temp_staging_dir_path, 'manga.xml'), 'w', encoding='utf-8') as f: f.write(manga_xml)
            
            meta_data = {
                'id': backup_id, 'date': datetime.now().isoformat(), 'username': username,
                'stats': {'anime': anime_stats, 'manga': manga_stats}
            }
            with open(os.path.join(temp_staging_dir_path, 'meta.json'), 'w', encoding='utf-8') as f:
                json.dump(meta_data, f, ensure_ascii=False, indent=2)
            
            validate_backup_files(temp_staging_dir_path)

            with zipfile.ZipFile(zip_path_final, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for filename in ['anime.json', 'manga.json', 'animemanga_stats.txt', 'anime.xml', 'manga.xml', 'meta.json']:
                    zipf.write(os.path.join(temp_staging_dir_path, filename), filename)
            
            validate_backup_zip(zip_path_final)

            save_latest_stats({'anime': anime_stats, 'manga': manga_stats, 'username': username, 'last_updated': meta_data['date']})
            sse_queue.put({'type': 'backup_created', 'data': {'username': username, 'timestamp': meta_data['date'], 'stats': {'anime': anime_stats, 'manga': manga_stats}}})
            save_log(f"Successfully created backup for {username}. ID: {backup_id}", True)
            return meta_data

        except Exception as e_inner:
            if os.path.exists(zip_path_final): os.remove(zip_path_final)
            save_log(f"Inner backup process failed for {username}: {str(e_inner)}", False)
            raise
        finally:
            if os.path.exists(temp_staging_dir_path):
                shutil.rmtree(temp_staging_dir_path)
            
    except Exception as e:
        save_log(f"Overall backup creation failed for {username}: {str(e)}", False)
        raise 

def auto_backup_task():
    global auto_backup_config
    while not stop_auto_backup.is_set():
        try:
            if auto_backup_config:
                username = auto_backup_config.get('username')
                keep_last = int(auto_backup_config.get('keepLast', 1))
                interval_hours = float(auto_backup_config.get('interval', 24))

                if not username:
                    save_log("Auto backup task: Username missing in config. Stopping task.", False)
                    stop_auto_backup.set() 
                    auto_backup_config = None 
                    if os.path.exists(CONFIG_FILE): os.remove(CONFIG_FILE)
                    break 

                save_log(f"Auto backup task: Starting backup for {username}.", True)
                try:
                    create_backup(username)
                    with backup_lock:
                        backups = get_user_backups(username)
                        if len(backups) > keep_last:
                            backups_to_delete = sorted(backups, key=lambda x: x['date'])[:-keep_last]
                            for backup_meta in backups_to_delete:
                                save_log(f"Auto backup: Deleting old backup {backup_meta['id']} for user {username}", True)
                                delete_backup_file(backup_meta['id'])
                except Exception as backup_error:
                    save_log(f"Auto backup task error during backup/cleanup for {username}: {str(backup_error)}", False)
                
                sleep_duration_seconds = interval_hours * 3600
                sleep_interval_check = 60 
                elapsed_sleep = 0
                while elapsed_sleep < sleep_duration_seconds and not stop_auto_backup.is_set():
                    time.sleep(min(sleep_interval_check, sleep_duration_seconds - elapsed_sleep))
                    elapsed_sleep += sleep_interval_check
            else: 
                if stop_auto_backup.is_set(): break
                save_log("Auto backup task: No configuration found. Waiting for configuration.", False)
                time.sleep(300) 
        except Exception as e:
            save_log(f"Critical error in auto backup loop: {str(e)}", False)
            time.sleep(60)


def get_user_backups(username_filter=None):
    backups = []
    if not os.path.exists(BACKUP_DIR):
        return backups
    try:
        for filename in os.listdir(BACKUP_DIR):
            if filename.endswith('.zip') and not filename.startswith("_TEMP_"):
                if username_filter and not filename.startswith(f"{username_filter}_"):
                    continue
                try:
                    zip_file_path = os.path.join(BACKUP_DIR, filename)
                    with zipfile.ZipFile(zip_file_path, 'r') as zipf:
                        if 'meta.json' in zipf.namelist():
                            with zipf.open('meta.json') as f_meta:
                                backup_data = json.load(io.TextIOWrapper(f_meta, encoding='utf-8'))
                                backups.append({
                                    'id': backup_data.get('id', filename[:-4]),
                                    'date': backup_data.get('date', 'N/A'),
                                    'username': backup_data.get('username', 'N/A'),
                                    'content': f"{backup_data.get('stats', {}).get('anime', {}).get('totalEntries', 0)} Anime, {backup_data.get('stats', {}).get('manga', {}).get('totalEntries', 0)} Manga"
                                })
                        else:
                            save_log(f"meta.json not found in backup {filename}", False)
                except (zipfile.BadZipFile, json.JSONDecodeError) as e_zip:
                    save_log(f"Corrupted backup file {filename} or meta.json: {str(e_zip)}", False)
                except Exception as e_inner:
                     save_log(f"Error processing backup file {filename}: {str(e_inner)}", False)
    except Exception as e:
        save_log(f"Error listing user backups from {BACKUP_DIR}: {str(e)}", False)
    return sorted(backups, key=lambda x: x['date'], reverse=True)

def delete_backup_file(backup_id):
    try:
        backup_path = os.path.join(BACKUP_DIR, f"{backup_id}.zip")
        if os.path.exists(backup_path):
            os.remove(backup_path)
            save_log(f"Deleted backup {backup_id}", True)
            return True
        save_log(f"Attempted to delete non-existent backup {backup_id}", False)
        return False
    except Exception as e:
        save_log(f"Error deleting backup file {backup_id}: {str(e)}", False)
        return False

@app.route('/')
def index():
    latest_stats_data = load_latest_stats()
    return render_template('index.html', latest_stats=latest_stats_data)

@app.route('/latest-stats')
def get_latest_stats_route():
    stats = load_latest_stats()
    return jsonify(stats if stats else {})


@app.route('/events')
def events():
    def event_stream():
        while True:
            try:
                message = sse_queue.get(timeout=25)
                yield f"data: {json.dumps(message)}\\n\\n"
            except queue.Empty:
                yield "event: keep-alive\\ndata: {}\\n\\n" 
            except GeneratorExit: 
                break
            except Exception as e_stream:
                print(f"Error in SSE event stream: {e_stream}")
                break 
            
    return Response(stream_with_context(event_stream()),
                   mimetype='text/event-stream',
                   headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no', 'Connection': 'keep-alive'})


@app.route('/backup', methods=['POST'])
def manual_backup_route():
    username = None
    data = None
    try:
        data = request.get_json()
        if not data or not data.get('username'): 
            save_log('Manual backup: Username is required, but not provided or data is malformed.', False)
            return jsonify({'error': 'Username is required.'}), 400
        username = data.get('username')
        
        save_log(f"Manual backup initiated for user: {username}", True)
        backup_meta = create_backup(username) 
        return jsonify({'status': 'success', 'message': f'Backup successfully created for {username}.', 'data': backup_meta})
        
    except Exception as e:
        user_str = username if username else (data.get('username', 'N/A') if isinstance(data, dict) else 'N/A')
        save_log(f"Manual backup route error for user '{user_str}': {str(e)}", False)
        return jsonify({'error': str(e)}), 500

@app.route('/auto-backup', methods=['POST'])
def start_auto_backup_route():
    global auto_backup_thread, auto_backup_config
    try:
        data = request.get_json()
        username = data.get('username')
        keep_last_str = data.get('keepLast')
        interval_str = data.get('interval')

        if not all([username, keep_last_str, interval_str]):
            save_log('Auto-backup start: Missing required fields.', False)
            return jsonify({'error': 'All fields (username, keepLast, interval) are required'}), 400
        
        try:
            keep_last = int(keep_last_str)
            interval = float(interval_str)
            if keep_last <= 0 or interval <= 0:
                save_log(f'Auto-backup start: Invalid keepLast/interval for {username}. Must be > 0.', False)
                return jsonify({'error': 'Keep last and interval must be positive numbers.'}), 400
        except ValueError:
            save_log(f'Auto-backup start: Invalid number format for keepLast/interval for {username}.', False)
            return jsonify({'error': 'Invalid number format for keepLast or interval.'}), 400
        
        if auto_backup_thread and auto_backup_thread.is_alive():
            save_log("Stopping existing auto-backup thread before starting new one.", True)
            stop_auto_backup.set()
            auto_backup_thread.join(timeout=10)
        
        stop_auto_backup.clear()
        auto_backup_config = {'username': username, 'keepLast': keep_last, 'interval': interval}
        save_config(auto_backup_config)
        
        auto_backup_thread = threading.Thread(target=auto_backup_task, daemon=True)
        auto_backup_thread.start()
        
        save_log(f"Auto backup started for {username}, interval: {interval} hours, keep: {keep_last}", True)
        return jsonify({'status': 'success', 'message': f'Auto backup started for {username}.', 'config': auto_backup_config})
    except Exception as e:
        save_log(f"Failed to start auto backup: {str(e)}", False)
        auto_backup_config = None 
        stop_auto_backup.set()
        if os.path.exists(CONFIG_FILE):
            try: os.remove(CONFIG_FILE)
            except OSError as oe: save_log(f"Error removing config during auto-backup start failure: {str(oe)}", False)
        return jsonify({'error': str(e)}), 500

@app.route('/stop-auto-backup', methods=['POST'])
def stop_auto_backup_route():
    global auto_backup_config, auto_backup_thread
    try:
        save_log("Attempting to stop auto backup...", True)
        stop_auto_backup.set()
        if auto_backup_thread and auto_backup_thread.is_alive():
            auto_backup_thread.join(timeout=10)
        
        auto_backup_config = None
        auto_backup_thread = None
        
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
            save_log("Removed auto backup configuration file.", True)
            
        save_log("Auto backup stopped successfully.", True)
        return jsonify({'status': 'success', 'message': 'Auto backup stopped.'})
    except Exception as e:
        save_log(f"Error stopping auto backup: {str(e)}", False)
        return jsonify({'error': str(e)}), 500

@app.route('/auto-backup-status')
def get_auto_backup_status_route():
    is_running = bool(auto_backup_thread and auto_backup_thread.is_alive() and not stop_auto_backup.is_set())
    current_config_to_display = auto_backup_config if is_running else load_config()
    return jsonify({'running': is_running, 'config': current_config_to_display})


@app.route('/backups')
def get_backups_route():
    try:
        all_backups = get_user_backups() 
        return jsonify(all_backups)
    except Exception as e:
        save_log(f"Error in /backups route: {str(e)}", False)
        return jsonify({'error': str(e)}), 500

@app.route('/backup/<backup_id>/stats')
def get_backup_stats_route(backup_id):
    try:
        zip_path = os.path.join(BACKUP_DIR, f"{backup_id}.zip")
        if not os.path.exists(zip_path):
            return jsonify({'error': 'Backup not found'}), 404
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            if 'meta.json' in zipf.namelist():
                with zipf.open('meta.json') as f_meta:
                    backup_data = json.load(io.TextIOWrapper(f_meta, encoding='utf-8'))
                    return jsonify(backup_data.get('stats', {}))
            return jsonify({'error': 'meta.json not found in backup'}), 404
    except Exception as e:
        save_log(f"Error getting backup stats for {backup_id}: {str(e)}", False)
        return jsonify({'error': str(e)}), 500

@app.route('/backup/<backup_id>/download')
def download_backup_route(backup_id):
    try:
        backup_path = os.path.join(BACKUP_DIR, f"{backup_id}.zip")
        if not os.path.exists(backup_path):
            return jsonify({'error': 'Backup not found'}), 404
        return send_file(backup_path, mimetype='application/zip', as_attachment=True, download_name=f"{backup_id}.zip")
    except Exception as e:
        save_log(f"Error downloading backup {backup_id}: {str(e)}", False)
        return jsonify({'error': str(e)}), 500

@app.route('/backup/<backup_id>', methods=['DELETE'])
def delete_backup_route(backup_id):
    try:
        if delete_backup_file(backup_id):
            sse_queue.put({'type': 'backup_deleted', 'data': {'id': backup_id }})
            all_backups = get_user_backups()
            if all_backups:
                latest_backup_meta_path = os.path.join(BACKUP_DIR, f"{all_backups[0]['id']}.zip")
                new_latest_stats = None
                try:
                    with zipfile.ZipFile(latest_backup_meta_path, 'r') as zipf_latest:
                        if 'meta.json' in zipf_latest.namelist():
                            with zipf_latest.open('meta.json') as f_latest_meta:
                                latest_meta = json.load(io.TextIOWrapper(f_latest_meta, encoding='utf-8'))
                                new_latest_stats = {
                                    'anime': latest_meta['stats']['anime'],
                                    'manga': latest_meta['stats']['manga'],
                                    'username': latest_meta['username'],
                                    'last_updated': latest_meta['date']
                                }
                    if new_latest_stats:
                        save_latest_stats(new_latest_stats)
                        sse_queue.put({'type': 'latest_stats_updated', 'data': new_latest_stats})
                    else: 
                        if os.path.exists(LATEST_STATS_FILE): os.remove(LATEST_STATS_FILE)
                        sse_queue.put({'type': 'latest_stats_updated', 'data': {}})
                except Exception as e_stat_update:
                    save_log(f"Error updating latest stats after delete: {e_stat_update}", False)
                    if os.path.exists(LATEST_STATS_FILE): os.remove(LATEST_STATS_FILE)
                    sse_queue.put({'type': 'latest_stats_updated', 'data': {}})
            else: 
                if os.path.exists(LATEST_STATS_FILE): os.remove(LATEST_STATS_FILE)
                sse_queue.put({'type': 'latest_stats_updated', 'data': {}})

            return jsonify({'status': 'success'})
        return jsonify({'error': 'Backup not found or deletion failed'}), 404
    except Exception as e:
        save_log(f"Error deleting backup {backup_id} via route: {str(e)}", False)
        return jsonify({'error': str(e)}), 500

@app.route('/logs')
def get_logs_route():
    try:
        if os.path.exists(LOGS_FILE):
            with open(LOGS_FILE, 'r') as f:
                logs_data = json.load(f)
                return jsonify(logs_data)
        return jsonify([])
    except Exception as e:
        save_log(f"Error getting logs: {str(e)}", False)
        return jsonify({'error': f"Error reading logs: {str(e)}"}), 500

@app.route('/save-log', methods=['POST']) 
def save_log_client_route():
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'Message is required'}), 400
        save_log(f"[CLIENT] {data['message']}", data.get('isSuccess', False))
        return jsonify({'status': 'success'})
    except Exception as e:
        print(f"Error in /save-log route: {str(e)}")
        return jsonify({'error': str(e)}), 500

def initialize_auto_backup():
    global auto_backup_thread, auto_backup_config
    
    loaded_config = load_config()
    if loaded_config:
        save_log(f"Found auto-backup configuration: {loaded_config}", True)
        
        username = loaded_config.get('username')
        try:
            keep_last = int(loaded_config.get('keepLast', 0))
            interval = float(loaded_config.get('interval', 0))
        except (ValueError, TypeError):
            keep_last = 0
            interval = 0
            save_log("Invalid numeric values in loaded auto-backup config.", False)

        if username and keep_last > 0 and interval > 0:
            auto_backup_config = loaded_config
            stop_auto_backup.clear()
            
            if auto_backup_thread and auto_backup_thread.is_alive():
                 save_log("Auto backup thread already running (unexpected). Stopping it first.", False)
                 stop_auto_backup.set()
                 auto_backup_thread.join(timeout=5)

            auto_backup_thread = threading.Thread(target=auto_backup_task, daemon=True)
            auto_backup_thread.start()
            save_log(f"Restored and started auto backup for '{username}' on application start. Interval: {interval}h, Keep: {keep_last}.", True)
        else:
            save_log(f"Loaded auto-backup config for '{username}' is incomplete or invalid (Keep: {keep_last}, Interval: {interval}). Auto-backup not started. Please reconfigure.", False)
            auto_backup_config = None
            if os.path.exists(CONFIG_FILE):
                try:
                    os.remove(CONFIG_FILE)
                    save_log("Removed invalid/incomplete auto-backup configuration file.", True)
                except OSError as oe:
                    save_log(f"Error removing invalid config file {CONFIG_FILE}: {str(oe)}", False)
    else:
        save_log("No auto-backup configuration found on application start.", True)
        auto_backup_config = None


if __name__ == '__main__':
    save_log("AniVault application starting up...", True)
    initialize_auto_backup()
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)
