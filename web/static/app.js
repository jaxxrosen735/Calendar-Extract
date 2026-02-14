
let currentViewDate = new Date();
let calendarEvents = [];
let isDragging = false;

document.addEventListener('DOMContentLoaded', () => {
    // checkCdnStatus();
    loadCalendarData();
    setupDraggable();
    
    // Poll system status every 30 seconds
    setInterval(updateSystemStatus, 30000);
    updateSystemStatus();
});

/**
 * CDN DIAGNOSTIC
 * Checks if ICAL was loaded from CDN or local fallback

function checkCdnStatus() {
    const indicator = document.createElement('div');
    indicator.style.fontSize = '9px';
    indicator.style.padding = '2px';
    indicator.style.textAlign = 'right';
    
    // Logic: If the script tag with the CDN URL didn't load, 
    // we know because we checked 'typeof ICAL' in the HTML fallback.
    const isLocal = document.querySelector('script[src*="static/ical.min.js"]');
    
    if (isLocal) {
        indicator.innerHTML = 'LIB_STATUS: <span style="color: yellow;">[LOCAL_FALLBACK]</span>';
        addLog("CDN_SRI_FAIL: Using local ical.js", "yellow");
    } else {
        indicator.innerHTML = 'LIB_STATUS: <span style="color: #00ff00;">[CDN_ACTIVE]</span>';
        addLog("CDN_SRI_SUCCESS: High-speed assets linked", "#00ff00");
    }
    document.querySelector('.window').appendChild(indicator);
}*/

/**
 * CALENDAR ENGINE
 */
async function loadCalendarData() {
    try {
        const response = await fetch('/calendar'); 
        if (!response.ok) throw new Error(`HTTP_ERR_${response.status}`);
        
        const rawData = await response.text();

        // FIX: Use ICAL.parse() but wrap it in an ICAL.Component
        // Some versions of ical.js require this specific sequence for raw strings:
        const jcalData = ICAL.parse(rawData);
        const comp = new ICAL.Component(jcalData);
        
        // Ensure we are looking at the VCALENDAR level
        calendarEvents = comp.getAllSubcomponents('vevent').map(vevent => {
            const event = new ICAL.Event(vevent);
            return {
                title: event.summary,
                start: event.startDate ? event.startDate.toJSDate() : new Date(),
                time: event.startDate ? event.startDate.toJSDate().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '',
                description: event.description || null,
                location: event.location || "No location provided.",
                //end: event.endDate ? event.endDate.toJSDate() : null,
                end: event.endDate ? event.endDate.toJSDate().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '',
                uid: event.uid || '',
            };
        });
        
        renderCalendar();
        addLog("CALENDAR_SYNC_COMPLETE", "cyan");
    } catch (e) {
        // If the error persists, it's likely the .ics file is empty or malformed
        addLog(`PARSING_ERROR: ${e.message}`, "red");
        console.error("Full Error Context:", e);
    }
}

