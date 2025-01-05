import os
import json
import zipfile
import shutil
import xmltodict
from datetime import datetime

class BackupHandler:
    def __init__(self, backup_dir="backups"):
        self.backup_dir = backup_dir
        os.makedirs(backup_dir, exist_ok=True)
        
    def get_backup_stats(self, backup_path):
        """Liest Statistiken aus einem Backup"""
        try:
            with zipfile.ZipFile(backup_path, 'r') as zip_ref:
                # Liste alle Dateien im ZIP
                for filename in zip_ref.namelist():
                    if 'animemanga_stats.txt' in filename:
                        with zip_ref.open(filename) as f:
                            return f.read().decode('utf-8')
            return None
        except Exception as e:
            print(f"Error reading stats: {str(e)}", file=sys.stderr, flush=True)
            return None        
        

    def create_backup(self, username, anime_data, manga_data, stats):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{username}_backup_{timestamp}"
        backup_dir = os.path.join(self.backup_dir, backup_name)
        os.makedirs(backup_dir, exist_ok=True)
        
        try:
            # 1. Raw AniList Backups
            self._save_json(backup_dir, "anime.json", anime_data)
            self._save_json(backup_dir, "manga.json", manga_data)

            # 2. MAL Export
            anime_xml = self._convert_to_mal_xml(anime_data, "anime")
            manga_xml = self._convert_to_mal_xml(manga_data, "manga")
            self._save_file(backup_dir, "anime.xml", anime_xml)
            self._save_file(backup_dir, "manga.xml", manga_xml)

            # 3. Non-MAL entries
            anime_not_in_mal = self._find_non_mal_entries(anime_data)
            manga_not_in_mal = self._find_non_mal_entries(manga_data)
            self._save_json(backup_dir, "anime_NotInMal.json", anime_not_in_mal)
            self._save_json(backup_dir, "manga_NotInMal.json", manga_not_in_mal)

            # 4. Stats
            self._save_file(backup_dir, "animemanga_stats.txt", stats)

            # 5. Tachiyomi files
            manga_not_in_tachi = self._find_non_tachi_entries(manga_data)
            tachi_backup = self._create_tachi_backup(manga_not_in_tachi)
            self._save_json(backup_dir, "manga_NotInTachi.json", manga_not_in_tachi)
            self._save_json(backup_dir, "manga_TachiyomiBackup.json", tachi_backup)

            # Create ZIP
            zip_path = os.path.join(self.backup_dir, f"{backup_name}.zip")
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(backup_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arc_name = os.path.join(os.path.basename(backup_dir), file)
                        zipf.write(file_path, arc_name)

            # Cleanup
            self._cleanup_temp_dir(backup_dir)
            return zip_path

        except Exception as e:
            self._cleanup_temp_dir(backup_dir)
            raise e

    def _save_json(self, dir_path, filename, data):
        path = os.path.join(dir_path, filename)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _save_file(self, dir_path, filename, content):
        path = os.path.join(dir_path, filename)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

    def _convert_to_mal_xml(self, data, media_type):
        mal_data = {
            'myanimelist': {
                f'my{media_type}list': {
                    f'{media_type}': []
                }
            }
        }

        for list_group in data['data']['MediaListCollection']['lists']:
            for entry in list_group['entries']:
                mal_entry = {
                    'series_title': entry['media']['title']['romaji'],
                    'series_animedb_id': str(entry['mediaId']),
                    'my_watched_episodes' if media_type == 'anime' else 'my_read_chapters': str(entry['progress']),
                    'my_score': str(entry['score']),
                    'my_status': self._convert_status_to_mal(entry['status']),
                    'my_times_watched' if media_type == 'anime' else 'my_times_read': str(entry['repeat']),
                    'update_on_import': '1'
                }
                
                if media_type == 'manga':
                    mal_entry['my_read_volumes'] = str(entry.get('progressVolumes', 0))

                mal_data['myanimelist'][f'my{media_type}list'][f'{media_type}'].append(mal_entry)

        return xmltodict.unparse(mal_data, pretty=True)

    def _convert_status_to_mal(self, status):
        status_map = {
            'CURRENT': '1',    # Watching/Reading
            'COMPLETED': '2',  # Completed
            'PAUSED': '3',     # On Hold
            'DROPPED': '4',    # Dropped
            'PLANNING': '6'    # Plan to Watch/Read
        }
        return status_map.get(status, '6')

    def _find_non_mal_entries(self, data):
        non_mal_entries = []
        for list_group in data['data']['MediaListCollection']['lists']:
            for entry in list_group['entries']:
                if entry['mediaId'] > 50000:  # Annahme: IDs > 50000 existieren nicht auf MAL
                    non_mal_entries.append(entry)
        return non_mal_entries

    def _find_non_tachi_entries(self, manga_data):
        return [entry for list_group in manga_data['data']['MediaListCollection']['lists']
                for entry in list_group['entries']]

    def _create_tachi_backup(self, manga_entries):
        return {
            "version": 2,
            "mangas": [{
                "manga": {
                    "title": entry['media']['title']['romaji'],
                    "author": "",
                    "artist": "",
                    "description": "",
                    "genre": [],
                    "status": entry['media']['status'],
                    "thumbnail_url": ""
                },
                "chapters": [],
                "track": {
                    "status": entry['status'],
                    "score": entry['score'],
                    "last_chapter_read": entry['progress']
                },
                "categories": ["Anilist"]
            } for entry in manga_entries],
            "categories": [{"name": "Anilist", "order": 0}]
        }

    def _cleanup_temp_dir(self, dir_path):
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)

    def cleanup_old_backups(self, max_backups):
        if not os.path.exists(self.backup_dir):
            return

        backups = []
        for file in os.listdir(self.backup_dir):
            if file.endswith('.zip'):
                path = os.path.join(self.backup_dir, file)
                backups.append((os.path.getctime(path), path))

        backups.sort(reverse=True)
        for _, path in backups[max_backups:]:
            try:
                os.remove(path)
            except Exception:
                pass

def get_backup_stats(self, backup_path):
    """Liest Statistiken aus einem Backup"""
    try:
        with zipfile.ZipFile(backup_path, 'r') as zip_ref:
            # Liste alle Dateien im ZIP
            for filename in zip_ref.namelist():
                if 'animemanga_stats.txt' in filename:
                    with zip_ref.open(filename) as f:
                        return f.read().decode('utf-8')
        return None
    except Exception as e:
        print(f"Error reading stats: {str(e)}")
        return None