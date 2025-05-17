/* Variables */
:root {
  --background-primary: #1a1a1a;
  --background-secondary: #2a2a2a;
  --background-tertiary: #333333;
  
  --status-watching: #3b82f6;  /* Tailwind blue-500 */
  --status-reading: #3b82f6;   /* Same as watching for manga */
  --status-completed: #22c55e; /* Tailwind green-500 */
  --status-on-hold: #eab308;      /* Tailwind yellow-500 */
  --status-dropped: #ef4444;   /* Tailwind red-500 */
  --status-planning: #8b5cf6;  /* Tailwind purple-500 */
  
  --btn-blue: var(--status-watching);
  --btn-green: var(--status-completed);
  --btn-yellow: var(--status-on-hold);
  --btn-red: var(--status-dropped);
  --btn-purple: var(--status-planning);

  --text-primary: #ffffff;
  --text-secondary: #9ca3af; /* gray-400 */
}

/* Global Styles */
body {
   font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
   background-color: var(--background-primary);
   color: var(--text-primary);
   margin: 0;
   padding: 15px;
}

/* Custom Scrollbar */
::-webkit-scrollbar {
    width: 10px;
    height: 10px;
}

::-webkit-scrollbar-track {
    background: var(--background-secondary);
    border-radius: 5px;
}

::-webkit-scrollbar-thumb {
    background: #4a4a4a;
    border-radius: 5px;
}

::-webkit-scrollbar-thumb:hover {
    background: #5a5a5a;
}

.container {
   width: 90%;
   max-width: 1200px;
   margin: 0 auto;
   padding: 0 15px;
}

/* Headings */
h2, h3, h4 {
   margin-top: 0;
   font-weight: 500;
}

h2 {
   font-size: 1.5rem;
   margin-bottom: 1.2rem;
   color: var(--text-primary);
}

h3 {
    font-size: 1.2rem;
    margin-bottom: 1rem;
    color: var(--text-primary);
}

h4 {
   margin: 20px 0 15px;
   font-size: 1.1rem;
   color: var(--text-secondary);
}

/* Section Styling */
.section {
   background-color: var(--background-secondary);
   border-radius: 8px;
   padding: 30px;
   margin-bottom: 25px;
   color: var(--text-primary);
}

/* Input Styles */
.input-group {
   display: flex;
   gap: 10px;
   margin-bottom: 15px;
   align-items: center; /* Vertically align items */
}

input[type="text"], input[type="number"] {
   background-color: var(--background-tertiary);
   border: 1px solid #404040; /* Subtle border */
   padding: 8px 12px;
   border-radius: 4px;
   color: var(--text-primary);
   font-size: 1rem;
   height: 40px;
   box-sizing: border-box;
}
input[type="text"]:focus, input[type="number"]:focus {
    outline: none;
    border-color: var(--btn-blue);
    box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.3);
}


input[type="text"] {
   width: 200px;
}

input[type="number"] {
   flex-grow: 0;
   text-align: center;
}

/* Buttons */
button {
   padding: 12px 24px;
   border: none;
   border-radius: 4px;
   cursor: pointer;
   font-weight: 500;
   font-size: 1rem;
   min-width: 100px;
   color: white;
   transition: background-color 0.2s ease, transform 0.1s ease;
}
button:active {
    transform: translateY(1px);
}


.btn-blue { background-color: var(--btn-blue); }
.btn-green { background-color: var(--btn-green); }
.btn-purple { background-color: var(--btn-purple); }
.btn-yellow { background-color: var(--btn-yellow); }
.btn-red { background-color: var(--btn-red); }

