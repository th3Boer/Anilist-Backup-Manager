const MAX_LOG_ENTRIES_DISPLAY = 100;
let sseEventSource = null; 

document.addEventListener('DOMContentLoaded', () => {
    loadBackups();
    loadLogs(); 
    checkAutoBackupStatus();
    setupSSE();
    
    if (window.initialLatestStats) {
        displayLatestStats(window.initialLatestStats);
    } else {
        fetchLatestStats(); 
    }

    const modal = document.getElementById('statsModal');
    const span = document.getElementsByClassName('close')[0];
    if (span) {
      span.onclick = closeStatsModal;
    }
    window.onclick = function(event) {
        if (event.target === modal) {
            closeStatsModal();
        }
    };
});

function setupSSE() {
    if (sseEventSource) {
        sseEventSource.close(); 
    }
    sseEventSource = new EventSource("/events");

    sseEventSource.onopen = function() {
        // console.log("SSE Connection Opened.");
    };

    sseEventSource.onmessage = function(event) {
        if (!event.data || event.data === '{}') { 
            return;
        }
        
        try {
            const parsedData = JSON.parse(event.data);
            // console.log("SSE Received:", parsedData);

            if (parsedData.type === 'backup_created') {
                showNotification(`Backup created for ${parsedData.data.username}`, 'success');
                loadBackups(); 
                if (parsedData.data.stats) {
                    const fullStatsData = {
                        anime: parsedData.data.stats.anime,
                        manga: parsedData.data.stats.manga,
                        username: parsedData.data.username,
                        last_updated: parsedData.data.timestamp
                    };
                    displayLatestStats(fullStatsData);
                }
            } else if (parsedData.type === 'backup_deleted') {
                showNotification(`Backup ${parsedData.data.id} deleted.`, 'success');
                loadBackups(); 
                fetchLatestStats(); 
            } else if (parsedData.type === 'latest_stats_updated') {
                displayLatestStats(parsedData.data); 
            } else if (parsedData.type === 'log_updated') {
                if (parsedData.data) {
                    appendLogEntryToDisplay(parsedData.data); 
                }
            }
        } catch (e) {
            console.error("Error parsing SSE data:", e, "Data:", event.data);
        }
    };

    sseEventSource.addEventListener('keep-alive', function(event) {
        // console.log("SSE Keep-alive event received");
    });

    sseEventSource.onerror = function(err) {
        console.error("EventSource failed:", err);
        addLogEntryToUI("[SYSTEM] SSE connection error. Real-time updates stopped.", false); 
        if (sseEventSource) {
            sseEventSource.close();
        }
        // setTimeout(setupSSE, 10000); 
    };
}

function appendLogEntryToDisplay(logEntryData) {
    const logContainer = document.getElementById('logContainer');
    if (!logContainer || !logEntryData) return;

    const date = new Date(logEntryData.timestamp).toLocaleString();
    const logClass = logEntryData.is_success ? 'log-success' : 'log-error';
    const entry = document.createElement('div');
    entry.classList.add('log-entry', logClass);
    entry.innerHTML = `<span>${date}</span> - <span>${logEntryData.message}</span>`;
    
    logContainer.appendChild(entry);

    while (logContainer.children.length > MAX_LOG_ENTRIES_DISPLAY) {
        logContainer.removeChild(logContainer.firstChild);
    }
    logContainer.scrollTop = logContainer.scrollHeight; 
}


async function fetchLatestStats() {
    try {
        const response = await fetch('/latest-stats');
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const stats = await response.json();
        displayLatestStats(stats); 
    } catch (error) {
        console.error("Failed to fetch latest stats:", error);
        const statsOverviewDiv = document.getElementById('latestStatsOverview');
        if (statsOverviewDiv) statsOverviewDiv.innerHTML = '<p>Could not load latest backup stats.</p>';
    }
}

function formatStatusLabel(status) {
    // Ersetzt Underscores mit Leerzeichen und macht dann den ersten Buchstaben jedes Wortes groß.
    // Beispiel: "on_hold" -> "On Hold", "plan_to_watch" -> "Plan To Watch"
    return status.replace(/_/g, ' ')
                 .replace(/\b\w/g, l => l.toUpperCase());
}

