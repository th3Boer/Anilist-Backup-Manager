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

# Global variables
BACKUP_DIR = "backups"
LOGS_FILE = "logs.json"
CONFIG_FILE = "config.json"
LATEST_STATS_FILE = "latest_stats.json" # For persistent stats
MAX_LOGS = 100

# Auto-Backup Configuration
auto_backup_thread = None
stop_auto_backup = threading.Event()
auto_backup_config = None
backup_lock = threading.Lock()

# Create directories
if not os.path.exists(BACKUP_DIR):
    os.makedirs(BACKUP_DIR)

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
                score
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
                score
                progress # For my_read_chapters
                progressVolumes # For my_read_volumes
                status
                repeat # For my_times_read
            }
        }
    }
}
"""

def validate_backup_files(backup_dir):
    """
    Validates that all required files exist and are non-empty in the backup directory
    """
    required_files = ['anime.json', 'manga.json', 'animemanga_stats.txt', 
                     'anime.xml', 'manga.xml', 'meta.json']
    
    for filename in required_files:
        file_path = os.path.join(backup_dir, filename)
        if not os.path.exists(file_path):
            raise ValueError(f"Missing required file: {filename}")
        if os.path.getsize(file_path) == 0:
            raise ValueError(f"Empty file detected: {filename}")

def validate_backup_zip(zip_path):
    """
    Validates that a backup ZIP contains all required files and they are non-empty
    """
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
                        if not data:
                            raise ValueError(f"Empty JSON content in: {req_file}")
                    except json.JSONDecodeError:
                        raise ValueError(f"Invalid JSON in: {req_file}")
    
    return True

def load_config():
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        # Use a distinct message for this specific log to avoid recursion if save_log calls load_config
        print(f"Error directly in load_config: {str(e)}") 
    return None

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)
    except Exception as e:
        save_log(f"Error saving config: {str(e)}")

def load_latest_stats():
    try:
        if os.path.exists(LATEST_STATS_FILE):
            with open(LATEST_STATS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        save_log(f"Error loading latest stats: {str(e)}")
    return None

def save_latest_stats(stats_data):
    try:
        with open(LATEST_STATS_FILE, 'w') as f:
            json.dump(stats_data, f, indent=2)
    except Exception as e:
        save_log(f"Error saving latest stats: {str(e)}")

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
                print(f"Warning: logs.json was corrupted. Starting with empty logs.")
                logs = []
            except Exception as e_read:
                print(f"Error reading logs.json: {e_read}. Starting with empty logs.")
                logs = []

        logs.append(log_entry_data)
        logs = logs[-MAX_LOGS:]
        
        with open(LOGS_FILE, 'w') as f:
            json.dump(logs, f)

        # Send SSE event to update logs on the frontend
        sse_queue.put({'type': 'log_updated', 'data': log_entry_data})
            
    except Exception as e:
        # Fallback to print if saving log or sending SSE fails, to avoid recursion
        print(f"CRITICAL: Failed to save log entry or send SSE event. Log: {log_entry_data}, Error: {e}")


def fetch_anilist_data(username):
    url = 'https://graphql.anilist.co'
    response = requests.post(url, json={
        'query': ANILIST_QUERY,
        'variables': {'username': username}
    })
    
    if response.status_code == 404:
        raise Exception(f"User '{username}' not found on AniList.")
    if response.status_code != 200:
        raise Exception(f'Failed to fetch data from Anilist (Status: {response.status_code})')
    
    return response.json()

def calculate_stats(data):
    anime_entries = []
    manga_entries = []
    
    anime_status = { 'watching': 0, 'completed': 0, 'planning': 0, 'dropped': 0, 'on_hold': 0 }
    manga_status = { 'reading': 0, 'completed': 0, 'planning': 0, 'dropped': 0, 'on_hold': 0 }
    
    # Ensure 'data' and its nested keys exist before trying to access them
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
    status_map_anime = { 'CURRENT': 'Watching', 'COMPLETED': 'Completed', 'PLANNING': 'Plan to Watch', 'DROPPED': 'Dropped', 'PAUSED': 'On-Hold' }
    status_map_manga = { 'CURRENT': 'Reading', 'COMPLETED': 'Completed', 'PLANNING': 'Plan to Read', 'DROPPED': 'Dropped', 'PAUSED': 'On-Hold' }
    
    formatted_entries = []
    for entry in entries:
        media = entry.get('media', {})
        title = media.get('title', {}).get('romaji', 'N/A Title')
        media_id = media.get('id', 0)
        score = int(entry.get('score', 0) or 0)
        progress = entry.get('progress', 0) or 0
        rewatched = entry.get('repeat', 0) or 0
        entry_status_val = entry.get('status', 'PLANNING') # Default to PLANNING if status is missing

        if type == 'anime':
            status_str = status_map_anime.get(entry_status_val, 'Plan to Watch')
            formatted_entries.append(entry_template_anime.format(
                media_id=media_id, title=title, score=score, status=status_str, progress=progress, rewatched=rewatched
            ))
        else: 
            status_str = status_map_manga.get(entry_status_val, 'Plan to Read')
            progress_volumes = entry.get('progressVolumes', 0) or 0
            formatted_entries.append(entry_template_manga.format(
                media_id=media_id, title=title, score=score, status=status_str, progress=progress, progress_volumes=progress_volumes, rewatched=rewatched
            ))
            
    xml_footer = "</myanimelist>"
    return xml_header + '\n'.join(formatted_entries) + '\n' + xml_footer

def create_backup(username):
    # Log an attempt at the very beginning, before any potentially failing operations
    save_log(f"Attempting to create backup for user: {username}", is_success=True) # Mark as success for now, will log failure if it occurs
    try:
        raw_data = fetch_anilist_data(username)
        raw_data['username'] = username 
        anime_stats, manga_stats = calculate_stats(raw_data)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_id = f"{username}_{timestamp}"
        meta_data = None 
        
        with backup_lock:
            backup_dir_path = os.path.join(BACKUP_DIR, backup_id) # Renamed to avoid conflict
            os.makedirs(backup_dir_path, exist_ok=True)
            zip_path = None

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

                with open(os.path.join(backup_dir_path, 'anime.json'), 'w', encoding='utf-8') as f:
                    json.dump(anime_data_list, f, ensure_ascii=False, indent=2)
                with open(os.path.join(backup_dir_path, 'manga.json'), 'w', encoding='utf-8') as f:
                    json.dump(manga_data_list, f, ensure_ascii=False, indent=2)

                stats_text = f"""Anime & Manga Statistics for {username}
Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{json.dumps({'anime': anime_stats, 'manga': manga_stats}, indent=2)}
"""
                with open(os.path.join(backup_dir_path, 'animemanga_stats.txt'), 'w', encoding='utf-8') as f:
                    f.write(stats_text)

                anime_xml = generate_mal_xml(anime_data_list, 'anime')
                manga_xml = generate_mal_xml(manga_data_list, 'manga')
                with open(os.path.join(backup_dir_path, 'anime.xml'), 'w', encoding='utf-8') as f: f.write(anime_xml)
                with open(os.path.join(backup_dir_path, 'manga.xml'), 'w', encoding='utf-8') as f: f.write(manga_xml)
                
                meta_data = {
                    'id': backup_id, 'date': datetime.now().isoformat(), 'username': username,
                    'stats': {'anime': anime_stats, 'manga': manga_stats}
                }
                with open(os.path.join(backup_dir_path, 'meta.json'), 'w', encoding='utf-8') as f:
                    json.dump(meta_data, f, ensure_ascii=False, indent=2)
                    
                zip_path = os.path.join(BACKUP_DIR, f"{backup_id}.zip")
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for filename in ['anime.json', 'manga.json', 'animemanga_stats.txt', 'anime.xml', 'manga.xml', 'meta.json']:
                        zipf.write(os.path.join(backup_dir_path, filename), filename)
                
                shutil.rmtree(backup_dir_path)
                                
                save_latest_stats({'anime': anime_stats, 'manga': manga_stats, 'username': username, 'last_updated': meta_data['date']})
                sse_queue.put({'type': 'backup_created', 'data': {'username': username, 'timestamp': meta_data['date'], 'stats': {'anime': anime_stats, 'manga': manga_stats}}})
                save_log(f"Successfully created backup for {username}. ID: {backup_id}", True)
                return meta_data

            except Exception as e_inner:
                if os.path.exists(backup_dir_path): shutil.rmtree(backup_dir_path)
                if zip_path and os.path.exists(zip_path): os.remove(zip_path)
                # Log this specific inner failure before re-raising
                save_log(f"Inner backup process failed for {username}: {str(e_inner)}", False)
                raise e_inner 
            
    except Exception as e:
        save_log(f"Overall backup creation failed for {username}: {str(e)}", False)
        raise # Re-raise to be caught by the route handler

def auto_backup_task():
    global auto_backup_config
    while not stop_auto_backup.is_set():
        try:
            if auto_backup_config:
                username = auto_backup_config.get('username')
                keep_last = int(auto_backup_config.get('keepLast', 1))
                interval_hours = float(auto_backup_config.get('interval', 1))
                if username and keep_last > 0:
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
                time.sleep(5)
        except Exception as e:
            save_log(f"Critical error in auto backup loop: {str(e)}", False)
            time.sleep(60)

def get_user_backups(username_filter=None):
    backups = []
    if not os.path.exists(BACKUP_DIR): # Ensure backup dir exists
        return backups
    try:
        for filename in os.listdir(BACKUP_DIR):
            if filename.endswith('.zip'):
                if username_filter and not filename.startswith(f"{username_filter}_"):
                    continue
                try:
                    with zipfile.ZipFile(os.path.join(BACKUP_DIR, filename), 'r') as zipf:
                        if 'meta.json' in zipf.namelist():
                            with zipf.open('meta.json') as f:
                                backup_data = json.load(io.TextIOWrapper(f, encoding='utf-8'))
                                backups.append({
                                    'id': backup_data.get('id', filename[:-4]),
                                    'date': backup_data.get('date', 'N/A'),
                                    'username': backup_data.get('username', 'N/A'),
                                    'content': f"{backup_data.get('stats', {}).get('anime', {}).get('totalEntries', 0)} Anime, {backup_data.get('stats', {}).get('manga', {}).get('totalEntries', 0)} Manga"
                                })
                        else:
                            save_log(f"meta.json not found in backup {filename}", False)
                except Exception as e_inner:
                     save_log(f"Error processing backup file {filename}: {str(e_inner)}", False)
    except Exception as e:
        save_log(f"Error listing user backups: {str(e)}", False)
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
    return jsonify(stats if stats else {}) # Return empty object if no stats


@app.route('/events')
def events():
    def event_stream():
        # Immediately send a "connected" or "init" event if needed
        # sse_queue.put({"type": "sse_connected", "data": "Connection established"}) 
        while True:
            try:
                message = sse_queue.get(timeout=25) # Slightly lower timeout
                yield f"data: {json.dumps(message)}\n\n"
            except queue.Empty:
                yield "event: keep-alive\ndata: {}\n\n" # Explicit keep-alive event
            except GeneratorExit: 
                break
            except Exception as e_stream:
                # Log this error on the server side
                print(f"Error in SSE event stream: {e_stream}") # Use print to avoid save_log recursion
                # Optionally, try to inform the client if possible, though the connection might be broken
                # yield f"event: error\ndata: {json.dumps({'message': 'SSE stream error occurred'})}\n\n"
                break # Stop this stream on error
            
    return Response(stream_with_context(event_stream()),
                   mimetype='text/event-stream',
                   headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no', 'Connection': 'keep-alive'})


@app.route('/backup', methods=['POST'])
def manual_backup_route(): # Renamed to avoid confusion with function
    username = None
    try:
        data = request.get_json()
        if not data or not data.get('username'): # Check if data itself is None
            save_log('Manual backup: Username is required, but not provided or data is malformed.', False)
            return jsonify({'error': 'Username is required.'}), 400
        username = data.get('username')
        
        save_log(f"Manual backup initiated for user: {username}", True) # Log initiation
        backup_meta = create_backup(username) 
        # Success is logged within create_backup, SSE event also sent from there
        return jsonify({'status': 'success', 'message': f'Backup successfully created for {username}.', 'data': backup_meta})
        
    except Exception as e:
        # Error should have been logged by create_backup or fetch_anilist_data
        # but we add a route-level log too for clarity.
        user_str = username if username else data.get('username', 'N/A') if isinstance(data, dict) else 'N/A'
        save_log(f"Manual backup route error for user '{user_str}': {str(e)}", False)
        return jsonify({'error': str(e)}), 500

@app.route('/auto-backup', methods=['POST'])
def start_auto_backup():
    global auto_backup_thread, auto_backup_config
    try:
        data = request.get_json()
        username = data.get('username')
        keep_last = data.get('keepLast')
        interval = data.get('interval')
        if not all([username, keep_last, interval]):
            save_log('Auto-backup start: Missing required fields.', False)
            return jsonify({'error': 'All fields (username, keepLast, interval) are required'}), 400
        try:
            keep_last = int(keep_last)
            interval = float(interval)
            if keep_last <= 0 or interval <= 0:
                save_log(f'Auto-backup start: Invalid keepLast/interval for {username}.', False)
                return jsonify({'error': 'Keep last and interval must be positive numbers'}), 400
        except ValueError:
            save_log(f'Auto-backup start: Invalid number format for {username}.', False)
            return jsonify({'error': 'Invalid number format for keepLast or interval'}), 400
        
        if auto_backup_thread and auto_backup_thread.is_alive():
            save_log("Stopping existing auto-backup thread before starting new one.", True)
            stop_auto_backup.set()
            auto_backup_thread.join(timeout=5)
        
        stop_auto_backup.clear()
        auto_backup_config = {'username': username, 'keepLast': keep_last, 'interval': interval}
        save_config(auto_backup_config)
        
        auto_backup_thread = threading.Thread(target=auto_backup_task, daemon=True)
        auto_backup_thread.start()
        
        save_log(f"Auto backup started for {username}, interval: {interval} hours, keep: {keep_last}", True)
        return jsonify({'status': 'success', 'message': f'Auto backup started for {username}.'})
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
            auto_backup_thread.join(timeout=5)
        auto_backup_config = None
        auto_backup_thread = None
        if os.path.exists(CONFIG_FILE): os.remove(CONFIG_FILE)
        save_log("Auto backup stopped successfully", True)
        return jsonify({'status': 'success'})
    except Exception as e:
        save_log(f"Error stopping auto backup: {str(e)}", False)
        return jsonify({'error': str(e)}), 500

@app.route('/auto-backup-status')
def get_auto_backup_status():
    is_running = bool(auto_backup_thread and auto_backup_thread.is_alive() and not stop_auto_backup.is_set())
    current_config = auto_backup_config if is_running else load_config()
    return jsonify({'running': is_running, 'config': current_config})

@app.route('/backups')
def get_backups_route():
    try:
        all_backups = get_user_backups() 
        return jsonify(all_backups) # Already sorted by get_user_backups
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
                with zipf.open('meta.json') as f:
                    backup_data = json.load(io.TextIOWrapper(f, encoding='utf-8'))
                    return jsonify(backup_data.get('stats', {}))
            return jsonify({'error': 'meta.json not found in backup'}), 404
    except Exception as e:
        save_log(f"Error getting backup stats for {backup_id}: {str(e)}", False)
        return jsonify({'error': str(e)}), 500

@app.route('/backup/<backup_id>/download')
def download_backup(backup_id):
    try:
        backup_path = os.path.join(BACKUP_DIR, f"{backup_id}.zip")
        if not os.path.exists(backup_path):
            return jsonify({'error': 'Backup not found'}), 404
        return send_file(backup_path, mimetype='application/zip', as_attachment=True, download_name=f"{backup_id}.zip")
    except Exception as e:
        save_log(f"Error downloading backup {backup_id}: {str(e)}", False)
        return jsonify({'error': str(e)}), 500

@app.route('/backup/<backup_id>', methods=['DELETE'])
def delete_backup_route(backup_id): # Renamed
    try:
        if delete_backup_file(backup_id):
            latest_stats = load_latest_stats()
            # A bit complex: check if the deleted backup was the one providing latest stats
            # This assumes 'id' was part of latest_stats, which it isn't directly.
            # A simpler approach: just fetch the latest available backup's stats if any.
            # For now, just send an event that it was deleted. The UI can refetch latest if needed.
            sse_queue.put({'type': 'backup_deleted', 'data': {'id': backup_id }})
            sse_queue.put({'type': 'latest_stats_updated', 'data': load_latest_stats()}) # Force update latest_stats on UI
            return jsonify({'status': 'success'})
        return jsonify({'error': 'Backup not found or deletion failed'}), 404
    except Exception as e:
        save_log(f"Error deleting backup {backup_id} via route: {str(e)}", False)
        return jsonify({'error': str(e)}), 500

@app.route('/logs')
def get_logs_route(): # Renamed
    try:
        if os.path.exists(LOGS_FILE):
            with open(LOGS_FILE, 'r') as f:
                logs_data = json.load(f)
                return jsonify(logs_data) # Logs are already sorted by append order
        return jsonify([])
    except Exception as e:
        save_log(f"Error getting logs: {str(e)}", False)
        return jsonify({'error': f"Error reading logs: {str(e)}"}), 500

@app.route('/save-log', methods=['POST']) 
def save_log_client_route(): # Renamed
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'Message is required'}), 400
        save_log(f"[CLIENT] {data['message']}", data.get('isSuccess', False))
        return jsonify({'status': 'success'})
    except Exception as e:
        print(f"Error in /save-log route: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Initial log to confirm application start
    save_log("Application starting up...", True)
    
    saved_config = load_config()
    if saved_config:
        auto_backup_config = saved_config 
        if auto_backup_config.get('username') and auto_backup_config.get('interval') and auto_backup_config.get('keepLast'):
            stop_auto_backup.clear()
            auto_backup_thread = threading.Thread(target=auto_backup_task, daemon=True)
            auto_backup_thread.start()
            save_log(f"Restored and started auto backup for {saved_config['username']} on application start.", True)
        else:
            save_log("Found auto-backup config but critical parameters were missing. Config cleared, not starting auto-backup.", False)
            auto_backup_config = None 
            if os.path.exists(CONFIG_FILE):
                try: os.remove(CONFIG_FILE)
                except OSError as oe: save_log(f"Error removing incomplete config file: {str(oe)}", False)
    
    # Start Flask app
    # Use threaded=True for SSE with the development server. For production, use a proper WSGI server like Gunicorn.
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)
