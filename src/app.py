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
        save_log(f"Error loading config: {str(e)}")
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
    try:
        logs = []
        if os.path.exists(LOGS_FILE):
            with open(LOGS_FILE, 'r') as f:
                logs = json.load(f)
        
        logs.append({
            'timestamp': datetime.now().isoformat(),
            'message': message,
            'is_success': is_success
        })
        
        logs = logs[-MAX_LOGS:]  # Keep only last MAX_LOGS logs
        
        with open(LOGS_FILE, 'w') as f:
            json.dump(logs, f)
            
    except Exception as e:
        print(f"Error saving log: {e}")

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
    
    if data['data'].get('MediaListCollection') and data['data']['MediaListCollection'].get('lists'):
        for list_group in data['data']['MediaListCollection']['lists']:
            for entry in list_group['entries']:
                anime_entries.append(entry)
                status_key = entry['status'].lower()
                if status_key == "current": status_key = "watching"
                if status_key == "paused": status_key = "on_hold"
                if status_key in anime_status:
                    anime_status[status_key] += 1
    
    if data['data'].get('MediaListCollection2') and data['data']['MediaListCollection2'].get('lists'):
        for list_group in data['data']['MediaListCollection2']['lists']:
            for entry in list_group['entries']:
                manga_entries.append(entry)
                status_key = entry['status'].lower()
                if status_key == "current": status_key = "reading"
                if status_key == "paused": status_key = "on_hold"
                if status_key in manga_status:
                    manga_status[status_key] += 1
    
    anime_scores = [e['score'] for e in anime_entries if e['score'] and e['score'] > 0]
    manga_scores = [e['score'] for e in manga_entries if e['score'] and e['score'] > 0]

    anime_stats = {
        'totalEntries': len(anime_entries),
        'episodesWatched': sum(entry.get('progress', 0) or 0 for entry in anime_entries),
        'meanScore': round(sum(anime_scores) / len(anime_scores), 1) if anime_scores else 0,
        'status': anime_status,
        'username': data.get('username', '') # Store username for display
    }
    
    manga_stats = {
        'totalEntries': len(manga_entries),
        'chaptersRead': sum(entry.get('progress', 0) or 0 for entry in manga_entries),
        'volumesRead': sum(entry.get('progressVolumes', 0) or 0 for entry in manga_entries),
        'meanScore': round(sum(manga_scores) / len(manga_scores), 1) if manga_scores else 0,
        'status': manga_status,
        'username': data.get('username', '') # Store username for display
    }
    
    return anime_stats, manga_stats

def generate_mal_xml(entries, type='anime'):
    """Generate MyAnimeList XML export format"""
    xml_header = """<?xml version="1.0" encoding="UTF-8" ?>
<myanimelist>
"""
    # myinfo can be added here if needed, but it's not strictly necessary for list import
    # <myinfo>
    #   <user_export_type>1</user_export_type> <!-- 1 for anime, 2 for manga -->
    # </myinfo>

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
    
    status_map_anime = {
        'CURRENT': 'Watching',
        'COMPLETED': 'Completed',
        'PLANNING': 'Plan to Watch',
        'DROPPED': 'Dropped',
        'PAUSED': 'On-Hold' # Equivalent to On-Hold in MAL
    }
    status_map_manga = {
        'CURRENT': 'Reading',
        'COMPLETED': 'Completed',
        'PLANNING': 'Plan to Read',
        'DROPPED': 'Dropped',
        'PAUSED': 'On-Hold' # Equivalent to On-Hold in MAL
    }
    
    formatted_entries = []
    for entry in entries:
        title = entry['media']['title']['romaji']
        media_id = entry['media']['id']
        score = int(entry['score']) if entry['score'] else 0
        progress = entry['progress'] if entry['progress'] else 0
        rewatched = entry.get('repeat', 0)

        if type == 'anime':
            status = status_map_anime.get(entry['status'], 'Plan to Watch')
            formatted_entries.append(entry_template_anime.format(
                media_id=media_id,
                title=title,
                score=score,
                status=status,
                progress=progress,
                rewatched=rewatched
            ))
        else: # manga
            status = status_map_manga.get(entry['status'], 'Plan to Read')
            progress_volumes = entry.get('progressVolumes', 0)
            formatted_entries.append(entry_template_manga.format(
                media_id=media_id,
                title=title,
                score=score,
                status=status,
                progress=progress,
                progress_volumes=progress_volumes,
                rewatched=rewatched
            ))
            
    xml_footer = "</myanimelist>"
    return xml_header + '\n'.join(formatted_entries) + '\n' + xml_footer