function displayLatestStats(statsData) {
    const statsOverviewDiv = document.getElementById('latestStatsOverview');
    if (!statsOverviewDiv) return;

    if (!statsData || !statsData.anime || !statsData.manga || !statsData.username) { 
        statsOverviewDiv.innerHTML = '<p>No backup data available yet. Create a backup to see stats.</p>';
        return;
    }
    
    const { anime, manga, username, last_updated } = statsData;
    let lastUpdatedDate = 'N/A';
    if (last_updated) {
        try {
            lastUpdatedDate = new Date(last_updated).toLocaleString();
        } catch (e) { /* ignore date parsing error */ }
    }
    
    statsOverviewDiv.innerHTML = `
        <div class="detailed-stats-container" style="padding: 0; gap: 10px;">
            <div class="detailed-stats-section" data-type="anime" style="padding: 15px;">
                <h3 style="font-size: 1.2rem; margin-bottom: 15px;">Anime Stats (${username || 'N/A'})</h3>
                <div class="main-stats">
                    <div class="stat-box"> <div class="stat-label">Total</div> <div class="stat-value">${anime.totalEntries !== undefined ? anime.totalEntries : 'N/A'}</div> </div>
                    <div class="stat-box"> <div class="stat-label">Episodes</div> <div class="stat-value">${anime.episodesWatched !== undefined ? anime.episodesWatched : 'N/A'}</div> </div>
                    <div class="stat-box"> <div class="stat-label">Mean Score</div> <div class="stat-value">${anime.meanScore !== undefined && anime.meanScore > 0 ? anime.meanScore.toFixed(1) : 'N/A'}</div> </div>
                </div>
                <div class="status-grid">
                    ${Object.entries(anime.status || {}).map(([statusKey, count]) => `
                        <div class="status-box ${statusKey.toLowerCase().replace(/\s+/g, '-').replace('_','-')}" style="padding: 6px;">
                            <div class="status-count">${count}</div> <div class="status-label" style="font-size: 0.7rem;">${formatStatusLabel(statusKey)}</div>
                        </div>`).join('')}
                </div>
            </div>
            <div class="detailed-stats-section" data-type="manga" style="padding: 15px;">
                <h3 style="font-size: 1.2rem; margin-bottom: 15px;">Manga Stats (${username || 'N/A'})</h3>
                <div class="main-stats">
                    <div class="stat-box"> <div class="stat-label">Total</div> <div class="stat-value">${manga.totalEntries !== undefined ? manga.totalEntries : 'N/A'}</div> </div>
                    <div class="stat-box"> <div class="stat-label">Chapters</div> <div class="stat-value">${manga.chaptersRead !== undefined ? manga.chaptersRead : 'N/A'}</div> </div>
                    <div class="stat-box"> <div class="stat-label">Volumes</div> <div class="stat-value">${manga.volumesRead !== undefined ? manga.volumesRead : 'N/A'}</div> </div>
                    <div class="stat-box"> <div class="stat-label">Mean Score</div> <div class="stat-value">${manga.meanScore !== undefined && manga.meanScore > 0 ? manga.meanScore.toFixed(1) : 'N/A'}</div> </div>
                </div>
                 <div class="status-grid">
                    ${Object.entries(manga.status || {}).map(([statusKey, count]) => `
                        <div class="status-box ${statusKey.toLowerCase().replace(/\s+/g, '-').replace('_','-')}" style="padding: 6px;">
                            <div class="status-count">${count}</div> <div class="status-label" style="font-size: 0.7rem;">${formatStatusLabel(statusKey)}</div>
                        </div>`).join('')}
                </div>
            </div>
        </div>
        <p style="font-size: 0.8rem; color: var(--text-secondary); text-align: center; margin-top: 10px;">Last updated: ${lastUpdatedDate}</p>`;
}


async function manualBackup() {
    const usernameInput = document.getElementById('manualUsername');
    const username = usernameInput.value.trim(); 
    if (!username) {
        showNotification('Manual Backup: Please enter a username.', 'error', true); 
        usernameInput.focus();
        return;
    }

    showNotification(`Manual Backup: Starting backup for ${username}... This may take a moment.`, 'info');
    const backupButton = usernameInput.nextElementSibling; 
    if(backupButton) backupButton.disabled = true;

    try {
        const response = await fetch('/backup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username })
        });
        const result = await response.json(); 
        
        if (response.ok && result.status === 'success') {
            showNotification(result.message || `Manual backup for ${username} completed successfully.`, 'success');
        } else {
            const errorMessage = result.error || `Backup request failed with status: ${response.status}`;
            throw new Error(errorMessage);
        }
    } catch (error) {
        console.error('Manual Backup Error:', error);
        showNotification(`Manual Backup Failed: ${error.message}`, 'error', true); 
        addLogEntryToUI(`[ERROR] Manual backup for ${username} failed: ${error.message}`, false);
    } finally {
        if(backupButton) backupButton.disabled = false;
    }
}