function renderCalendar() {
    const table = document.getElementById('calendar-table');
    const monthDisplay = document.getElementById('current-month-display');
    const year = currentViewDate.getFullYear();
    const month = currentViewDate.getMonth();

    monthDisplay.innerText = currentViewDate.toLocaleString('default', { month: 'long', year: 'numeric' }).toUpperCase();
    
    // Windows 95 Table Headers
    let html = '<tr bgcolor="#c0c0c0"><th>S</th><th>M</th><th>T</th><th>W</th><th>T</th><th>F</th><th>S</th></tr><tr>';
    
    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();

    // Fill empty days for start of month
    for (let i = 0; i < firstDay; i++) {
        html += '<td bgcolor="#dfdfdf"></td>';
    }

    for (let day = 1; day <= daysInMonth; day++) {
        if ((firstDay + day - 1) % 7 === 0 && day !== 1) {
            html += '</tr><tr>';
        }
        
        const isToday = new Date().toDateString() === new Date(year, month, day).toDateString();
        const dayEvents = calendarEvents.filter(e => 
            e.start.getFullYear() === year && 
            e.start.getMonth() === month && 
            e.start.getDate() === day
        );

        const eventHtml = dayEvents.map(e => {
            const safeTitle = e.title.replace(/'/g, "\\'");
            const safeDesc = (e.description ? e.description : '').replace(/'/g, "\\'").replace(/\n/g, " ");
            const safeLocation = e.location.replace(/'/g, "\\'");
            const safeTime = e.time.replace(/'/g, "\\'");
            const safeEnd = e.end ? e.end.toLocaleString() : '';
            // Pass all details to popup
            return `<div class="event-link" onclick="showEventDetails('${safeTitle}', '${safeDesc}', '${safeLocation}', '${safeTime}', '${safeEnd}')">${e.time ? e.time + ' ' : ''}${e.title}</div>`;
        }).join('');
        html += `<td class="${isToday ? 'today' : ''}"><b>${day}</b>${eventHtml}</td>`;
    }
    
    html += '</tr>';
    table.innerHTML = html;
}

function changeMonth(dir) {
    currentViewDate.setMonth(currentViewDate.getMonth() + dir);
    renderCalendar();
}

/**
 * MODAL & UI LOGIC
 */
function showEventDetails(title, description, location, time, end) {
    document.getElementById('modal-title').innerText = title;
    let details = `Time: ${time}\nLocation: ${location}\n`;
    if (end) details += `Ends: ${end}\n`;
    if (description && description.trim() !== "") {
        details += `\n${description}`;
    }
    document.getElementById('modal-desc').innerText = details;
    document.getElementById('event-modal').style.display = 'block';
    document.getElementById('modal-overlay').style.display = 'block';
    addLog(`VIEWING_EVENT: ${title.substring(0,15)}...`, "white");
}

function closeModal() {
    document.getElementById('event-modal').style.display = 'none';
    document.getElementById('modal-overlay').style.display = 'none';
}

function setupDraggable() {
    const modal = document.getElementById('event-modal');
    const titleBar = modal.querySelector('.title-bar');

    titleBar.onmousedown = (e) => {
        isDragging = true;
        let offsetX = e.clientX - modal.getBoundingClientRect().left;
        let offsetY = e.clientY - modal.getBoundingClientRect().top;

        document.onmousemove = (ev) => {
            if (isDragging) {
                modal.style.left = ev.clientX - offsetX + (modal.offsetWidth / 2) + 'px';
                modal.style.top = ev.clientY - offsetY + (modal.offsetHeight / 2) + 'px';
                modal.style.transform = 'translate(-50%, -50%)'; // Keep it centered relative to mouse
            }
        };
    };
    document.onmouseup = () => isDragging = false;
}

/**
 * SYSTEM STATUS POLLING
 */
async function updateSystemStatus() {
    const statusEl = document.getElementById('sched-status');
    try {
        const response = await fetch('/status');
        const data = await response.json();
        statusEl.innerText = data.status;
        statusEl.style.color = (data.status === "ACTIVE") ? "green" : "red";
    } catch (e) {
        statusEl.innerHTML = '<span class="blink" style="color:red">OFFLINE</span>';
    }
}

async function triggerScrape() {
    addLog("MANUAL_SCRAPE_REQUESTED", "yellow");
    try {
        await fetch('/trigger', { method: 'POST' });
        addLog("SCRAPE_SIGNAL_SENT_SUCCESS", "cyan");
    } catch (e) {
        addLog("SCRAPE_SIGNAL_FAILURE", "red");
    }
}

function addLog(message, color = "#00ff00") {
    const logEl = document.getElementById('logs');
    const entry = document.createElement('div');
    entry.innerHTML = `[${new Date().toLocaleTimeString()}] <span style="color:${color}">${message}</span>`;
    logEl.prepend(entry);
}