def create_backup(username):
    try:
        # Fetch data outside the lock
        raw_data = fetch_anilist_data(username)
        # Add username to raw_data for calculate_stats to use if needed
        raw_data['username'] = username 
        anime_stats, manga_stats = calculate_stats(raw_data)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_id = f"{username}_{timestamp}"
        meta_data = None 
        
        with backup_lock:
            backup_dir = os.path.join(BACKUP_DIR, backup_id)
            os.makedirs(backup_dir, exist_ok=True)
            zip_path = None # Define zip_path to be accessible in except block

            try:
                anime_data_list = []
                manga_data_list = []
                
                if raw_data['data'].get('MediaListCollection') and raw_data['data']['MediaListCollection'].get('lists'):
                    for list_group in raw_data['data']['MediaListCollection']['lists']:
                        anime_data_list.extend(list_group['entries'])
                        
                if raw_data['data'].get('MediaListCollection2') and raw_data['data']['MediaListCollection2'].get('lists'):
                    for list_group in raw_data['data']['MediaListCollection2']['lists']:
                        manga_data_list.extend(list_group['entries'])

                with open(os.path.join(backup_dir, 'anime.json'), 'w', encoding='utf-8') as f:
                    json.dump(anime_data_list, f, ensure_ascii=False, indent=2)
                    
                with open(os.path.join(backup_dir, 'manga.json'), 'w', encoding='utf-8') as f:
                    json.dump(manga_data_list, f, ensure_ascii=False, indent=2)

                stats_text = f"""Anime & Manga Statistics for {username}
Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Anime Statistics:
---------------
Total Entries: {anime_stats['totalEntries']}
Episodes Watched: {anime_stats['episodesWatched']}
Mean Score: {anime_stats['meanScore']:.1f}

Status Distribution:
- Watching: {anime_stats['status']['watching']}
- Completed: {anime_stats['status']['completed']}
- On Hold: {anime_stats['status']['on_hold']}
- Dropped: {anime_stats['status']['dropped']}
- Plan to Watch: {anime_stats['status']['planning']}

Manga Statistics:
---------------
Total Entries: {manga_stats['totalEntries']}
Chapters Read: {manga_stats['chaptersRead']}
Volumes Read: {manga_stats['volumesRead']}
Mean Score: {manga_stats['meanScore']:.1f}

Status Distribution:
- Reading: {manga_stats['status']['reading']}
- Completed: {manga_stats['status']['completed']}
- On Hold: {manga_stats['status']['on_hold']}
- Dropped: {manga_stats['status']['dropped']}
- Plan to Read: {manga_stats['status']['planning']}
"""
                with open(os.path.join(backup_dir, 'animemanga_stats.txt'), 'w', encoding='utf-8') as f:
                    f.write(stats_text)

                anime_xml = generate_mal_xml(anime_data_list, 'anime')
                manga_xml = generate_mal_xml(manga_data_list, 'manga')

                with open(os.path.join(backup_dir, 'anime.xml'), 'w', encoding='utf-8') as f:
                    f.write(anime_xml)
                    
                with open(os.path.join(backup_dir, 'manga.xml'), 'w', encoding='utf-8') as f:
                    f.write(manga_xml)
                
                meta_data = {
                    'id': backup_id,
                    'date': datetime.now().isoformat(),
                    'username': username,
                    'stats': {
                        'anime': anime_stats,
                        'manga': manga_stats
                    }
                }
                
                with open(os.path.join(backup_dir, 'meta.json'), 'w', encoding='utf-8') as f:
                    json.dump(meta_data, f, ensure_ascii=False, indent=2)
                    
                zip_path = os.path.join(BACKUP_DIR, f"{backup_id}.zip")
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for filename in ['anime.json', 'manga.json', 'animemanga_stats.txt', 
                                   'anime.xml', 'manga.xml', 'meta.json']:
                        file_path = os.path.join(backup_dir, filename)
                        zipf.write(file_path, filename)
                
                shutil.rmtree(backup_dir) # Remove temporary directory after zipping
                                
                # Save these stats as the latest
                save_latest_stats({'anime': anime_stats, 'manga': manga_stats, 'username': username, 'last_updated': meta_data['date']})

                sse_queue.put({
                    'type': 'backup_created',
                    'data': {
                        'username': username,
                        'timestamp': meta_data['date'],
                        'stats': {'anime': anime_stats, 'manga': manga_stats} # Send new stats for SSE update
                    }
                })
                
                save_log(f"Created backup for {username}", True)
                return meta_data

            except Exception as e:
                if os.path.exists(backup_dir):
                    shutil.rmtree(backup_dir)
                if zip_path and os.path.exists(zip_path):
                    os.remove(zip_path)
                raise e # Re-raise the exception to be caught by the outer try-except
            
    except Exception as e:
        save_log(f"Backup failed for {username}: {str(e)}")
        # Do not raise Exception here, as it will be caught by the route and returned as JSON
        # The calling function should handle the None return or check for error in response
        raise # Re-raise to be caught by the route handler

