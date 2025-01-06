let isAutoBackupRunning = false;
let currentAutoBackupUsername = null;

const WELCOME_MESSAGE = "Welcome to the AniList Backup Manager! This tool helps you create and manage automatic backups from AniList.co\n⚠️ Important: Ensure that your AniList.co profile is set to \"Public\" so the backup can access your data.";

function addLog(message, isSuccess = false) {
    const logContainer = document.getElementById('logContainer');
    const logEntry = document.createElement('div');
    logEntry.className = `log-entry${isSuccess ? ' log-success' : ''}`;
    logEntry.textContent = `[${new Date().toLocaleString()}] ${message}`;
    logContainer.appendChild(logEntry);
    logContainer.scrollTop = logContainer.scrollHeight;

    fetch('/save-log', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            message,
            isSuccess,
            timestamp: new Date().toISOString()
        })
    }).catch(error => console.error('Error saving log:', error));
    
    updateBackupsList();
}

function loadLogs() {
    fetch('/logs')
        .then(response => response.json())
        .then(logs => {
            const logContainer = document.getElementById('logContainer');
            logContainer.innerHTML = '';
            
            if (logs.length === 0) {
                const welcomeLines = WELCOME_MESSAGE.split('\n');
                welcomeLines.forEach(line => {
                    const logEntry = document.createElement('div');
                    logEntry.className = 'log-entry';
                    logEntry.style.color = '#ffffff';
                    logEntry.textContent = `[${new Date().toLocaleString()}] ${line}`;
                    logContainer.appendChild(logEntry);
                });
            } else {
                logs.forEach(log => {
                    const logEntry = document.createElement('div');
                    logEntry.className = `log-entry${log.is_success ? ' log-success' : ''}`;
                    logEntry.textContent = `[${new Date(log.timestamp).toLocaleString()}] ${log.message}`;
                    logContainer.appendChild(logEntry);
                });
            }
            
            logContainer.scrollTop = logContainer.scrollHeight;
        })
        .catch(error => console.error('Error loading logs:', error));
}

function setButtonLoading(button, isLoading, newText = null) {
    if (isLoading) {
        // Speichere den neuen Text statt des aktuellen, falls vorhanden
        button.dataset.newText = newText || button.textContent;
        button.disabled = true;
        button.innerHTML = `
            <div class="loading-container">
                <div class="loading-bar">
                    <div class="loading-bar-progress"></div>
                </div>
                <span>${button.textContent}</span>
            </div>
        `;
    } else {
        button.disabled = false;
        // Verwende den gespeicherten neuen Text
        button.textContent = button.dataset.newText || button.textContent;
        delete button.dataset.newText;
    }
}

function validateAutoBackupFields() {
    const username = document.getElementById('autoUsername').value.trim();
    const keepLast = document.getElementById('keepLastBackups').value.trim();
    const interval = document.getElementById('backupInterval').value.trim();
    
    if (!username) {
        addLog('Please enter a username');
        return false;
    }
    if (!keepLast) {
        addLog('Please specify how many backups to keep');
        return false;
    }
    if (!interval) {
        addLog('Please specify the backup interval');
        return false;
    }

    if (!Number.isInteger(Number(keepLast)) || Number(keepLast) <= 0) {
        addLog('Keep last must be a positive whole number');
        return false;
    }

    if (isNaN(Number(interval)) || Number(interval) <= 0) {
        addLog('Interval must be a positive number');
        return false;
    }

    return true;
}


function setupSSEConnection() {
    const eventSource = new EventSource('/events');
    
    eventSource.onmessage = function(event) {
        const data = JSON.parse(event.data);
        if (data.type === 'backup_created') {
            updateBackupsList();
            updateOverview();
        }
    };

    eventSource.onerror = function(error) {
        console.error('SSE connection error:', error);
        // Try to reconnect after 5 seconds
        setTimeout(setupSSEConnection, 5000);
    };
}

// Initial calls
loadLogs();
updateBackupsList();
setupSSEConnection();

// Check auto backup status on page load



function updateButtonState(isRunning) {
    const button = document.getElementById('autoBackupButton');
    const usernameInput = document.getElementById('autoUsername');
    const keepLastInput = document.getElementById('keepLastBackups');
    const intervalInput = document.getElementById('backupInterval');
    
    if (isRunning) {
        button.textContent = 'Stop';
        button.className = 'btn-red';
        usernameInput.disabled = true;
        keepLastInput.disabled = true;
        intervalInput.disabled = true;
    } else {
        button.textContent = 'Start';
        button.className = 'btn-green';
        usernameInput.disabled = false;
        keepLastInput.disabled = false;
        intervalInput.disabled = false;
    }
}


