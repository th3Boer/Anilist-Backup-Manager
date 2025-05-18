# Anilist Backup Manager (AniList Vault) 🛡️💾

Easily create and manage backups of your AniList.co anime and manga lists with AniList Vault! This web-based tool allows you to perform manual or automatic backups, storing detailed statistics like total entries, time watched, mean scores, and more.

# IMPROTANT: Your AniList Profile needs to be public.

AniList Vault runs Docker container for simple setup and portability.

![Screenshot 2025-05-18 020208](https://github.com/user-attachments/assets/03b30da7-b140-4d8b-9e92-3ef8685ba4db)

## ✨ Key Features

*   **Effortless Backups:**
    *   **Manual:** Create a full backup of your lists with a single click.
    *   **Automatic:** Schedule recurring backups at your preferred interval (e.g., daily). Keep a configurable number of recent backups, with older ones being automatically removed.
*   **Insightful Statistics:**
    *   View comprehensive statistics for your anime and manga activity directly within the application.
    *   Track total entries, episodes watched, chapters/volumes read, average scores, and how your lists are distributed across statuses (Watching, Completed, On-Hold, Dropped, Planning).
    *   The latest backup's statistics are always visible on the main page for a quick overview.
*   **Simple Backup Management:**
    *   Download your backup archives (as ZIP files) anytime.
    *   Review the detailed statistics for any specific backup.
    *   Easily delete older or unneeded backups from the interface.
*   **Versatile Export Formats:**
    *   Backups include your raw list data in JSON format.
    *   MyAnimeList (MAL) compatible XML files (`anime.xml`, `manga.xml`) are also generated, allowing for easy import into AniList, MAL, or other tracking services.
*   **Real-time Activity Logs:** Monitor backup processes and any potential issues with live log updates in the web UI.
*   **User-Friendly Interface:**
    *   Enjoy a clean, modern, and responsive design that works cottura on desktop, tablets (like iPad Pro), and mobile devices.
    *   Features a comfortable dark mode.
*   **Dockerized for Convenience:** Packaged as a Docker container for smooth and straightforward deployment.


### Access AniList Vault:**
    Open your web browser and go to `http://localhost:5000` (or the IP address of your Docker host if it's running elsewhere).

### Where Your Data is Saved

*   **Backups:** Your backup ZIP files are safely stored in a `backups` folder created in the same directory as your `docker-compose.yml` file. This ensures your backups are preserved even if you update or restart the application.
*   **Application Settings:** Configuration for automatic backups and application logs are stored internally by the application and will persist through normal restarts and updates.

### Using the Web Interface

*   **Manual Backup:** Enter your AniList username, click "Backup Now," and let AniList Vault do the rest.
*   **Automatic Backup:**
    1.  Provide your AniList username.
    2.  Specify how many recent backups you'd like to keep.
    3.  Set the backup frequency in hours.
    4.  Click "Start." You can "Stop" the automatic process at any time.
*   **Activity Logs:** Check here for updates on backup processes and any system messages.
*   **Previous Backups:** This section lists all your past backups. You can view their stats, download them, or delete them.


## 🙏 Acknowledgements

*   A big thank you to **AniList.co** for their fantastic platform and GraphQL API.

---

Developed by [th3Boer](https://github.com/th3Boer)
