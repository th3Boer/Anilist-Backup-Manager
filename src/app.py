from flask import Flask, render_template, request, jsonify, send_file
import os
import json
from datetime import datetime
import threading
import time
import requests
import zipfile
import io

app = Flask(__name__)

# Globale Variablen
BACKUP_DIR = "backups"
LOGS_FILE = "logs.json"
CONFIG_FILE = "config.json"  # Neue Konfigurationsdatei
MAX_LOGS = 100

# Auto-Backup Konfiguration
auto_backup_thread = None
stop_auto_backup = threading.Event()
auto_backup_config = None
backup_lock = threading.Lock()

# Verzeichnisse erstellen
if not os.path.exists(BACKUP_DIR):
    os.makedirs(BACKUP_DIR)

# GraphQL Query
ANILIST_QUERY = """
query ($username: String) {
    MediaListCollection(userName: $username, type: ANIME) {
        lists {
            entries {
                media {
                    title {
                        romaji
                    }
                }
                score
                progress
                status
            }
        }
    }
    MediaListCollection2: MediaListCollection(userName: $username, type: MANGA) {
        lists {
            entries {
                media {
                    title {
                        romaji
                    }
                }
                score
                progress
                status
            }
        }
    }
}
"""

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
        
        # Keep only last 100 logs
        logs = logs[-MAX_LOGS:]
        
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
    
    if response.status_code != 200:
        raise Exception('Failed to fetch data from Anilist')
    
    return response.json()

def calculate_stats(data):
    anime_entries = []
    manga_entries = []
    
    # Status counters for anime
    anime_status = {
        'watching': 0,
        'completed': 0,
        'planning': 0,
        'dropped': 0,
        'on_hold': 0
    }
    
    # Status counters for manga
    manga_status = {
        'reading': 0,
        'completed': 0,
        'planning': 0,
        'dropped': 0,
        'on_hold': 0
    }
    
    # Anime Stats
    if 'MediaListCollection' in data['data']:
        for list_group in data['data']['MediaListCollection']['lists']:
            for entry in list_group['entries']:
                anime_entries.append(entry)
                status = entry['status'].lower()
                if status in anime_status:
                    anime_status[status] += 1
    
    # Manga Stats
    if 'MediaListCollection2' in data['data']:
        for list_group in data['data']['MediaListCollection2']['lists']:
            for entry in list_group['entries']:
                manga_entries.append(entry)
                status = entry['status'].lower()
                if status in manga_status:
                    manga_status[status] += 1
    
    anime_stats = {
        'totalEntries': len(anime_entries),
        'timeWatched': sum(entry['progress'] for entry in anime_entries),
        'meanScore': round(sum(entry['score'] for entry in anime_entries if entry['score']) / len([e for e in anime_entries if e['score']]), 1) if anime_entries else 0,
        'status': anime_status
    }
    
    manga_stats = {
        'totalEntries': len(manga_entries),
        'chaptersRead': sum(entry['progress'] for entry in manga_entries),
        'meanScore': round(sum(entry['score'] for entry in manga_entries if entry['score']) / len([e for e in manga_entries if e['score']]), 1) if manga_entries else 0,
        'status': manga_status
    }
    
    return anime_stats, manga_stats

def generate_mal_xml(entries, type='anime'):
    """Generate MyAnimeList XML export format"""
    template = """<?xml version="1.0" encoding="UTF-8" ?>
<myanimelist>
    {entries}
</myanimelist>
"""
    
    entry_template = """    <{type}>
        <title><![CDATA[{title}]]></title>
        <score>{score}</score>
        {extra_fields}
        <status>{status}</status>
        <tags><![CDATA[]]></tags>
    </{type}>
"""
    
    status_map = {
        'CURRENT': 'Watching' if type == 'anime' else 'Reading',
        'COMPLETED': 'Completed',
        'PLANNING': 'Plan to Watch' if type == 'anime' else 'Plan to Read',
        'DROPPED': 'Dropped',
        'PAUSED': 'On-Hold'
    }
    
    formatted_entries = []
    for entry in entries:
        extra_fields = f"        <{'episodes' if type == 'anime' else 'chapters'}>{entry['progress']}</{'episodes' if type == 'anime' else 'chapters'}>\n"
        
        formatted_entries.append(entry_template.format(
            type=type,
            title=entry['media']['title']['romaji'],
            score=int(entry['score']) if entry['score'] else 0,
            status=status_map.get(entry['status'], 'Plan to Watch' if type == 'anime' else 'Plan to Read'),
            extra_fields=extra_fields
        ))
    
    return template.format(entries='\n'.join(formatted_entries))