async function cleanupUserBackups(username, keepLast) {
    try {
        const response = await fetch('/backups');
        if (!response.ok) throw new Error('Failed to fetch backups');
        
        const backups = await response.json();
        const userBackups = backups
            .filter(backup => backup.username === username)
            .sort((a, b) => new Date(b.date) - new Date(a.date));

        if (userBackups.length > keepLast) {
            const backupsToDelete = userBackups.slice(keepLast);
            for (const backup of backupsToDelete) {
                await deleteBackup(backup.id, false);
            }
            addLog(`Deleted ${backupsToDelete.length} old backup(s) for ${username}`, true);
        }
    } catch (error) {
        addLog(`Error cleaning up backups: ${error.message}`);
    }
}

async function manualBackup() {
    const username = document.getElementById('manualUsername').value.trim();
    if (!username) {
        addLog('Please enter a username');
        return;
    }

    const button = document.querySelector('.btn-blue');
    setButtonLoading(button, true);
    addLog('Starting manual backup...', true);
    
    try {
        const response = await fetch('/backup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Backup failed');
        }

        addLog('Manual backup completed successfully!', true);
        await updateBackupsList();
        await updateOverview();
    } catch (error) {
        addLog(`Error: ${error.message}`);
    } finally {
        setButtonLoading(button, false);
    }
}

async function toggleAutoBackup() {
    const button = document.getElementById('autoBackupButton');
    const usernameInput = document.getElementById('autoUsername');
    const keepLastInput = document.getElementById('keepLastBackups');
    const intervalInput = document.getElementById('backupInterval');
    
    const username = usernameInput.value.trim();
    const keepLast = keepLastInput.value.trim();
    const interval = intervalInput.value.trim();

    // Startvorgang
    if (button.textContent === 'Start') {
        if (!validateAutoBackupFields()) {
            return;
        }
        setButtonLoading(button, true, 'Stop');  // Hier den neuen Text mitgeben
        try {
            const response = await fetch('/auto-backup', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ 
                    username, 
                    keepLast: parseInt(keepLast), 
                    interval: parseFloat(interval) 
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to start auto backup');
            }

            isAutoBackupRunning = true;
            currentAutoBackupUsername = username;
            
            usernameInput.disabled = true;
            keepLastInput.disabled = true;
            intervalInput.disabled = true;
            
            button.className = 'btn-red';
            
            addLog(`Started auto backup for ${username} - keeping last ${keepLast} backups, running every ${interval} hours`, true);
            await cleanupUserBackups(username, parseInt(keepLast));
        } catch (error) {
            addLog(`Error: ${error.message}`);
            setButtonLoading(button, true, 'Start');  // Bei Fehler zurück zu Start
        } finally {
            setButtonLoading(button, false);
        }
    } 
    // Stoppvorgang
    else {
        setButtonLoading(button, true, 'Start');  // Hier den neuen Text mitgeben
        try {
            const response = await fetch('/stop-auto-backup', { 
                method: 'POST'
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to stop auto backup');
            }

            isAutoBackupRunning = false;
            currentAutoBackupUsername = null;
            
            usernameInput.disabled = false;
            keepLastInput.disabled = false;
            intervalInput.disabled = false;
            
            button.className = 'btn-green';
            
            addLog('Auto backup stopped successfully', true);
        } catch (error) {
            addLog(`Error: ${error.message}`);
            setButtonLoading(button, true, 'Stop');  // Bei Fehler zurück zu Stop
        } finally {
            setButtonLoading(button, false);
        }
    }
}

// In main.js, update die Funktion, die die Backup-Zeilen erstellt:

function updateBackupsList() {
    try {
        fetch('/backups')
            .then(response => response.json())
            .then(backups => {
                const tbody = document.getElementById('backupsTableBody');
                tbody.innerHTML = '';

                backups.forEach(backup => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td data-label="Date">${new Date(backup.date).toLocaleString()}</td>
                        <td data-label="Username">${backup.username}</td>
                        <td data-label="Content">${backup.content}</td>
                        <td data-label="Actions">
                            <div class="actions">
                                <button class="btn-purple" onclick="showStats('${backup.id}')">Stats</button>
                                <button class="btn-yellow" onclick="downloadBackup('${backup.id}')">Download</button>
                                <button class="btn-red" onclick="deleteBackup('${backup.id}', true)">Delete</button>
                            </div>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });
            });
    } catch (error) {
        addLog(`Error updating backups list: ${error.message}`);
    }
}





async function downloadBackup(backupId) {
    try {
        const response = await fetch(`/backup/${backupId}/download`);
        if (!response.ok) throw new Error('Failed to download backup');
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `backup_${backupId}.zip`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        addLog('Backup downloaded successfully!', true);
    } catch (error) {
        addLog(`Error downloading backup: ${error.message}`);
    }
}