def auto_backup_task():
    global auto_backup_config
    
    while not stop_auto_backup.is_set():
        try:
            if auto_backup_config:
                username = auto_backup_config.get('username')
                keep_last = int(auto_backup_config.get('keepLast', 1))
                interval_hours = float(auto_backup_config.get('interval', 1)) # Ensure this is hours
                
                if username and keep_last > 0:
                    try:
                        create_backup(username) # This will now also save_latest_stats
                        
                        with backup_lock:
                            backups = get_user_backups(username)
                            if len(backups) > keep_last:
                                backups_to_delete = sorted(backups, key=lambda x: x['date'])[:-keep_last]
                                for backup_meta in backups_to_delete:
                                    delete_backup_file(backup_meta['id'])
                    except Exception as backup_error:
                        save_log(f"Auto backup task error for {username}: {str(backup_error)}")
                
                # Sleep logic for interval
                sleep_duration_seconds = interval_hours * 3600
                sleep_interval_check = 60  # Check for stop event every 60 seconds
                
                elapsed_sleep = 0
                while elapsed_sleep < sleep_duration_seconds and not stop_auto_backup.is_set():
                    time.sleep(min(sleep_interval_check, sleep_duration_seconds - elapsed_sleep))
                    elapsed_sleep += sleep_interval_check
            else:
                if stop_auto_backup.is_set():
                    break
                time.sleep(5) # Wait if no config
                
        except Exception as e:
            save_log(f"Critical error in auto backup loop: {str(e)}")
            time.sleep(60)

def get_user_backups(username_filter=None): # Allow filtering by username
    backups = []
    try:
        for filename in os.listdir(BACKUP_DIR):
            if filename.endswith('.zip'):
                if username_filter and not filename.startswith(f"{username_filter}_"):
                    continue
                backup_id = filename[:-4]
                try:
                    with zipfile.ZipFile(os.path.join(BACKUP_DIR, filename), 'r') as zipf:
                        if 'meta.json' in zipf.namelist():
                            with zipf.open('meta.json') as f:
                                backup_data = json.load(io.TextIOWrapper(f, encoding='utf-8'))
                                backups.append({
                                    'id': backup_data['id'],
                                    'date': backup_data['date'],
                                    'username': backup_data['username'],
                                    'content': f"{backup_data['stats']['anime']['totalEntries']} Anime, {backup_data['stats']['manga']['totalEntries']} Manga"
                                })
                        else:
                            save_log(f"meta.json not found in backup {filename}")
                except Exception as e_inner:
                     save_log(f"Error processing backup file {filename}: {str(e_inner)}")
    except Exception as e:
        save_log(f"Error getting user backups: {str(e)}")
    return sorted(backups, key=lambda x: x['date'], reverse=True)


