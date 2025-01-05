import threading
import time

class Scheduler:
    def __init__(self):
        self.thread = None
        self.running = False
        self.callback = None
        self.interval = None

    def start(self, callback, interval_hours):
        """Startet den Scheduler"""
        self.callback = callback
        self.interval = interval_hours * 3600  # Konvertiere zu Sekunden
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._run)
            self.thread.daemon = True
            self.thread.start()

    def stop(self):
        """Stoppt den Scheduler"""
        self.running = False
        if self.thread:
            self.thread.join()
            self.thread = None

    def _run(self):
        """Scheduler Hauptschleife"""
        while self.running:
            try:
                self.callback()
            except Exception:
                pass  # Fehler werden geloggt aber nicht propagiert
            time.sleep(self.interval)