async function deleteBackup(backupId, showConfirm = true) {
    if (showConfirm && !confirm('Are you sure you want to delete this backup?')) return;

    try {
        const response = await fetch(`/backup/${backupId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) throw new Error('Failed to delete backup');
        
        if (showConfirm) {
            addLog('Backup deleted successfully!', true);
        }
        await updateBackupsList();
    } catch (error) {
        if (showConfirm) {
            addLog(`Error deleting backup: ${error.message}`);
        }
    }
}

function showStats(backupId) {
    try {
        fetch(`/backup/${backupId}/stats`)
            .then(response => response.json())
            .then(stats => {
                const statsContent = document.getElementById('statsContent');
                
                statsContent.innerHTML = `
                    <div class="detailed-stats-container">
                        <div class="detailed-stats-section">
                            <h3>Anime Statistics</h3>
                            <div class="main-stats">
                                <div class="stat-box">
                                    <div class="stat-icon">📚</div>
                                    <div class="stat-label">Total Entries</div>
                                    <div class="stat-value">${stats.anime.totalEntries}</div>
                                </div>
                                <div class="stat-box">
                                    <div class="stat-icon">⏱️</div>
                                    <div class="stat-label">Time Watched</div>
                                    <div class="stat-value">${stats.anime.timeWatched}h</div>
                                </div>
                                <div class="stat-box">
                                    <div class="stat-icon">⭐</div>
                                    <div class="stat-label">Mean Score</div>
                                    <div class="stat-value">${stats.anime.meanScore.toFixed(1)}</div>
                                </div>
                            </div>
                            
                            <div class="status-title">Status Distribution</div>
                            <div class="status-grid">
                                <div class="status-box watching">
                                    <div class="status-count">${stats.anime.status?.watching || 0}</div>
                                    <div class="status-label">Watching</div>
                                </div>
                                <div class="status-box completed">
                                    <div class="status-count">${stats.anime.status?.completed || 0}</div>
                                    <div class="status-label">Completed</div>
                                </div>
                                <div class="status-box on-hold">
                                    <div class="status-count">${stats.anime.status?.on_hold || 0}</div>
                                    <div class="status-label">On Hold</div>
                                </div>
                                <div class="status-box dropped">
                                    <div class="status-count">${stats.anime.status?.dropped || 0}</div>
                                    <div class="status-label">Dropped</div>
                                </div>
                                <div class="status-box planning">
                                    <div class="status-count">${stats.anime.status?.planning || 0}</div>
                                    <div class="status-label">Plan to Watch</div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="stats-divider"></div>
                        
                        <div class="detailed-stats-section">
                            <h3>Manga Statistics</h3>
                            <div class="main-stats">
                                <div class="stat-box">
                                    <div class="stat-icon">📚</div>
                                    <div class="stat-label">Total Entries</div>
                                    <div class="stat-value">${stats.manga.totalEntries}</div>
                                </div>
                                <div class="stat-box">
                                    <div class="stat-icon">📖</div>
                                    <div class="stat-label">Chapters Read</div>
                                    <div class="stat-value">${stats.manga.chaptersRead}</div>
                                </div>
                                <div class="stat-box">
                                    <div class="stat-icon">⭐</div>
                                    <div class="stat-label">Mean Score</div>
                                    <div class="stat-value">${stats.manga.meanScore.toFixed(1)}</div>
                                </div>
                            </div>
                            
                            <div class="status-title">Status Distribution</div>
                            <div class="status-grid">
                                <div class="status-box reading">
                                    <div class="status-count">${stats.manga.status?.reading || 0}</div>
                                    <div class="status-label">Reading</div>
                                </div>
                                <div class="status-box completed">
                                    <div class="status-count">${stats.manga.status?.completed || 0}</div>
                                    <div class="status-label">Completed</div>
                                </div>
                                <div class="status-box on-hold">
                                    <div class="status-count">${stats.manga.status?.on_hold || 0}</div>
                                    <div class="status-label">On Hold</div>
                                </div>
                                <div class="status-box dropped">
                                    <div class="status-count">${stats.manga.status?.dropped || 0}</div>
                                    <div class="status-label">Dropped</div>
                                </div>
                                <div class="status-box planning">
                                    <div class="status-count">${stats.manga.status?.planning || 0}</div>
                                    <div class="status-label">Plan to Read</div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
                
                modal.style.display = "block";
            });
    } catch (error) {
        addLog(`Error showing stats: ${error.message}`);
    }
}