def delete_backup_file(backup_id):
    try:
        backup_path = os.path.join(BACKUP_DIR, f"{backup_id}.zip")
        if os.path.exists(backup_path):
            os.remove(backup_path)
            save_log(f"Deleted backup {backup_id}", True)
            return True
        return False
    except Exception as e:
        save_log(f"Error deleting backup file {backup_id}: {str(e)}")
        return False

@app.route('/')
def index():
    latest_stats_data = load_latest_stats()
    return render_template('index.html', latest_stats=latest_stats_data)

@app.route('/latest-stats')
def get_latest_stats_route():
    stats = load_latest_stats()
    if stats:
        return jsonify(stats)
    return jsonify(None)


@app.route('/events')
def events():
    def event_stream():
        while True:
            try:
                message = sse_queue.get(timeout=30) # Timeout to allow sending keep-alive
                yield f"data: {json.dumps(message)}\n\n"
            except queue.Empty:
                yield "data: {}\n\n" # Keep-alive to prevent connection closure
            except GeneratorExit: # Client disconnected
                break
            
    return Response(stream_with_context(event_stream()),
                   mimetype='text/event-stream',
                   headers={'Cache-Control': 'no-cache',
                           'X-Accel-Buffering': 'no', # For Nginx
                           'Connection': 'keep-alive'})


