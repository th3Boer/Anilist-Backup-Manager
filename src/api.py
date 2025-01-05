# src/api.py
import requests

class AniListAPI:
    def __init__(self):
        self.API_URL = 'https://graphql.anilist.co'

    def get_anime_list(self, username):
        query = """
        query ($username: String) {
          MediaListCollection(userName: $username, type: ANIME) {
            lists {
              name
              entries {
                mediaId
                status
                score
                progress
                repeat
                media {
                  id
                  title {
                    romaji
                    english
                    native
                  }
                  episodes
                  status
                }
              }
            }
          }
        }
        """
        
        variables = {'username': username}
        response = requests.post(self.API_URL, json={'query': query, 'variables': variables})
        
        if response.status_code == 404:
            raise Exception("User not found")
        elif response.status_code != 200:
            raise Exception(f"API error: {response.status_code}")
            
        return response.json()

    def get_manga_list(self, username):
        query = """
        query ($username: String) {
          MediaListCollection(userName: $username, type: MANGA) {
            lists {
              name
              entries {
                mediaId
                status
                score
                progress
                progressVolumes
                repeat
                media {
                  id
                  title {
                    romaji
                    english
                    native
                  }
                  chapters
                  volumes
                  status
                }
              }
            }
          }
        }
        """
        
        variables = {'username': username}
        response = requests.post(self.API_URL, json={'query': query, 'variables': variables})
        
        if response.status_code == 404:
            raise Exception("User not found")
        elif response.status_code != 200:
            raise Exception(f"API error: {response.status_code}")
            
        return response.json()