async function updateOverview() {
    try {
        const response = await fetch('/backups');
        if (!response.ok) throw new Error('Failed to fetch backups');
        
        const backups = await response.json();
        if (backups.length > 0) {
            const latestBackup = backups[0];
            const statsResponse = await fetch(`/backup/${latestBackup.id}/stats`);
            if (!statsResponse.ok) throw new Error('Failed to fetch stats');
            
            const stats = await statsResponse.json();
            
            document.getElementById('animeTotalEntries').textContent = stats.anime.totalEntries;
            document.getElementById('animeTimeWatched').textContent = `${stats.anime.timeWatched}h`;
            document.getElementById('animeMeanScore').textContent = stats.anime.meanScore.toFixed(1);
            
            document.getElementById('mangaTotalEntries').textContent = stats.manga.totalEntries;
            document.getElementById('mangaChaptersRead').textContent = stats.manga.chaptersRead;
            document.getElementById('mangaMeanScore').textContent = stats.manga.meanScore.toFixed(1);
        }
    } catch (error) {
        console.error('Error updating overview:', error);
    }
}

// Modal handling
const modal = document.getElementById("statsModal");
const closeBtn = document.getElementsByClassName("close")[0];

closeBtn.onclick = function() {
    modal.style.display = "none";
}

window.onclick = function(event) {
    if (event.target == modal) {
        modal.style.display = "none";
    }
}


// Stats Overview Component
const StatsOverview = () => {
    const container = document.getElementById('statsOverview');
    container.innerHTML = `
        <div class="stats-overview">
            <div class="stats-card">
                <div class="stats-card-header">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2" class="mr-2">
                        <rect x="2" y="7" width="20" height="15" rx="2" ry="2"></rect>
                        <polyline points="17 2 12 7 7 2"></polyline>
                    </svg>
                    <h3>Anime Stats</h3>
                </div>
                <div class="stats-card-content">
                    <div class="stats-card-item">
                        <div class="stats-card-label">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2" class="mr-2">
                                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
                                <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
                            </svg>
                            Total Entries
                        </div>
                        <div class="stats-card-value">
                            <span id="animeTotalEntries"></span>
                        </div>
                    </div>
                    <div class="stats-card-item">
                        <div class="stats-card-label">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2" class="mr-2">
                                <circle cx="12" cy="12" r="10"></circle>
                                <polyline points="12 6 12 12 16 14"></polyline>
                            </svg>
                            Time Watched
                        </div>
                        <div class="stats-card-value">
                            <span id="animeTimeWatched"></span>
                        </div>
                    </div>
                    <div class="stats-card-item">
                        <div class="stats-card-label">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2" class="mr-2">
                                <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
                            </svg>
                            Mean Score
                        </div>
                        <div class="stats-card-value">
                            <span id="animeMeanScore"></span>
                        </div>
                    </div>
                </div>
            </div>

            <div class="stats-card">
                <div class="stats-card-header">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#8b5cf6" stroke-width="2" class="mr-2">
                        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
                        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
                    </svg>
                    <h3>Manga Stats</h3>
                </div>
                <div class="stats-card-content">
                    <div class="stats-card-item">
                        <div class="stats-card-label">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#8b5cf6" stroke-width="2" class="mr-2">
                                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
                                <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
                            </svg>
                            Total Entries
                        </div>
                        <div class="stats-card-value">
                            <span id="mangaTotalEntries"></span>
                        </div>
                    </div>
                    <div class="stats-card-item">
                        <div class="stats-card-label">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#8b5cf6" stroke-width="2" class="mr-2">
                                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                                <line x1="3" y1="9" x2="21" y2="9"></line>
                                <line x1="9" y1="21" x2="9" y2="9"></line>
                            </svg>
                            Chapters Read
                        </div>
                        <div class="stats-card-value">
                            <span id="mangaChaptersRead"></span>
                        </div>
                    </div>
                    <div class="stats-card-item">
                        <div class="stats-card-label">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#8b5cf6" stroke-width="2" class="mr-2">
                                <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
                            </svg>
                            Mean Score
                        </div>
                        <div class="stats-card-value">
                            <span id="mangaMeanScore"></span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
};

// Initialize the overview on page load
document.addEventListener('DOMContentLoaded', () => {
    StatsOverview();
});

// Initialize the overview on page load
document.addEventListener('DOMContentLoaded', () => {
    StatsOverview();
});

// Initialize the overview on page load
document.addEventListener('DOMContentLoaded', () => {
    StatsOverview();
});

// Initialize the overview on page load
document.addEventListener('DOMContentLoaded', () => {
    StatsOverview();
});

// Rest of your existing main.js code here...


// Initial calls
loadLogs();
updateBackupsList();

// Check auto backup status on page load
fetch('/auto-backup-status')
    .then(response => response.json())
    .then(status => {
        isAutoBackupRunning = status.running;
        const usernameInput = document.getElementById('autoUsername');
        const keepLastInput = document.getElementById('keepLastBackups');
        const intervalInput = document.getElementById('backupInterval');

        if (status.running && status.config) {
            usernameInput.value = status.config.username;
            keepLastInput.value = status.config.keepLast;
            intervalInput.value = status.config.interval;
        }
        
        updateButtonState(status.running);
    })
    .catch(error => console.error('Error checking auto backup status:', error));