.btn-blue:hover { background-color: #2563eb; }
.btn-green:hover { background-color: #16a34a; }
.btn-yellow:hover { background-color: #ca8a04; }
.btn-red:hover { background-color: #dc2626; }
.btn-purple:hover { background-color: #7c3aed; }

/* Table Styles */
.table {
   width: 100%;
   border-collapse: collapse;
}

.table th, .table td {
   padding: 12px 10px; /* Increased padding */
   border-bottom: 1px solid #404040;
}

.table th {
   background-color: var(--background-tertiary);
   text-align: left;
   font-weight: 500;
   color: var(--text-secondary);
}

.table tr:last-child td {
    border-bottom: none;
}
.table tr:hover {
    background-color: rgba(255,255,255,0.03);
}


/* Modal Styling */
.modal {
   display: none;
   position: fixed;
   z-index: 1000; /* Ensure modal is on top */
   left: 0;
   top: 0;
   width: 100%;
   height: 100%;
   background-color: rgba(0, 0, 0, 0.8); /* Darker overlay */
   overflow-y: auto; /* Allow modal itself to scroll if content is too tall */
}

.modal-content {
    padding: 24px;
    width: 90%; /* Responsive width */
    max-width: 1000px;  /* Increased for better layout */
    background-color: var(--background-secondary);
    margin: 5vh auto; /* Centered with margin from top/bottom */
    border-radius: 8px;
    box-shadow: 0 5px 15px rgba(0,0,0,0.5);
    position: relative; /* For close button positioning */
}

#statsContentContainer { /* Specific container for stats inside modal */
    max-height: 80vh; /* Max height for the content area */
    overflow-y: auto; /* Scroll for content area if it overflows */
}


.stats-container { /* Old class, might be unused now, ensure new classes are used */
    display: flex;
    gap: 24px;
    justify-content: space-between;
}

.stats-section { /* Old class, might be unused now */
    flex: 1;
    padding: 20px;
    border-radius: 8px;
}


/* Logs Section */
.logs {
   padding: 15px;
   font-family: monospace;
   font-size: 0.9rem;
   max-height: 300px;
   overflow-y: auto;
   background-color: var(--background-primary); /* Slightly darker than section */
   border: 1px solid var(--background-tertiary);
   border-radius: 6px;
   line-height: 1.5;
}

.log-entry {
   margin: 5px 0;
   padding: 3px 5px;
   border-radius: 3px;
}
.log-entry span:first-child {
    color: var(--text-secondary);
    margin-right: 10px;
}

.log-success {
   color: var(--status-completed);
}
.log-error { /* Added for error messages */
    color: var(--status-dropped);
}


/* Close Button */
.close {
   color: #aaa;
   position: absolute; /* Position relative to modal-content */
   top: 10px;
   right: 20px;
   font-size: 28px;
   font-weight: bold;
   cursor: pointer;
}

.close:hover, .close:focus {
   color: white;
   text-decoration: none;
}

/* Loading Animation */
.loading-container {
    display: flex;
    align-items: center;
    justify-content: center; /* Center it */
    gap: 10px;
    color: var(--text-secondary);
    padding: 20px;
}

.loading-bar {
    width: 50px;
    height: 3px;
    background-color: rgba(255, 255, 255, 0.2);
    border-radius: 2px;
    overflow: hidden;
}

.loading-bar-progress {
    width: 100%;
    height: 100%;
    background-color: white;
    animation: loading 1s infinite linear;
    transform-origin: 0% 50%;
}

@keyframes loading {
    0% { transform: scaleX(0); }
    50% { transform: scaleX(1); }
    100% { transform: scaleX(0); transform-origin: 100% 50%; }
}

/* GitHub Footer */
.github-footer {
    position: fixed;
    bottom: 0;
    right: 0;
    padding: 10px 15px;
    background-color: var(--background-primary); /* Match body for consistency */
    border-top-left-radius: 6px;
    font-size: 0.9rem;
    z-index: 100; /* Above other content but below modal */
    box-shadow: 0 -2px 10px rgba(0,0,0,0.3);
}

.github-footer a {
    color: #58a6ff; /* Default link color */
    text-decoration: none;
}
.github-footer a:hover {
    color: #79b8ff !important; /* Hover color from HTML */
    text-decoration: underline;
}

/* Detailed Stats Styling (for Modal and Main Page Overview) */
.detailed-stats-container {
    display: flex;
    gap: 24px; /* Was 32px, adjusted for potentially smaller main page area */
    padding: 10px 0; /* Reduced padding for main page */
}

.detailed-stats-section {
    flex: 1;
    background-color: var(--background-tertiary);
    border-radius: 12px;
    padding: 20px; /* Was 24px */
}

.detailed-stats-section h3 {
    font-size: 1.3rem; /* Was 1.4rem */
    margin: 0 0 20px 0; /* Was 24px */
    text-align: center;
    color: var(--text-primary);
    font-weight: 600;
}

.main-stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); /* Responsive columns */
    gap: 16px; /* Was 20px */
    margin-bottom: 24px; /* Was 32px */
}

.stat-box {
    background-color: var(--background-secondary);
    padding: 12px; /* Was 16px */
    border-radius: 10px;
    text-align: center;
}

.stat-icon { /* Not currently used in JS, but can be added */
    font-size: 1.5rem;
    margin-bottom: 8px;
}

.stat-label {
    color: var(--text-secondary);
    font-size: 0.85rem; /* Was 0.9rem */
    margin-bottom: 6px; /* Was 8px */
}

.stat-value {
    font-size: 1.4rem; /* Was 1.5rem */
    font-weight: 600;
    color: var(--text-primary);
}

.status-title { /* For modal */
    font-size: 1.1rem;
    color: var(--text-secondary);
    margin-bottom: 16px;
    text-align: center;
}

.status-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(70px, 1fr)); /* Responsive status boxes */
    gap: 10px; /* Was 12px */
}