@app.route('/backup', methods=['POST'])
def manual_backup():
    try:
        data = request.get_json()
        username = data.get('username')
        if not username:
            return jsonify({'error': 'Username is required'}), 400
        
        backup_meta = create_backup(username) # This can raise an exception
        return jsonify({'status': 'success', 'data': backup_meta})
        
    except Exception as e:
        save_log(f"Manual backup endpoint error for {data.get('username', 'N/A')}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/auto-backup', methods=['POST'])
def start_auto_backup():
    global auto_backup_thread, auto_backup_config
    
    try:
        data = request.get_json()
        username = data.get('username')
        keep_last = data.get('keepLast')
        interval = data.get('interval') # This is in hours from frontend
        
        if not all([username, keep_last, interval]):
            return jsonify({'error': 'All fields (username, keepLast, interval) are required'}), 400
            
        try:
            keep_last = int(keep_last)
            interval = float(interval) # Interval in hours
            if keep_last <= 0 or interval <= 0:
                return jsonify({'error': 'Keep last and interval must be positive numbers'}), 400
        except ValueError:
            return jsonify({'error': 'Invalid number format for keepLast or interval'}), 400
        
        if auto_backup_thread and auto_backup_thread.is_alive():
            stop_auto_backup.set()
            auto_backup_thread.join(timeout=5) # Increased timeout
        
        stop_auto_backup.clear()
        auto_backup_config = {
            'username': username,
            'keepLast': keep_last,
            'interval': interval # Store interval in hours
        }
        
        save_config(auto_backup_config)
        
        auto_backup_thread = threading.Thread(target=auto_backup_task, daemon=True)
        auto_backup_thread.start()
        
        save_log(f"Started auto backup for {username}, interval: {interval} hours, keep: {keep_last}", True)
        return jsonify({'status': 'success', 'message': f'Auto backup started for {username}.'})
        
    except Exception as e:
        auto_backup_config = None # Reset on failure
        stop_auto_backup.set() # Ensure it's stopped
        if os.path.exists(CONFIG_FILE):
            try:
                os.remove(CONFIG_FILE)
            except OSError as oe:
                save_log(f"Error removing config file during auto-backup start failure: {str(oe)}")

        save_log(f"Failed to start auto backup: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/stop-auto-backup', methods=['POST'])
def stop_auto_backup_route():
    global auto_backup_config, auto_backup_thread
    
    try:
        save_log("Attempting to stop auto backup...", True)
        stop_auto_backup.set()
        
        if auto_backup_thread and auto_backup_thread.is_alive():
            auto_backup_thread.join(timeout=5) # Wait for thread to finish
            
        auto_backup_config = None
        auto_backup_thread = None # Clear the thread object
        
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
            
        save_log("Auto backup stopped successfully", True)
        return jsonify({'status': 'success'})
    except Exception as e:
        save_log(f"Error stopping auto backup: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/auto-backup-status')
def get_auto_backup_status():
    is_running = bool(auto_backup_thread and auto_backup_thread.is_alive() and not stop_auto_backup.is_set())
    return jsonify({
        'running': is_running,
        'config': auto_backup_config if is_running else load_config() # Show saved config if not running but configured
    })

@app.route('/backups')
def get_backups_route(): # Renamed to avoid conflict
    try:
        # Optionally, could take a username query param: request.args.get('username')
        all_backups = get_user_backups() 
        return jsonify(sorted(all_backups, key=lambda x: x['date'], reverse=True))
    except Exception as e:
        save_log(f"Error in /backups route: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/backup/<backup_id>/stats')
def get_backup_stats_route(backup_id): # Renamed
    try:
        zip_path = os.path.join(BACKUP_DIR, f"{backup_id}.zip")
        if not os.path.exists(zip_path):
            return jsonify({'error': 'Backup not found'}), 404
        
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            if 'meta.json' in zipf.namelist():
                with zipf.open('meta.json') as f:
                    backup_data = json.load(io.TextIOWrapper(f, encoding='utf-8'))
                    return jsonify(backup_data['stats'])
            else:
                return jsonify({'error': 'meta.json not found in backup'}), 404
            
    except Exception as e:
        save_log(f"Error getting backup stats for {backup_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/backup/<backup_id>/download')
def download_backup(backup_id):
    try:
        backup_path = os.path.join(BACKUP_DIR, f"{backup_id}.zip")
        if not os.path.exists(backup_path):
            return jsonify({'error': 'Backup not found'}), 404
        
        return send_file(
            backup_path,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f"{backup_id}.zip"
        )
        
    except Exception as e:
        save_log(f"Error downloading backup {backup_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/backup/<backup_id>', methods=['DELETE'])
def delete_backup(backup_id):
    try:
        if delete_backup_file(backup_id):
            # If the deleted backup was the one whose stats are shown, clear latest_stats
            latest_stats = load_latest_stats()
            if latest_stats and latest_stats.get('id') == backup_id: # Assuming meta.json id was part of latest_stats
                 if os.path.exists(LATEST_STATS_FILE):
                    os.remove(LATEST_STATS_FILE)
                 sse_queue.put({'type': 'latest_stats_updated', 'data': None})


            sse_queue.put({'type': 'backup_deleted', 'data': {'id': backup_id }})
            return jsonify({'status': 'success'})
        else:
            return jsonify({'error': 'Backup not found or deletion failed'}), 404
        
    except Exception as e:
        save_log(f"Error deleting backup {backup_id} via route: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/logs')
def get_logs():
    try:
        if os.path.exists(LOGS_FILE):
            with open(LOGS_FILE, 'r') as f:
                return jsonify(json.load(f))
        return jsonify([])
    except Exception as e:
        save_log(f"Error getting logs: {str(e)}") # Should ideally not happen
        return jsonify({'error': f"Error reading logs: {str(e)}"}), 500

@app.route('/save-log', methods=['POST']) # Primarily for client-side logging if needed
def save_log_route():
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'Message is required'}), 400
        
        save_log(f"[CLIENT] {data['message']}", data.get('isSuccess', False))
        return jsonify({'status': 'success'})
    except Exception as e:
        # Avoid calling save_log here to prevent potential recursion if logging itself fails
        print(f"Error in /save-log route: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    saved_config = load_config()
    if saved_config:
        auto_backup_config = saved_config # Restore config
        # Re-initialize auto-backup thread if config exists
        if auto_backup_config.get('username') and auto_backup_config.get('interval') and auto_backup_config.get('keepLast'):
            stop_auto_backup.clear()
            auto_backup_thread = threading.Thread(target=auto_backup_task, daemon=True)
            auto_backup_thread.start()
            save_log(f"Restored auto backup for {saved_config['username']} on application start.", True)
        else:
            save_log("Found auto-backup config but some parameters were missing, not starting.", False)
            auto_backup_config = None # Invalidate corrupt/incomplete config
            if os.path.exists(CONFIG_FILE):
                os.remove(CONFIG_FILE)


    # Ensure Flask runs in a way that's compatible with threading for SSE
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)