def create_backup(username):
    try:
        # Fetch data outside the lock
        data = fetch_anilist_data(username)
        anime_stats, manga_stats = calculate_stats(data)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_id = f"{username}_{timestamp}"
        
        # Only use lock for file operations
        with backup_lock:
            backup_dir = os.path.join(BACKUP_DIR, backup_id)
            os.makedirs(backup_dir, exist_ok=True)

            # Create anime.json and manga.json
            anime_data = []
            manga_data = []
            
            if 'MediaListCollection' in data['data']:
                for list_group in data['data']['MediaListCollection']['lists']:
                    anime_data.extend(list_group['entries'])
                    
            if 'MediaListCollection2' in data['data']:
                for list_group in data['data']['MediaListCollection2']['lists']:
                    manga_data.extend(list_group['entries'])

            with open(os.path.join(backup_dir, 'anime.json'), 'w', encoding='utf-8') as f:
                json.dump(anime_data, f, ensure_ascii=False, indent=2)
                
            with open(os.path.join(backup_dir, 'manga.json'), 'w', encoding='utf-8') as f:
                json.dump(manga_data, f, ensure_ascii=False, indent=2)

            # Create stats text file
            stats_text = f"""Anime & Manga Statistics for {username}
Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Anime Statistics:
---------------
Total Entries: {anime_stats['totalEntries']}
Time Watched: {anime_stats['timeWatched']} hours
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

            # Create MAL XML exports
            anime_xml = generate_mal_xml(anime_data, 'anime')
            manga_xml = generate_mal_xml(manga_data, 'manga')

            with open(os.path.join(backup_dir, 'anime.xml'), 'w', encoding='utf-8') as f:
                f.write(anime_xml)
                
            with open(os.path.join(backup_dir, 'manga.xml'), 'w', encoding='utf-8') as f:
                f.write(manga_xml)
                
            # Create meta.json for our system
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
                
            # Create ZIP file
            zip_path = os.path.join(BACKUP_DIR, f"{backup_id}.zip")
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for filename in ['anime.json', 'manga.json', 'animemanga_stats.txt', 
                               'anime.xml', 'manga.xml', 'meta.json']:
                    file_path = os.path.join(backup_dir, filename)
                    zipf.write(file_path, filename)
                    
            # Cleanup directory
            for filename in os.listdir(backup_dir):
                os.remove(os.path.join(backup_dir, filename))
            os.rmdir(backup_dir)
            
        save_log(f"Created backup for {username}", True)
        return meta_data
            
    except Exception as e:
        save_log(f"Backup failed: {str(e)}")
        raise Exception(f"Backup failed: {str(e)}")

def auto_backup_task():
    global auto_backup_config
    
    while not stop_auto_backup.is_set():
        try:
            if auto_backup_config:
                username = auto_backup_config.get('username')
                keep_last = int(auto_backup_config.get('keepLast', 1))
                interval = float(auto_backup_config.get('interval', 1))
                
                if username and keep_last > 0:
                    try:
                        create_backup(username)
                        
                        # Cleanup old backups
                        backups = get_user_backups(username)
                        if len(backups) > keep_last:
                            backups_to_delete = sorted(backups, key=lambda x: x['date'])[:-keep_last]
                            for backup in backups_to_delete:
                                delete_backup_file(backup['id'])
                    except Exception as backup_error:
                        save_log(f"Auto backup task error: {str(backup_error)}")
                        # Continue running even if one backup fails
                
                # Sleep in smaller intervals for better responsiveness
                sleep_interval = min(interval * 3600, 60)  # Max 60 seconds per interval
                iterations = int((interval * 3600) / sleep_interval)
                
                for _ in range(iterations):
                    if stop_auto_backup.is_set():
                        break
                    time.sleep(sleep_interval)
            else:
                if stop_auto_backup.is_set():
                    break
                time.sleep(1)
                
        except Exception as e:
            save_log(f"Auto backup error: {str(e)}")
            time.sleep(60)  # Wait a minute on error

def get_user_backups(username):
    backups = []
    try:
        for filename in os.listdir(BACKUP_DIR):
            if filename.endswith('.zip') and filename.startswith(f"{username}_"):
                backup_id = filename[:-4]  # Remove .zip
                with zipfile.ZipFile(os.path.join(BACKUP_DIR, filename), 'r') as zipf:
                    with zipf.open('meta.json') as f:
                        backup_data = json.load(io.TextIOWrapper(f))
                        backups.append({
                            'id': backup_data['id'],
                            'date': backup_data['date'],
                            'username': backup_data['username'],
                            'content': f"{backup_data['stats']['anime']['totalEntries']} Anime, {backup_data['stats']['manga']['totalEntries']} Manga"
                        })
    except Exception as e:
        save_log(f"Error getting user backups: {str(e)}")
        return []
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
        save_log(f"Error deleting backup file: {str(e)}")
        return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/backup', methods=['POST'])
def manual_backup():
    try:
        data = request.get_json()
        username = data.get('username')
        if not username:
            return jsonify({'error': 'Username is required'}), 400
        
        backup_data = create_backup(username)
        return jsonify({'status': 'success', 'data': backup_data})
        
    except Exception as e:
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
            return jsonify({'error': 'All fields are required'}), 400
            
        try:
            keep_last = int(keep_last)
            interval = float(interval)
            if keep_last <= 0 or interval <= 0:
                return jsonify({'error': 'Keep last and interval must be positive numbers'}), 400
        except ValueError:
            return jsonify({'error': 'Invalid number format'}), 400
        
        # Stop existing auto backup if running
        if auto_backup_thread and auto_backup_thread.is_alive():
            stop_auto_backup.set()
            auto_backup_thread.join(timeout=2)
            time.sleep(0.5)  # Kurze Wartezeit für Cleanup
        
        # Reset stop event and config
        stop_auto_backup.clear()
        auto_backup_config = {
            'username': username,
            'keepLast': keep_last,
            'interval': interval
        }
        
        # Speichere Konfiguration
        save_config(auto_backup_config)
        
        # Start new thread
        auto_backup_thread = threading.Thread(target=auto_backup_task)
        auto_backup_thread.daemon = True
        auto_backup_thread.start()
        
        save_log(f"Started auto backup for {username}", True)
        return jsonify({'status': 'success'})
        
    except Exception as e:
        auto_backup_config = None
        stop_auto_backup.set()
        # Lösche Konfiguration bei Fehler
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
        save_log(f"Failed to start auto backup: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/stop-auto-backup', methods=['POST'])
def stop_auto_backup_route():
    global auto_backup_config, auto_backup_thread
    
    try:
        save_log("Stopping auto backup...", True)
        
        # Setze zuerst das Stop-Event
        stop_auto_backup.set()
        
        # Warte maximal 2 Sekunden auf Thread-Beendigung
        if auto_backup_thread and auto_backup_thread.is_alive():
            auto_backup_thread.join(timeout=2)
            
        # Cleanup
        auto_backup_config = None
        auto_backup_thread = None
        
        # Lösche Konfigurationsdatei
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
            
        save_log("Auto backup stopped successfully", True)
        return jsonify({'status': 'success'})
    except Exception as e:
        save_log(f"Error stopping auto backup: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/auto-backup-status')
def get_auto_backup_status():
    return jsonify({
        'running': bool(auto_backup_thread and auto_backup_thread.is_alive() and not stop_auto_backup.is_set()),
        'config': auto_backup_config
    })

@app.route('/backups')
def get_backups():
    try:
        all_backups = []
        for filename in os.listdir(BACKUP_DIR):
            if filename.endswith('.zip'):
                with zipfile.ZipFile(os.path.join(BACKUP_DIR, filename), 'r') as zipf:
                    with zipf.open('meta.json') as f:
                        backup_data = json.load(io.TextIOWrapper(f))
                        all_backups.append({
                            'id': backup_data['id'],
                            'date': backup_data['date'],
                            'username': backup_data['username'],
                            'content': f"{backup_data['stats']['anime']['totalEntries']} Anime, {backup_data['stats']['manga']['totalEntries']} Manga"
                        })
        return jsonify(sorted(all_backups, key=lambda x: x['date'], reverse=True))
        
    except Exception as e:
        save_log(f"Error getting backups: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/backup/<backup_id>/stats')
def get_backup_stats(backup_id):
    try:
        zip_path = os.path.join(BACKUP_DIR, f"{backup_id}.zip")
        if not os.path.exists(zip_path):
            return jsonify({'error': 'Backup not found'}), 404
        
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            with zipf.open('meta.json') as f:
                backup_data = json.load(io.TextIOWrapper(f))
                return jsonify(backup_data['stats'])
            
    except Exception as e:
        save_log(f"Error getting backup stats: {str(e)}")
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
        save_log(f"Error downloading backup: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/backup/<backup_id>', methods=['DELETE'])
def delete_backup(backup_id):
    try:
        backup_path = os.path.join(BACKUP_DIR, f"{backup_id}.zip")
        if not os.path.exists(backup_path):
            return jsonify({'error': 'Backup not found'}), 404
        
        os.remove(backup_path)
        save_log(f"Deleted backup {backup_id}", True)
        return jsonify({'status': 'success'})
        
    except Exception as e:
        save_log(f"Error deleting backup: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/logs')
def get_logs():
    try:
        if os.path.exists(LOGS_FILE):
            with open(LOGS_FILE, 'r') as f:
                return jsonify(json.load(f))
        return jsonify([])
    except Exception as e:
        save_log(f"Error getting logs: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/save-log', methods=['POST'])
def save_log_route():
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'Message is required'}), 400
        
        save_log(data['message'], data.get('isSuccess', False))
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Lade gespeicherte Konfiguration und starte Auto-Backup wenn vorhanden
    saved_config = load_config()
    if saved_config:
        auto_backup_config = saved_config
        auto_backup_thread = threading.Thread(target=auto_backup_task)
        auto_backup_thread.daemon = True
        auto_backup_thread.start()
        save_log(f"Restored auto backup for {saved_config['username']}", True)
    
    app.run(debug=True, host='0.0.0.0', port=5000)