.status-box {
    padding: 10px 6px; /* Was 12px 8px */
    border-radius: 8px;
    text-align: center;
    transition: transform 0.2s, opacity 0.2s;
    color: var(--text-primary); /* Ensure text inside is white */
}
/* Apply status colors directly if not done by specific classes */
.status-box.watching, .status-box.reading { background-color: var(--status-watching); }
.status-box.completed { background-color: var(--status-completed); }
.status-box.on-hold { background-color: var(--status-on-hold); }
.status-box.dropped { background-color: var(--status-dropped); }
.status-box.planning { background-color: var(--status-planning); }


.status-box:hover {
    transform: translateY(-2px);
    opacity: 0.9;
}

.status-count {
    font-size: 1.2rem; /* Was 1.3rem */
    font-weight: 700;
    margin-bottom: 4px;
    color: inherit; /* Inherit from .status-box for white text */
}

.status-label {
    font-size: 0.75rem; /* Was 0.8rem */
    color: rgba(255, 255, 255, 0.85); /* Slightly more opaque */
}

.stats-divider { /* For modal between anime/manga sections */
    width: 1px;
    background-color: var(--background-secondary); /* Match other separators */
    margin: 0 16px; /* Provide spacing */
}


/* Mobile Styles */
@media (max-width: 768px) {
    body {
        padding: 8px;
    }

    .container {
        width: 100%;
        padding: 0 8px;
    }

    .section {
        padding: 20px 16px; /* Adjusted padding */
        margin-bottom: 20px;
    }
    
    /* Layout for Manual & Auto Backup & Latest Stats Overview */
    .section > div[style*="flex-wrap: wrap"] { /* Target the flex container for auto backup and latest stats */
        flex-direction: column !important;
        gap: 24px;
    }
     .section > div[style*="display: flex"] { /* General flex containers */
        flex-direction: column;
        gap: 15px;
    }


    h1, h2 {
        text-align: center;
    }
    h2 {
        font-size: 1.3rem;
        margin-bottom: 16px;
    }

    .input-group {
        flex-direction: column;
        gap: 12px;
        margin-bottom: 16px;
    }
     .input-group > div[style*="flex-direction: column"] { /* Inner flex for keep last/every */
        width: 100%;
    }
    .input-group > div[style*="flex-direction: column"] > div { /* Each line (Keep last X backups) */
        display: flex;
        justify-content: space-between; /* Space out elements */
        width: 100%;
    }


    input[type="text"], 
    input[type="number"] {
        width: 100% !important; /* Force full width */
        height: 44px;
        margin: 0;
    }


    button {
        width: 100%;
        height: 44px;
        padding: 0 16px;
        font-size: 1rem;
    }

    /* Previous Backups Table Styling for Mobile */
    .table {
        display: block; /* Make table behave like a block for overflow */
        overflow-x: auto; /* Allow horizontal scroll if content too wide */
    }

    .table thead {
        display: none; /* Hide table headers */
    }

    .table tbody, .table tr, .table td {
        display: block; /* Stack table elements */
        width: 100% !important; /* Force full width */
        box-sizing: border-box;
    }

    .table tr {
        background-color: var(--background-tertiary);
        border-radius: 8px;
        margin-bottom: 12px;
        padding: 12px; /* Padding inside each "card" */
        border: 1px solid #404040;
    }
    .table tr:last-child {
        margin-bottom: 0;
    }


    .table td {
        padding: 8px 0; /* Adjust padding */
        border-bottom: 1px solid var(--background-secondary); /* Separator inside card */
        text-align: right; /* Align value to the right */
        position: relative; /* For pseudo-element */
    }
    .table td:last-child {
        border-bottom: none;
    }

    .table td:before {
        content: attr(data-label);
        font-weight: 500;
        color: var(--text-secondary);
        position: absolute;
        left: 0;
        text-align: left;
        white-space: nowrap;
    }
    
    .table td.actions { /* Special handling for actions cell */
       padding-top: 10px;
    }
    .actions { /* Container for action buttons in table */
        display: flex;
        flex-direction: column; /* Stack buttons vertically on mobile */
        gap: 8px;
        margin-top: 8px;
         /* border-top: 1px solid var(--background-secondary); /* Separator above actions */
    }

    .actions button {
        width: 100%; /* Full width buttons */
        font-size: 0.9rem;
        padding: 10px 8px; /* Adjust padding */
        height: auto; /* Auto height */
        min-width: 0;
    }


    /* Logs Area */
    .logs {
        padding: 12px;
        font-size: 0.85rem;
        line-height: 1.4;
    }

    /* Modal Adjustments for Mobile */
    .modal-content {
        padding: 16px;
        margin: 5vh auto; /* Less margin */
        width: 95%; /* More width on mobile */
    }
    #statsContentContainer {
         max-height: 85vh; /* Allow more height on mobile */
    }


    /* Detailed Stats in Modal and on Main Page for Mobile */
    .detailed-stats-container {
        flex-direction: column;
        gap: 16px; /* Reduced gap */
        padding: 0;
    }

    .detailed-stats-section {
        padding: 16px; /* Reduced padding */
    }
    .detailed-stats-section h3 {
        font-size: 1.1rem;
        margin-bottom: 12px;
    }

    .main-stats {
        grid-template-columns: repeat(auto-fit, minmax(80px, 1fr)); /* Smaller minmax */
        gap: 10px;
        margin-bottom: 16px;
    }
    .stat-box {
        padding: 10px;
    }
    .stat-label { font-size: 0.75rem; margin-bottom: 4px; }
    .stat-value { font-size: 1.2rem; }


    .status-grid {
        grid-template-columns: repeat(auto-fit, minmax(60px, 1fr)) !important; /* Ensure it applies */
        gap: 6px !important; /* Ensure it applies */
    }
    .status-box {
        padding: 8px 4px;
    }
    .status-count { font-size: 1rem; }
    .status-label { font-size: 0.65rem; }

    .stats-divider { /* Hide divider on mobile as sections stack */
        display: none;
    }

    .github-footer {
        padding: 8px 10px;
        font-size: 0.8rem;
        text-align: center; /* Center on mobile */
        width: 100%;
        box-sizing: border-box;
        border-top-left-radius: 0; /* Full width */
        background-color: var(--background-secondary); /* Blend more */
    }
}

/* iPhone specific fine-tuning (if needed, often covered by max-width: 768px) */
@media (max-width: 430px) {
    .section {
        padding: 15px 10px;
    }
    h1 { font-size: 1.3rem !important; }
    h2 { font-size: 1.2rem; margin-bottom: 12px; }

    input[type="text"], input[type="number"], button {
        height: 40px;
        font-size: 0.95rem;
    }
    
    .table td:before {
        font-size: 0.9rem; /* Slightly smaller label on very small screens */
    }
    .actions button {
        font-size: 0.85rem;
    }
}