async function toggleAutoBackup() {
    const button = document.getElementById('autoBackupButton');
    const usernameInput = document.getElementById('autoUsername');
    const username = usernameInput.value.trim();
    const keepLast = document.getElementById('keepLastBackups').value;
    const interval = document.getElementById('backupInterval').value; 

    const action = button.textContent === 'Start' ? 'start' : 'stop';
    showNotification(`Auto Backup: Attempting to ${action} for ${username || 'N/A'}...`, 'info');
    button.disabled = true; 

    try {
        let response;
        let payload = {};

        if (action === 'start') {
            if (!username || !keepLast || !interval) {
                throw new Error('Please fill in all auto backup fields (username, keep last, interval).');
            }
            if (parseInt(keepLast) <=0 || parseFloat(interval) <=0) {
                throw new Error('Keep last and interval must be positive numbers.');
            }
            payload = { username, keepLast, interval };
            response = await fetch('/auto-backup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
        } else { 
            response = await fetch('/stop-auto-backup', { method: 'POST' });
        }

        const result = await response.json();
        if (response.ok && result.status === 'success') {
            showNotification(result.message || `Auto backup ${action}ed successfully.`, 'success');
        } else {
            throw new Error(result.error || `Failed to ${action} auto backup.`);
        }
    } catch (error) {
        console.error(`Auto Backup ${action} Error:`, error);
        showNotification(`Auto Backup Failed: ${error.message}`, 'error', true);
        addLogEntryToUI(`[ERROR] Auto backup ${action} failed: ${error.message}`, false);
    } finally {
        await checkAutoBackupStatus(); 
    }
}

async function checkAutoBackupStatus() {
    const button = document.getElementById('autoBackupButton');
    const usernameInput = document.getElementById('autoUsername');
    const keepLastInput = document.getElementById('keepLastBackups');
    const intervalInput = document.getElementById('backupInterval');
    
    button.disabled = true; 

    try {
        const response = await fetch('/auto-backup-status');
        const result = await response.json();

        if (result.running && result.config) {
            button.textContent = 'Stop';
            button.classList.remove('btn-green');
            button.classList.add('btn-red');
            usernameInput.value = result.config.username || '';
            keepLastInput.value = result.config.keepLast || '5';
            intervalInput.value = result.config.interval || '24';
            usernameInput.disabled = true;
            keepLastInput.disabled = true;
            intervalInput.disabled = true;
        } else {
            button.textContent = 'Start';
            button.classList.remove('btn-red');
            button.classList.add('btn-green');
            if (result.config) { 
                 usernameInput.value = result.config.username || '';
                 keepLastInput.value = result.config.keepLast || '5';
                 intervalInput.value = result.config.interval || '24';
            }
            usernameInput.disabled = false;
            keepLastInput.disabled = false;
            intervalInput.disabled = false;
        }
    } catch (error) {
        console.error('Failed to get auto backup status:', error);
        addLogEntryToUI('[SYSTEM] Failed to get auto backup status.', false);
    } finally {
        button.disabled = false; 
    }
}

async function loadBackups() {
    try {
        const response = await fetch('/backups');
        const backups = await response.json();
        const backupsTableBody = document.getElementById('backupsTableBody');
        backupsTableBody.innerHTML = ''; 

        if (backups.error) {
            showNotification(`Error loading backups: ${backups.error}`, 'error', true);
            addLogEntryToUI(`[ERROR] Loading backups: ${backups.error}`, false);
            return;
        }
        if (!Array.isArray(backups) || backups.length === 0) {
            backupsTableBody.innerHTML = '<tr><td colspan="4" style="text-align:center;">No backups found.</td></tr>';
            return;
        }

        backups.forEach(backup => {
            const row = backupsTableBody.insertRow();
            const date = backup.date ? new Date(backup.date).toLocaleString() : 'N/A';
            row.insertCell().textContent = date;
            row.insertCell().textContent = backup.username || 'N/A';
            row.insertCell().textContent = backup.content || 'N/A';
            
            const actionsCell = row.insertCell();
            actionsCell.classList.add('actions'); 
            actionsCell.innerHTML = `
                <button class="btn-blue" onclick="openStatsModal('${backup.id}', '${backup.username || ''}')">Stats</button>
                <button class="btn-green" onclick="window.location.href='/backup/${backup.id}/download'">Download</button>
                <button class="btn-red" onclick="deleteBackup('${backup.id}')">Delete</button>
            `;
            row.cells[0].setAttribute('data-label', 'Date');
            row.cells[1].setAttribute('data-label', 'Username');
            row.cells[2].setAttribute('data-label', 'Content');
            row.cells[3].setAttribute('data-label', 'Actions');
        });
    } catch (error) {
        console.error('Load backups error:', error);
        showNotification('Failed to load backups.', 'error', true);
        addLogEntryToUI('[ERROR] Failed to load backups.', false);
    }
}

async function deleteBackup(backupId) {
    if (!confirm(`Are you sure you want to delete backup ${backupId}? This cannot be undone.`)) {
        return;
    }
    showNotification(`Deleting backup ${backupId}...`, 'info');
    try {
        const response = await fetch(`/backup/${backupId}`, { method: 'DELETE' });
        const result = await response.json();
        if (response.ok && result.status === 'success') {
            showNotification(`Backup ${backupId} deleted successfully.`, 'success');
        } else {
            throw new Error(result.error || 'Failed to delete backup.');
        }
    } catch (error) {
        console.error(`Delete Backup ${backupId} Error:`, error);
        showNotification(`Failed to delete backup ${backupId}: ${error.message}`, 'error', true);
        addLogEntryToUI(`[ERROR] Failed to delete backup ${backupId}: ${error.message}`, false);
    }
}

async function openStatsModal(backupId, username) {
    const modal = document.getElementById('statsModal');
    const statsContentContainer = document.getElementById('statsContentContainer');
    const modalUsernameSpan = document.getElementById('statsModalUsername');

    statsContentContainer.innerHTML = '<div class="loading-container"><div class="loading-bar"><div class="loading-bar-progress"></div></div> Fetching stats...</div>';
    modal.style.display = 'block';
    modalUsernameSpan.textContent = username || 'N/A';

    try {
        const response = await fetch(`/backup/${backupId}/stats`);
        const stats = await response.json();

        if (response.ok) {
            if (stats.error) {
                 statsContentContainer.innerHTML = `<p style="color: var(--status-dropped);">Error loading stats: ${stats.error}</p>`;
                 return;
            }
            if (!stats.anime || !stats.manga) {
                statsContentContainer.innerHTML = `<p>Statistics data is incomplete for this backup.</p>`;
                return;
            }
            const { anime, manga } = stats;
            statsContentContainer.innerHTML = `
                <div class="detailed-stats-container">
                    <div class="detailed-stats-section" data-type="anime">
                        <h3>Anime Statistics</h3>
                        <div class="main-stats">
                            <div class="stat-box"> <div class="stat-label">Total Entries</div> <div class="stat-value">${anime.totalEntries !== undefined ? anime.totalEntries : 'N/A'}</div> </div>
                            <div class="stat-box"> <div class="stat-label">Episodes Watched</div> <div class="stat-value">${anime.episodesWatched !== undefined ? anime.episodesWatched : 'N/A'}</div> </div>
                            <div class="stat-box"> <div class="stat-label">Mean Score</div> <div class="stat-value">${anime.meanScore !== undefined && anime.meanScore > 0 ? anime.meanScore.toFixed(1) : 'N/A'}</div> </div>
                        </div>
                        <h4 class="status-title">Status Distribution</h4>
                        <div class="status-grid">
                            ${Object.entries(anime.status || {}).map(([statusKey, count]) => `
                                <div class="status-box ${statusKey.toLowerCase().replace(/\s+/g, '-').replace('_','-')}">
                                    <div class="status-count">${count}</div> <div class="status-label">${formatStatusLabel(statusKey)}</div>
                                </div>`).join('')}
                        </div>
                    </div>
                    <div class="stats-divider"></div>
                    <div class="detailed-stats-section" data-type="manga">
                        <h3>Manga Statistics</h3>
                        <div class="main-stats">
                            <div class="stat-box"> <div class="stat-label">Total Entries</div> <div class="stat-value">${manga.totalEntries !== undefined ? manga.totalEntries : 'N/A'}</div> </div>
                            <div class="stat-box"> <div class="stat-label">Chapters Read</div> <div class="stat-value">${manga.chaptersRead !== undefined ? manga.chaptersRead : 'N/A'}</div> </div>
                            <div class="stat-box"> <div class="stat-label">Volumes Read</div> <div class="stat-value">${manga.volumesRead !== undefined ? manga.volumesRead : 'N/A'}</div> </div>
                            <div class="stat-box"> <div class="stat-label">Mean Score</div> <div class="stat-value">${manga.meanScore !== undefined && manga.meanScore > 0 ? manga.meanScore.toFixed(1) : 'N/A'}</div> </div>
                        </div>
                        <h4 class="status-title">Status Distribution</h4>
                        <div class="status-grid">
                             ${Object.entries(manga.status || {}).map(([statusKey, count]) => `
                                <div class="status-box ${statusKey.toLowerCase().replace(/\s+/g, '-').replace('_','-')}">
                                    <div class="status-count">${count}</div> <div class="status-label">${formatStatusLabel(statusKey)}</div>
                                </div>`).join('')}
                        </div>
                    </div>
                </div>`;
        } else {
            statsContentContainer.innerHTML = `<p style="color: var(--status-dropped);">Could not load statistics: ${stats.error || 'Server error'}</p>`;
        }
    } catch (error) {
        console.error('Error fetching stats for modal:', error);
        statsContentContainer.innerHTML = `<p style="color: var(--status-dropped);">Could not load statistics. Error: ${error.message}</p>`;
    }
}

function closeStatsModal() {
    const modal = document.getElementById('statsModal');
    if (modal) modal.style.display = 'none';
    const statsContentContainer = document.getElementById('statsContentContainer');
    if (statsContentContainer) statsContentContainer.innerHTML = ''; 
}

async function loadLogs() {
    const logContainer = document.getElementById('logContainer');
    if (!logContainer) return;
    logContainer.innerHTML = '<div class="log-entry">Loading logs...</div>'; 

    try {
        const response = await fetch('/logs');
        const logsFromServer = await response.json(); 
        logContainer.innerHTML = ''; 

        if (logsFromServer.error) {
            logContainer.innerHTML = `<div class="log-entry log-error">Error loading logs: ${logsFromServer.error}</div>`;
            return;
        }
        if (!Array.isArray(logsFromServer)) {
             logContainer.innerHTML = `<div class="log-entry log-error">Received invalid log data from server.</div>`;
             return;
        }
        
        const logsToDisplay = logsFromServer.slice(-MAX_LOG_ENTRIES_DISPLAY);

        logsToDisplay.forEach(logEntryData => {
            appendLogEntryToDisplay(logEntryData); 
        });
        if (logsToDisplay.length > 0) {
            logContainer.scrollTop = logContainer.scrollHeight;
        } else {
            logContainer.innerHTML = '<div class="log-entry">No log entries found.</div>';
        }

    } catch (error) {
        console.error('Failed to load logs:', error);
        if(logContainer) logContainer.innerHTML = '<div class="log-entry log-error">Failed to load logs. Check console for details.</div>';
    }
}

function addLogEntryToUI(message, isSuccess) {
    const logContainer = document.getElementById('logContainer');
    if (!logContainer) return;

    const date = new Date().toLocaleString();
    const logClass = isSuccess ? 'log-success' : 'log-error';
    const entry = document.createElement('div');
    entry.classList.add('log-entry', logClass);
    entry.innerHTML = `<span>${date}</span> - <span>${message}</span>`;
    
    while (logContainer.children.length >= MAX_LOG_ENTRIES_DISPLAY) {
        logContainer.removeChild(logContainer.firstChild);
    }
    logContainer.appendChild(entry);
    logContainer.scrollTop = logContainer.scrollHeight;
}

function showNotification(message, type = 'info', useAlertOnError = false) {
    console.log(`NOTIFICATION (${type}): ${message}`); 
    
    if (type === 'error' && useAlertOnError) {
        alert(`ERROR: ${message}`);
    }
    let logTypePrefix = '[NOTIF]';
    if (type === 'success') logTypePrefix = '[SUCCESS]';
    if (type === 'error') logTypePrefix = '[ERROR]';
    if (type === 'info') logTypePrefix = '[INFO]';

    addLogEntryToUI(`${logTypePrefix} ${message}`, type === 'success' || type === 'info');
}
