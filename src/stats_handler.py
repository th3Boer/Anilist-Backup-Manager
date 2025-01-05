class StatsHandler:
   def generate_stats(self, anime_data, manga_data):
       stats = []
       
       # Anime Stats
       stats.append("=== Anime Stats ===")
       anime_lists = anime_data['data']['MediaListCollection']['lists']
       
       total_anime = sum(len(list_group['entries']) for list_group in anime_lists)
       total_episodes = sum(entry['progress'] or 0 for list_group in anime_lists for entry in list_group['entries'])
       total_rewatches = sum(entry['repeat'] or 0 for list_group in anime_lists for entry in list_group['entries'])
       
       # Calculate watch time (assume 24 min per episode)
       minutes = total_episodes * 24
       hours = minutes // 60
       days = hours // 24
       hours_remainder = hours % 24
       
       # Calculate mean score
       scores = [entry['score'] for list_group in anime_lists for entry in list_group['entries'] if entry['score']]
       mean_score = sum(scores) / len(scores) if scores else 0
       
       # Get status distribution
       status_counts = {}
       for list_group in anime_lists:
           status = list_group['name']
           count = len(list_group['entries'])
           if count > 0:
               status_counts[status] = count
       
       stats.extend([
           f"Total Entries: {total_anime}",
           f"Episodes Watched: {total_episodes:,}",
           f"Time Watched: {days}d {hours_remainder}h",
           f"Mean Score: {mean_score:.1f}",
           f"Rewatched: {total_rewatches}",
           "",
           "Status Distribution:"
       ])
       
       for status, count in status_counts.items():
           stats.append(f"- {status}: {count}")
       
       # Manga Stats
       stats.append("\n=== Manga Stats ===")
       manga_lists = manga_data['data']['MediaListCollection']['lists']
       
       total_manga = sum(len(list_group['entries']) for list_group in manga_lists)
       total_chapters = sum(entry['progress'] or 0 for list_group in manga_lists for entry in list_group['entries'])
       total_volumes = sum(entry.get('progressVolumes', 0) or 0 for list_group in manga_lists for entry in list_group['entries'])
       total_rereads = sum(entry['repeat'] or 0 for list_group in manga_lists for entry in list_group['entries'])
       
       # Calculate mean score
       scores = [entry['score'] for list_group in manga_lists for entry in list_group['entries'] if entry['score']]
       mean_score = sum(scores) / len(scores) if scores else 0
       
       # Get status distribution
       status_counts = {}
       for list_group in manga_lists:
           status = list_group['name']
           count = len(list_group['entries'])
           if count > 0:
               status_counts[status] = count
       
       stats.extend([
           f"Total Entries: {total_manga}",
           f"Chapters Read: {total_chapters:,}",
           f"Volumes Read: {total_volumes:,}",
           f"Mean Score: {mean_score:.1f}",
           f"Reread: {total_rereads}",
           "",
           "Status Distribution:"
       ])
       
       for status, count in status_counts.items():
           stats.append(f"- {status}: {count}")
           
       return "\n".join(stats)