import { api } from '../../shared/api.js';
import { appState } from '../../shared/state.js';
import { statusColor } from '../../shared/utils.js';

var cachedSuccessLogs = [];
var currentActiveModalType = null; 

// RGB Animated Header Clock & Date Updater
function updateHeaderClock() {
    const now = new Date();
    let timeString = now.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true });
    timeString = timeString.toUpperCase();
    const dateString = now.toLocaleDateString('en-IN', { day: '2-digit', month: 'long', year: 'numeric' });
    const clockEl = document.getElementById("headerClock");
    if(clockEl){
        clockEl.innerHTML = `
            <div class="clock-time">${timeString}</div>
            <div class="clock-date">${dateString}</div>
        `;
    }
}
setInterval(updateHeaderClock, 1000);
updateHeaderClock();

var currentFilter = "all";
var selectedDate = "";
var currentPage = 1;
var pageLimit = 50;
var paginationData = { page: 1, limit: 50, total: 0, total_pages: 1, start: 0, end: 0 };

var spyeyeFilter = "all";
var spyeyeSelectedDate = "";
var spyeyeCurrentPage = 1;
var spyeyePageLimit = 50;
var spyeyeSortOrder = "new_first";
var spyeyePaginationData = { page: 1, limit: 50, total: 0, total_pages: 1, start: 0, end: 0 };

function showPage(pageId, pageTitle){
    closeMenu();
    document.querySelectorAll(".app-section").forEach(el => {
        el.style.display = "none";
    });
    let target = document.getElementById(pageId + "Section");
    if(target){
        target.style.display = "block";
    }
    let titleEl = document.getElementById("lblNavTitle");
    if(titleEl){
        titleEl.innerHTML = pageTitle;
    }
}

function toggleProviderFields() {
    const provider = document.getElementById("providerInput").value;
    const serviceInput = document.getElementById("serviceIdInput");
    const standardFields = document.getElementById("standardServiceFields");
    const temporasmsFields = document.getElementById("temporasmsFields");
    const defaults = {"4sim":"1929","otpdoctor":"16311","tempotp":"1846","temporasms":"nwov"};
    // SERVICE ID is common to every provider. TemporaSMS uses the same field
    // for its API `service` parameter; it only gets an additional OPERATOR field.
    if (standardFields) standardFields.style.display = "grid";
    if (temporasmsFields) temporasmsFields.style.display = provider === "temporasms" ? "block" : "none";
    if (serviceInput) serviceInput.value = defaults[provider] || "";
    if (provider === "temporasms") {
        const op = document.getElementById("temporasmsOperatorInput");
        if (op && !op.value.trim()) op.value = "10";
    }
    startBalanceMonitor();
}

function openMenu() { document.getElementById("sidebar").classList.add("active"); document.getElementById("backdrop").style.display = "block"; }
function closeMenu() { document.getElementById("sidebar").classList.remove("active"); document.getElementById("backdrop").style.display = "none"; }

function openPopup(viewType, title) {
    currentActiveModalType = viewType;
    document.getElementById("popupTitle").innerHTML = title;
    const templateNode = document.getElementById("temp-" + viewType);
    document.getElementById("popupBody").innerHTML = templateNode ? templateNode.innerHTML : "";
    const popupModal = document.getElementById("popupModal");
    popupModal.style.display = "flex";
    // Always open the realtime popup at the top; never restore the previous worker scroll position.
    const popupBody = document.getElementById("popupBody");
    if (popupBody) popupBody.scrollTop = 0;
    requestAnimationFrame(() => { if (popupBody) popupBody.scrollTop = 0; });
    refreshDashboard(); 
}

function closePopup() {
    const popupBody = document.getElementById("popupBody");
    if (popupBody) popupBody.scrollTop = 0;
    document.getElementById("popupModal").style.display = "none";
    currentActiveModalType = null;
}
function closePopupOutside(e) { if (e.target.id === "popupModal") { closePopup(); } }


async function loadPrimaryGame() {
    const popup = document.getElementById('popupBody');
    const select = popup ? popup.querySelector('#primaryGameSelect') : null;
    const status = popup ? popup.querySelector('#primaryGameStatus') : null;
    if (!select) return;

    try {
        const response = await fetch('/api/primary-game', { cache: 'no-store' });
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.detail || data.message || 'Failed to load primary game');

        const available = Array.isArray(data.available) ? data.available : [];
        select.innerHTML = '';
        available.forEach(game => {
            const option = document.createElement('option');
            option.value = game;
            option.textContent = game;
            option.selected = game === data.primary_game;
            select.appendChild(option);
        });
        if (status) status.textContent = 'Saved: ' + data.primary_game;
    } catch (err) {
        if (status) status.innerHTML = '<span style="color:#ef4444;">✗ ' + (err.message || 'Load failed') + '</span>';
    }
}

async function savePrimaryGame() {
    const popup = document.getElementById('popupBody');
    const select = popup ? popup.querySelector('#primaryGameSelect') : null;
    const status = popup ? popup.querySelector('#primaryGameStatus') : null;
    if (!select || !select.value) return;

    try {
        const response = await fetch('/api/primary-game', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ game: select.value })
        });
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.detail || data.message || 'Save failed');

        if (status) status.innerHTML = '<span style="color:#34d399;">✓ Saved: ' + escapeGameSequenceText(data.primary_game) + '</span>';

        // Primary selection swaps with its existing sequence position, so
        // immediately reflect the server's updated sequence in the modal.
        if (Array.isArray(data.sequence)) {
            renderGameSequence(data.sequence, data.available || undefined);
            initGameSequenceControls();
        } else {
            await loadGameSequence();
        }
    } catch (err) {
        if (status) status.innerHTML = '<span style="color:#ef4444;">✗ ' + (err.message || 'Save failed') + '</span>';
    }
}

async function openGameSequenceModal() {
    closeMenu();
    openPopup('game-sequence', '🎮 Game Sequence');
    await Promise.all([loadGameSequence(), loadPrimaryGame()]);
}

async function loadGameSequence() {
    const list = document.getElementById('gameSequenceList');
    const status = document.getElementById('gameSequenceStatus');
    if (!list) return;
    list.innerHTML = '<div style="color:#64748b; text-align:center; padding:10px;">Loading game sequence...</div>';
    try {
        const response = await fetch('/api/game-sequence', { cache: 'no-store' });
        const data = await response.json();
        if (!data.success) throw new Error(data.message || 'Failed to load sequence');
        renderGameSequence(data.sequence || [], data.available || data.sequence || []);
        initGameSequenceControls();
        if (status) status.textContent = '';
    } catch (err) {
        list.innerHTML = '<div style="color:#ef4444; padding:10px;">Failed to load game sequence.</div>';
        if (status) status.textContent = err.message || String(err);
    }
}


function renderGameSequence(sequence, availableGames) {
    const list = document.getElementById('gameSequenceList');
    if (!list) return;

    const active = Array.isArray(sequence) ? sequence.filter(Boolean) : [];
    const available = Array.isArray(availableGames) && availableGames.length
        ? availableGames
        : active.slice();

    // Preserve saved order for enabled games, then append disabled games in
    // the configured GAME_MAP order.
    const activeSet = new Set(active);
    const ordered = [
        ...active.filter(game => available.includes(game)),
        ...available.filter(game => !activeSet.has(game))
    ];

    list.innerHTML = '';

    ordered.forEach((game, index) => {
        const enabled = activeSet.has(game);
        const row = document.createElement('div');
        row.dataset.game = game;
        row.dataset.enabled = enabled ? '1' : '0';
        row.className = 'game-sequence-row' + (enabled ? '' : ' game-sequence-disabled');
        row.style.cssText =
            'display:flex; align-items:center; gap:8px; padding:8px; ' +
            'background:' + (enabled ? '#0f172a' : '#0b1220') + '; ' +
            'border:1px solid ' + (enabled ? '#1e293b' : '#172033') + '; ' +
            'border-radius:7px; opacity:' + (enabled ? '1' : '.58') + ';';

        const numberText = enabled
            ? String(active.indexOf(game) + 1)
            : '—';

        row.innerHTML = `
            <label style="display:flex; align-items:center; justify-content:center; width:28px; margin:0; cursor:pointer;">
                <input type="checkbox"
                       class="game-sequence-enable"
                       ${enabled ? 'checked' : ''}
                       aria-label="Enable ${escapeGameSequenceText(game)}"
                       style="width:18px; height:18px; margin:0; accent-color:#22c55e;">
            </label>
            <span class="game-sequence-number"
                  style="width:26px; color:#64748b; font-weight:700; text-align:center;">
                ${numberText}
            </span>
            <span style="flex:1; color:#f8fafc; font-weight:700;">
                ${escapeGameSequenceText(game)}
            </span>
            <button type="button"
                    class="btn game-sequence-move"
                    data-direction="-1"
                    ${!enabled ? 'disabled' : ''}
                    style="width:42px; margin:0; padding:5px 9px;">
                ↑
            </button>
            <button type="button"
                    class="btn game-sequence-move"
                    data-direction="1"
                    ${!enabled ? 'disabled' : ''}
                    style="width:42px; margin:0; padding:5px 9px;">
                ↓
            </button>
        `;

        list.appendChild(row);
    });

    updateGameSequenceButtons();
}

function escapeGameSequenceText(value) {
    return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
}

function updateGameSequenceButtons() {
    const list = document.getElementById('gameSequenceList');
    if (!list) return;

    const rows = Array.from(list.querySelectorAll('.game-sequence-row'));
    const enabledRows = rows.filter(row => row.dataset.enabled === '1');

    rows.forEach(row => {
        const number = row.querySelector('.game-sequence-number');
        const enabled = row.dataset.enabled === '1';
        if (number) {
            number.textContent = enabled
                ? String(enabledRows.indexOf(row) + 1)
                : '—';
        }

        const up = row.querySelector('[data-direction="-1"]');
        const down = row.querySelector('[data-direction="1"]');

        if (up) up.disabled = !enabled || enabledRows.indexOf(row) === 0;
        if (down) down.disabled = !enabled ||
            enabledRows.indexOf(row) === enabledRows.length - 1;
    });
}

function setGameSequenceEnabled(row, enabled) {
    const list = document.getElementById('gameSequenceList');
    if (!list || !row) return;

    row.dataset.enabled = enabled ? '1' : '0';

    // Enabled rows stay at the top and preserve their relative order.
    // A newly enabled game is appended to the end of the enabled section.
    const rows = Array.from(list.querySelectorAll('.game-sequence-row'));
    const enabledRows = rows.filter(r => r.dataset.enabled === '1');
    const disabledRows = rows.filter(r => r.dataset.enabled !== '1');

    list.innerHTML = '';
    [...enabledRows, ...disabledRows].forEach(r => list.appendChild(r));

    rows.forEach(r => {
        const isEnabled = r.dataset.enabled === '1';
        r.style.opacity = isEnabled ? '1' : '.58';
        r.style.background = isEnabled ? '#0f172a' : '#0b1220';
        r.style.borderColor = isEnabled ? '#1e293b' : '#172033';
        const checkbox = r.querySelector('.game-sequence-enable');
        if (checkbox) checkbox.checked = isEnabled;
        const buttons = r.querySelectorAll('.game-sequence-move');
        buttons.forEach(btn => btn.disabled = !isEnabled);
    });

    updateGameSequenceButtons();
}

function moveGameSequence(index, direction) {
    const list = document.getElementById('gameSequenceList');
    if (!list) return;

    const rows = Array.from(list.querySelectorAll('.game-sequence-row'));
    const enabledRows = rows.filter(row => row.dataset.enabled === '1');
    const current = rows[index];

    if (!current || current.dataset.enabled !== '1') return;

    const activeIndex = enabledRows.indexOf(current);
    const targetIndex = activeIndex + Number(direction);

    if (targetIndex < 0 || targetIndex >= enabledRows.length) return;

    const targetRow = enabledRows[targetIndex];

    if (Number(direction) < 0) {
        list.insertBefore(current, targetRow);
    } else {
        list.insertBefore(current, targetRow.nextSibling);
    }

    // Keep disabled games below all enabled games.
    const nowRows = Array.from(list.querySelectorAll('.game-sequence-row'));
    const enabledNow = nowRows.filter(r => r.dataset.enabled === '1');
    const disabledNow = nowRows.filter(r => r.dataset.enabled !== '1');
    list.innerHTML = '';
    [...enabledNow, ...disabledNow].forEach(r => list.appendChild(r));

    updateGameSequenceButtons();
}

function initGameSequenceControls() {
    const list = document.getElementById('gameSequenceList');
    if (!list || list.dataset.controlsReady === '1') return;

    list.dataset.controlsReady = '1';

    list.addEventListener('click', function (event) {
        const button = event.target.closest('.game-sequence-move');
        if (!button || !list.contains(button)) return;

        event.preventDefault();
        event.stopPropagation();

        const row = button.closest('.game-sequence-row');
        if (!row) return;

        const rows = Array.from(list.querySelectorAll('.game-sequence-row'));
        const index = rows.indexOf(row);
        const direction = Number(button.dataset.direction);

        moveGameSequence(index, direction);
    });

    list.addEventListener('change', function (event) {
        const checkbox = event.target.closest('.game-sequence-enable');
        if (!checkbox || !list.contains(checkbox)) return;

        const row = checkbox.closest('.game-sequence-row');
        if (!row) return;

        setGameSequenceEnabled(row, checkbox.checked);
    });
}

async function saveGameSequence() {
    const list = document.getElementById('gameSequenceList');
    const status = document.getElementById('gameSequenceStatus');
    if (!list) return;

    const sequence = Array.from(list.querySelectorAll('.game-sequence-row'))
        .filter(row => row.dataset.enabled === '1')
        .map(row => row.dataset.game)
        .filter(Boolean);

    if (!sequence.length) {
        if (status) status.innerHTML = '<span style="color:#ef4444;">At least one game must be enabled.</span>';
        return;
    }

    try {
        const response = await fetch('/api/game-sequence', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sequence })
        });
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.detail || data.message || 'Save failed');

        renderGameSequence(data.sequence || sequence, data.available || undefined);
        if (status) status.innerHTML = '<span style="color:#34d399;">✓ Game sequence saved.</span>';
    } catch (err) {
        if (status) status.innerHTML = '<span style="color:#ef4444;">✗ ' + (err.message || 'Save failed') + '</span>';
    }
}

async function openSpyEyeAccountModal() {
    closeMenu();
    openPopup('account-info', '🔑 SPYEYE Account Information');
    const contentEl = document.getElementById("accountInfoContent");
    if (contentEl) contentEl.innerHTML = `<div style="color:#64748b;text-align:center;padding:18px;">Fetching account details...</div>`;
    try {
        const data = await api.getSpyEyeAccount();
        if (!data || Object.keys(data).length === 0) {
            if (contentEl) contentEl.innerHTML = `<div style="color:#ef4444;text-align:center;padding:18px;">No account info available.</div>`;
            return;
        }
        const esc = (v) => String(v ?? '-').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'","&#039;");
        const secretKeys = new Set(['accesscode','access_code','api_key','apikey','secret','secret_key','password','token','authorization']);
        const displayValue = (key,value) => {
            if (!secretKeys.has(String(key).toLowerCase())) return esc(value);
            const s=String(value ?? '');
            return s.length<=4 ? '••••••••' : esc(s.slice(0,2)+'••••••••'+s.slice(-2));
        };
        const apps=Array.isArray(data.apps)?data.apps:[];
        const entries=Object.entries(data).filter(([k])=>k!=='apps');
        let html=`<div class="premium-account-hero"><div class="premium-account-hero-title">🔑 SPYEYE Account Overview</div><div class="premium-account-hero-sub">Secure account summary · sensitive credentials are masked</div></div><div class="premium-account-grid">`;
        entries.forEach(([k,v])=>{
            const val=(v && typeof v==='object')?JSON.stringify(v):v;
            html+=`<div class="premium-account-item"><div class="premium-account-key">${esc(k)}</div><div class="premium-account-value">${displayValue(k,val)}</div></div>`;
        });
        html+=`</div>`;
        if(apps.length){
            html+=`<div class="premium-account-hero"><div class="premium-account-hero-title">📱 App Configuration</div><div class="premium-account-hero-sub">${apps.length} configured apps</div></div><div class="premium-apps">`;
            apps.forEach(app=>{
                if(!app || typeof app!=='object') return;
                html+=`<div class="premium-app-card"><div class="premium-app-name">${esc(app.app_name||app.name||'Unknown App')}</div>
                    <div class="premium-app-row"><span>Base charge</span><b>${esc(app.base_charge??'-')}</b></div>
                    <div class="premium-app-row"><span>Discount</span><b>${esc(app.discount_amount??'-')}</b></div>
                    <div class="premium-app-row"><span>Final charge</span><b>${esc(app.final_charge??'-')}</b></div></div>`;
            });
            html+=`</div>`;
        }
        if(contentEl) contentEl.innerHTML=html;
    } catch(e) {
        console.error(e);
        if(contentEl) contentEl.innerHTML=`<div style="color:#ef4444;text-align:center;padding:18px;">Failed to load account info.</div>`;
    }
}

async function openSpyEyeHistoryModal() {
    closeMenu();
    spyeyeCurrentPage = 1;
    openPopup('server-history', '📜 SPYEYE Server History');
    
    let filterSelect = document.getElementById("spyeyeDateFilterSelect");
    if (filterSelect) filterSelect.value = spyeyeFilter;
    
    let limitSelect = document.getElementById("spyeyePageLimitSelect");
    if (limitSelect) limitSelect.value = spyeyePageLimit;

    let sortSelect = document.getElementById("spyeyeSortOrderSelect");
    if (sortSelect) sortSelect.value = spyeyeSortOrder;

    let datePicker = document.getElementById("spyeyeDatePickerInput");
    if (datePicker) {
        datePicker.style.display = (spyeyeFilter === "date") ? "inline-block" : "none";
        if (spyeyeSelectedDate) datePicker.value = spyeyeSelectedDate;
    }

    await fetchSpyEyeHistory();
}

async function updateSpyEyeLiveSheetStatus() {
    const el = document.getElementById("spyeyeLiveSheetStatus");
    if (!el) return;
    try {
        const data = await api.getSpyEyeHistorySyncStatus();
        if (!data || data.success === false) {
            el.textContent = "🟠 LIVE SHEET SYNC: Status unavailable";
            return;
        }
        if (data.error) {
            el.textContent = `🔴 LIVE SHEET SYNC ERROR: ${data.error}`;
            el.style.color = "#f87171";
            return;
        }
        el.style.color = "#34d399";
        if (data.last_sync) {
            const t = new Date(data.last_sync);
            el.textContent = `🟢 LIVE SHEET SYNC: Active • Last sync ${t.toLocaleTimeString('en-IN', {hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:true})} • New: ${data.new_records ?? 0}`;
        } else {
            el.textContent = "🟢 LIVE SHEET SYNC: Active • Waiting for history data";
        }
    } catch (err) {
        el.textContent = "🟠 LIVE SHEET SYNC: Status unavailable";
    }
}

async function fetchSpyEyeHistory() {
    let tableBody = document.getElementById("serverHistoryTableBody");
    let cardsWrapper = document.getElementById("serverHistoryCardsWrapper");
    
    if (tableBody) {
        tableBody.innerHTML = `<tr><td colspan="9" style="color:#64748b; text-align:center;">Loading SPYEYE server history.....</td></tr>`;
    }
    if (cardsWrapper) {
        cardsWrapper.innerHTML = `<p style="color:#64748b; text-align:center; padding:15px;">Loading server history...</p>`;
    }
    
    try {
        let data = await api.getSpyEyeHistory(spyeyeFilter, spyeyeCurrentPage, spyeyePageLimit, spyeyeSelectedDate, spyeyeSortOrder);
        let rows = "";
        let cardsHtml = "";
        let historyList = data.history || [];
        
        if(historyList.length === 0) {
            rows = `<tr><td colspan="9" style="color:#64748b; text-align:center;">No server history records found.</td></tr>`;
            cardsHtml = `<p style="color:#64748b; text-align:center; padding:15px;">No server history records found.</p>`;
        } else {
            historyList.forEach((item) => {
                rows += `<tr>
                    <td class="spyeye-serial">${item.serial_no ?? '-'}</td>
                    <td style="color:#38bdf8;"><b>${item.app_name ?? '-'}</b></td>
                    <td><code>${item.deviceid ?? '-'}</code></td>
                    <td style="color:#34d399;"><b>${item.balance ?? '-'}</b></td>
                    <td><b>${item.phone ?? '-'}</b></td>
                    <td><code>${item.password ?? '-'}</code></td>
                    <td style="white-space:nowrap;">${item.date ?? '-'}</td>
                    <td>${item.uid ?? '-'}</td>
                    <td><code>${item.gid ?? '-'}</code></td>
                </tr>`;

                cardsHtml += `
                <div class="spyeye-history-card">
                    <div class="spyeye-history-title">
                        <span class="spyeye-history-serial">#${item.serial_no ?? '-'}</span>
                        <b>${item.app_name ?? '-'}</b>
                        <span class="spyeye-history-balance">${item.balance ?? '-'}</span>
                    </div>
                    <div class="spyeye-history-row">
                        <span class="spyeye-history-label">PHONE</span>
                        <span class="spyeye-history-value">+91 ${item.phone ?? '-'}</span>
                    </div>
                    <div class="spyeye-history-row">
                        <span class="spyeye-history-label">PASSWORD</span>
                        <span class="spyeye-history-value"><code>${item.password ?? '-'}</code></span>
                    </div>
                    <div class="spyeye-history-row">
                        <span class="spyeye-history-label">DEVICE ID</span>
                        <span class="spyeye-history-value"><code>${item.deviceid ?? '-'}</code></span>
                    </div>
                    <div class="spyeye-history-row">
                        <span class="spyeye-history-label">DATE</span>
                        <span class="spyeye-history-value">${item.date ?? '-'}</span>
                    </div>
                    <div class="spyeye-history-row">
                        <span class="spyeye-history-label">UID / GID</span>
                        <span class="spyeye-history-value">${item.uid ?? '-'} / <code>${item.gid ?? '-'}</code></span>
                    </div>
                </div>`;
            });
        }
        if (tableBody) tableBody.innerHTML = rows;
        if (cardsWrapper) cardsWrapper.innerHTML = cardsHtml;

        if (data.pagination) {
            spyeyePaginationData = data.pagination;
            renderSpyEyePagination();
        }
        updateSpyEyeLiveSheetStatus();
    } catch(e) {
        if (tableBody) tableBody.innerHTML = `<tr><td colspan="9" style="color:#ef4444; text-align:center;">Failed to load server history.</td></tr>`;
        if (cardsWrapper) cardsWrapper.innerHTML = `<p style="color:#ef4444; text-align:center; padding:15px;">Failed to load server history.</p>`;
    }
}

function changeSpyEyeDateFilter() {
    const selectEl = document.getElementById("spyeyeDateFilterSelect");
    if (!selectEl) return;
    const val = selectEl.value;
    const datePicker = document.getElementById("spyeyeDatePickerInput");
    if (val === "date") {
        if (datePicker) datePicker.style.display = "inline-block";
        spyeyeFilter = "date";
        if (datePicker && datePicker.value) {
            spyeyeSelectedDate = datePicker.value;
        }
    } else {
        if (datePicker) datePicker.style.display = "none";
        spyeyeSelectedDate = "";
        spyeyeFilter = val;
    }
    spyeyeCurrentPage = 1;
    fetchSpyEyeHistory();
}

function setSpyEyeQuickDateFilter(filterType) {
    const selectEl = document.getElementById("spyeyeDateFilterSelect");
    if (selectEl) selectEl.value = filterType;
    const datePicker = document.getElementById("spyeyeDatePickerInput");
    if (datePicker) datePicker.style.display = "none";
    spyeyeFilter = filterType;
    spyeyeSelectedDate = "";
    spyeyeCurrentPage = 1;
    fetchSpyEyeHistory();
}

function onSpyEyeDateSelected() {
    const datePicker = document.getElementById("spyeyeDatePickerInput");
    if (datePicker && datePicker.value) {
        spyeyeSelectedDate = datePicker.value;
        spyeyeFilter = "date";
        spyeyeCurrentPage = 1;
        fetchSpyEyeHistory();
    }
}

function changeSpyEyeSortOrder() {
    const selectEl = document.getElementById("spyeyeSortOrderSelect");
    if (!selectEl) return;
    spyeyeSortOrder = selectEl.value === "old_first" ? "old_first" : "new_first";
    spyeyeCurrentPage = 1;
    fetchSpyEyeHistory();
}

function changeSpyEyePageLimit() {
    const limitSelect = document.getElementById("spyeyePageLimitSelect");
    if (limitSelect) {
        spyeyePageLimit = parseInt(limitSelect.value);
    }
    spyeyeCurrentPage = 1;
    fetchSpyEyeHistory();
}

function loadSpyEyePage(page) {
    if (page < 1 || page > spyeyePaginationData.total_pages) return;
    spyeyeCurrentPage = page;
    fetchSpyEyeHistory();
}

function renderSpyEyePagination() {
    const infoEl = document.getElementById("spyeyePaginationInfo");
    const controlsEl = document.getElementById("spyeyePaginationControls");
    if (!infoEl || !controlsEl) return;

    infoEl.innerText = `Showing ${spyeyePaginationData.start}-${spyeyePaginationData.end} of ${spyeyePaginationData.total}`;

    let html = "";
    const totalPages = spyeyePaginationData.total_pages || 1;

    if (spyeyeCurrentPage > 1) {
        html += `<button class="btn" style="width:auto; padding:4px 8px; font-size:11px; background:#1e293b; margin:0;" onclick="loadSpyEyePage(${spyeyeCurrentPage - 1})">&lt; Previous</button>`;
    } else {
        html += `<button class="btn" style="width:auto; padding:4px 8px; font-size:11px; background:#0d1526; color:#475569; cursor:not-allowed; margin:0;" disabled>&lt; Previous</button>`;
    }

    let startP = Math.max(1, spyeyeCurrentPage - 2);
    let endP = Math.min(totalPages, startP + 4);
    if (endP - startP < 4) {
        startP = Math.max(1, endP - 4);
    }

    for (let i = startP; i <= endP; i++) {
        if (i === spyeyeCurrentPage) {
            html += `<button class="btn" style="width:auto; padding:4px 9px; font-size:11px; background:#0099ff; margin:0; font-weight:bold;">${i}</button>`;
        } else {
            html += `<button class="btn" style="width:auto; padding:4px 9px; font-size:11px; background:#1e293b; margin:0;" onclick="loadSpyEyePage(${i})">${i}</button>`;
        }
    }

    if (spyeyeCurrentPage < totalPages) {
        html += `<button class="btn" style="width:auto; padding:4px 8px; font-size:11px; background:#1e293b; margin:0;" onclick="loadSpyEyePage(${spyeyeCurrentPage + 1})">Next &gt;</button>`;
    } else {
        html += `<button class="btn" style="width:auto; padding:4px 8px; font-size:11px; background:#0d1526; color:#475569; cursor:not-allowed; margin:0;" disabled>Next &gt;</button>`;
    }

    controlsEl.innerHTML = html;
}

async function syncSpyEyeHistory(syncType) {
    const sheetKeyInput = document.getElementById("spyeyeSheetKeyInput");
    const statusEl = document.getElementById("spyeyeSyncStatus");
    
    if (!sheetKeyInput || !sheetKeyInput.value.trim()) {
        if (statusEl) {
            statusEl.style.display = "block";
            statusEl.style.color = "#ef4444";
            statusEl.innerText = "Error: Please enter a valid Google Sheet Key.";
        }
        return;
    }

    if (statusEl) {
        statusEl.style.display = "block";
        statusEl.style.color = "#38bdf8";
        statusEl.innerText = "Syncing with Google Sheet, please wait...";
    }

    try {
        let payload = {
            sheet_key: sheetKeyInput.value.trim(),
            sync_type: syncType,
            date_filter: spyeyeFilter,
            date: spyeyeSelectedDate,
            sort_order: spyeyeSortOrder,
            page: spyeyeCurrentPage,
            limit: spyeyePageLimit
        };

        let data = await api.syncSpyEye(payload);

        if (data && data.success) {
            if (statusEl) {
                statusEl.style.color = "#34d399";
                statusEl.innerText = `Success: ${data.message} (${data.synced_records} records synced)`;
            }
        } else {
            if (statusEl) {
                statusEl.style.color = "#ef4444";
                statusEl.innerText = `Sync Failed: ${data?.error || 'Unknown error'}`;
            }
        }
    } catch (e) {
        if (statusEl) {
            statusEl.style.color = "#ef4444";
            statusEl.innerText = `Sync Error: ${e.message}`;
        }
    }
}

async function openOtpHistoryModal() {
    closeMenu();
    openPopup('otp-history', '📩 Number-Wise OTP History');
    try {
        let data = await api.getGroupedOtp();
        let wrapper = document.getElementById("otpHistoryTablesWrapper");
        wrapper.innerHTML = "";
        
        let groupedData = data.grouped_otp_history || {};
        
        if (Object.keys(groupedData).length === 0) {
            wrapper.innerHTML = `<p style="color:#64748b; text-align:center; padding:15px;">No OTP history recorded yet.</p>`;
            return;
        }

        for (const [phone, records] of Object.entries(groupedData)) {
            let container = document.createElement("div");
            container.className = "number-group-container";

            let html = `
                <div class="number-group-header">📱 Mobile Number: +91 ${phone}</div>
                <div class="table-responsive">
                    <table>
                        <thead>
                            <tr>
                                <th>Game Name</th>
                                <th>Send OTP Time</th>
                                <th>OTP</th>
                                <th>OTP Received Time</th>
                                <th>OTP Verified Time</th>
                            </tr>
                        </thead>
                        <tbody>
            `;

            records.forEach(rec => {
                html += `
                    <tr>
                        <td style="color:#38bdf8;"><b>${rec.game_name}</b></td>
                        <td>${rec.send_otp_time}</td>
                        <td style="color:#34d399; font-size:14px; font-family:monospace;"><b>${rec.otp_code || '---'}</b></td>
                        <td>${rec.otp_received_time}</td>
                        <td>${rec.otp_verified_time}</td>
                    </tr>
                `;
            });

            html += `
                        </tbody>
                    </table>
                </div>
            `;
            container.innerHTML = html;
            wrapper.appendChild(container);
        }
    } catch(e) {
        document.getElementById("otpHistoryTablesWrapper").innerHTML = `<p style="color:#ef4444; text-align:center; padding:15px;">Failed to load OTP history.</p>`;
    }
}

function startEnginePipeline() {
    api.startEngine({
        target: document.getElementById('targetInput').value,
        threads: document.getElementById('threadInput').value,
        provider: document.getElementById('providerInput').value,
        service_id: document.getElementById('serviceIdInput').value,
        operator: document.getElementById('temporasmsOperatorInput')?.value || '10'
    });
}

function stopEnginePipeline() { api.stopEngine(); }

function setDashboardText(id, value) {
    const el = document.getElementById(id);
    if (el) el.innerText = value ?? 0;
    return el;
}

function renderCancelLogs(logs) {
    const rows = (Array.isArray(logs) ? logs : []).filter(item => {
        const status = String(item.status || '').toLowerCase();
        return status === 'released' || status.includes('cancel successful');
    });
    if (!rows.length) {
        return `<tr><td colspan="6" style="color:#64748b; text-align:center; padding:14px;">No confirmed cancellation logs yet.</td></tr>`;
    }
    return rows.map(item => {
        const status = String(item.status || 'Released');
        return `<tr>
            <td>${item.time || '-'}</td>
            <td style="font-family:monospace;">+91 ${item.phone || '-'}</td>
            <td style="color:#34d399; font-weight:700;">${status}</td>
            <td>${item.provider || '-'}</td>
            <td>${item.attempts ?? '-'}</td>
            <td style="max-width:420px; white-space:normal; word-break:break-word;">${item.response || '-'}</td>
        </tr>`;
    }).join('');
}

function renderCancelFailedLogs(logs, failedList) {
    let rows = Array.isArray(failedList) ? failedList : [];
    if (!rows.length) {
        rows = (Array.isArray(logs) ? logs : []).filter(item => String(item.status || '').toLowerCase().includes('failed'));
    }
    if (!rows.length) {
        return `<tr><td colspan="6" style="color:#64748b; text-align:center; padding:14px;">No failed cancellation attempts.</td></tr>`;
    }
    return rows.map(item => `<tr>
        <td>${item.time || '-'}</td>
        <td style="font-family:monospace;">+91 ${item.phone || '-'}</td>
        <td style="color:#fb7185; font-weight:700;">${item.status || 'Failed Completely'}</td>
        <td>${item.provider || '-'}</td>
        <td>${item.attempts ?? '-'}</td>
        <td style="max-width:420px; white-space:normal; word-break:break-word;">${item.response || '-'}</td>
    </tr>`).join('');
}

function renderSuccessOtpLogs(records) {
    const rows = Array.isArray(records) ? records : [];
    if (!rows.length) return `<tr><td colspan="6" style="color:#64748b; text-align:center; padding:14px;">Waiting for OTP received events...</td></tr>`;
    return rows.map(item => {
        const games = Array.isArray(item.games) ? item.games.join(', ') : (item.game || '-');
        const balances = item.game_balances && typeof item.game_balances === 'object'
            ? Object.entries(item.game_balances).map(([g,b]) => `${g}: ${b}`).join(' | ')
            : (item.balance || '-');
        const otpReceived = item.otp_received || item.otp_received_time || 'Received';
        const live = item.live ? `<span style="color:#60a5fa;font-weight:800;">● LIVE</span>` : '';
        return `<tr>
            <td>${item.time || item.otp_received_time || '-'}</td>
            <td style="font-family:monospace;">+91 ${item.phone || '-'}</td>
            <td>${games}</td>
            <td style="color:#34d399;font-weight:800;">${otpReceived}</td>
            <td style="color:#fbbf24;font-weight:800;">${balances}</td>
            <td>${live}</td>
        </tr>`;
    }).join('');
}

function updateDashboard(data) {
    setDashboardText("lblTarget", data.total_targeted);
    setDashboardText("lblThreads", data.total_thread_count || 0);
    setDashboardText("lblSecured", data.total_secured);
    setDashboardText("lblSuccess", data.success_otps);
    setDashboardText("lblAlready", data.already_registered);

    // HOME ENGINE SUMMARY — live semantic counters:
    // Success OTP = numbers for which an OTP was actually verified successfully.
    // Active Worker = currently active worker/number tasks (realtime counter).
    // Secure Num = numbers successfully secured/bought by the engine.
    setDashboardText("homeSuccessOtp", Number(data.success_otps || 0));
    setDashboardText("homeActiveWorker", Number(data.realtime_active_threads || 0));
    setDashboardText("homeSecureNum", Number(data.total_secured || 0));
    // Cancelled Logs card is driven by the actual successful release entries,
    // so it updates even if a provider-specific counter was not incremented.
    const cancelLogs = Array.isArray(data.cancel_logs) ? data.cancel_logs : [];
    const cancelledKeys = new Set(
        cancelLogs
            .filter(item => /^(Released|Cancelled)$/i.test(String(item.status || '')))
            .map(item => String(item.txn_id || item.phone || ''))
            .filter(Boolean)
    );
    setDashboardText("lblCancelled", cancelledKeys.size || Number(data.cancelled_orders || 0));
    setDashboardText("lblRealtimeActive", data.realtime_active_threads || 0);
    setDashboardText("lblRealtimeAlready", data.realtime_already_logs || 0);
    // Keep the counters semantically separate: confirmed releases belong to
    // Cancelled Logs; failed attempts belong to Cancel Failed. De-duplicate
    // failed entries by transaction/phone before showing the UI count.
    const failedEntries = Array.isArray(data.cancel_failed_numbers_list)
        ? data.cancel_failed_numbers_list
        : [];
    const failedKeys = new Set(failedEntries.map(item => String(item.txn_id || item.phone || '')));
    const failedCount = failedEntries.length ? failedKeys.size : Number(data.cancel_failed_logs || 0);
    setDashboardText("lblCancelFailed", failedCount);

    const delayedQueue = Array.isArray(data.delayed_cancel_queue) ? data.delayed_cancel_queue : [];
    const delayedKeys = new Set(delayedQueue.map(item => String(item.txn_id || item.phone || '')));
    const delayedCancelLabel = document.getElementById("lblDelayedCancel");
    if (delayedCancelLabel) delayedCancelLabel.innerText = delayedKeys.size;

    if(data.selected_provider === "otpdoctor") {
        document.getElementById("lblGatewayTitle").innerText = "🌐 OTPDOCTOR BAL";
    } else if(data.selected_provider === "tempotp") {
        document.getElementById("lblGatewayTitle").innerText = "🌐 TEMPOTP BAL";
    } else if(data.selected_provider === "temporasms") {
        document.getElementById("lblGatewayTitle").innerText = "🌐 TEMPORASMS BAL";
    } else {
        document.getElementById("lblGatewayTitle").innerText = "🌐 4SIM API BAL";
    }

    if(data.spyeye_balance) {
        document.getElementById("lblSpyEyeCredits").innerText = data.spyeye_balance;
        let homeSpy = document.getElementById("homeSpyEyeCredits");
        if(homeSpy) homeSpy.innerText = data.spyeye_balance;
    }

    if(data.foursim_balance) {
        let simCard = document.getElementById("homeGatewayBalance");
        if(simCard) simCard.innerText = data.foursim_balance;
    }

    if(data.otpdoctor_balance) {
        let otpCard = document.getElementById("homeOtpDoctorBalance");
        if(otpCard) otpCard.innerText = data.otpdoctor_balance;
        let otpAnalytics = document.getElementById("lblOtpDoctorAnalytics");
        if(otpAnalytics) otpAnalytics.innerText = data.otpdoctor_balance;
    }

    if(data.tempotp_balance) {
        let tempCard = document.getElementById("homeTempOtpBalance");
        if(tempCard) tempCard.innerText = data.tempotp_balance;
    }

    if(data.temporasms_balance) {
        let temporaCard = document.getElementById("homeTemporaSmsBalance");
        if(temporaCard) temporaCard.innerText = data.temporasms_balance;
    }

    if(data.gateway_balance) {
        document.getElementById("lblGatewayBalance").innerText = data.gateway_balance;
    }
    
    document.getElementById("engineState").innerHTML = data.system_status;
    document.getElementById('engineProgressBar').style.width = (data.progress || 0) + "%";
    document.getElementById('engineEta').innerHTML = "ETA : " + (data.eta || "---");

    if(data.health_check) {
        let netNode = document.getElementById("healthNet"), simNode = document.getElementById("healthSim"), spyNode = document.getElementById("healthSPYEYE");
        let modalNet = document.getElementById("modalHealthNet"), modalSim = document.getElementById("modalHealthSim"), modalSpy = document.getElementById("modalHealthSPYEYE");
        
        if(netNode) { netNode.innerText = data.health_check.internet; netNode.style.color = data.health_check.internet === "Connected" ? "#34d399" : "#ef4444"; }
        if(simNode) { simNode.innerText = data.health_check.gateway || "Connected"; simNode.style.color = "#34d399"; }
        if(spyNode) { spyNode.innerText = data.health_check.SPYEYE; spyNode.style.color = data.health_check.SPYEYE === "Connected" ? "#34d399" : "#ef4444"; }

        if(modalNet) { modalNet.innerText = data.health_check.internet; modalNet.style.color = data.health_check.internet === "Connected" ? "#34d399" : "#ef4444"; }
        if(modalSim) { modalSim.innerText = data.health_check.gateway || "Connected"; modalSim.style.color = "#34d399"; }
        if(modalSpy) { modalSpy.innerText = data.health_check.SPYEYE; modalSpy.style.color = data.health_check.SPYEYE === "Connected" ? "#34d399" : "#ef4444"; }
    }

    let summaryHTML = "";
    if (!data.registration_summary || Object.keys(data.registration_summary).length === 0) {
        summaryHTML = `<tr><td colspan="2" style="color:#64748b;">Waiting...</td></tr>`;
    } else {
        Object.entries(data.registration_summary).forEach(([game, count]) => {
            summaryHTML += `<tr><td>${game}</td><td>${count} Accounts</td></tr>`;
        });
    }
    let regSumBody = document.getElementById("registrationSummaryBody");
    if(regSumBody) regSumBody.innerHTML = summaryHTML;
    let modalRegSumBody = document.getElementById("modalRegistrationSummaryBody");
    if(modalRegSumBody) modalRegSumBody.innerHTML = summaryHTML;

    let analyticsRows = "";
    if (!data.game_analytics || Object.keys(data.game_analytics).length === 0) {
        analyticsRows = `<tr><td colspan="4" style="color:#64748b;">Awaiting context...</td></tr>`;
    } else {
        Object.keys(data.game_analytics).forEach(game => {
            let g = data.game_analytics[game];
            analyticsRows += `<tr><td>${game}</td><td style="color:#34d399;">${g.success}</td><td style="color:#fb923c;">${g.already || 0}</td><td style="color:#ef4444;">${g.failed}</td></tr>`;
        });
    }
    let analyticsBody = document.getElementById("analyticsBody");
    if(analyticsBody) analyticsBody.innerHTML = analyticsRows;
    let modalAnalyticsBody = document.getElementById("modalAnalyticsBody");
    if(modalAnalyticsBody) modalAnalyticsBody.innerHTML = analyticsRows;

    let errorLogRows = "";
    if (!data.error_logs || data.error_logs.length === 0) {
        errorLogRows = `<tr><td colspan="4" style="color:#64748b; text-align:center;">No error signatures captured.</td></tr>`;
    } else {
        data.error_logs.forEach(err => {
            errorLogRows += `<tr>
                <td>${err.time}</td>
                <td style="color:#f8fafc; font-family:monospace;">+91 ${err.phone}</td>
                <td style="color:#38bdf8;">${err.game}</td>
                <td><span class="badge error-bg">${err.reason}</span></td>
            </tr>`;
        });
    }
    let errorLogsTableBody = document.getElementById("errorLogsTableBody");
    if(errorLogsTableBody) errorLogsTableBody.innerHTML = errorLogRows;
    let modalErrorLogsTableBody = document.getElementById("modalErrorLogsTableBody");
    if(modalErrorLogsTableBody) modalErrorLogsTableBody.innerHTML = errorLogRows;

    // The server prepends newly completed records. Keep the newest OTP-received
    // records at the top of the Live repository on every refresh.
    const rawSuccessRecords = Array.isArray(data.success_records) ? data.success_records.slice() : [];
    // One live row per phone: merge duplicate completion snapshots and keep
    // the newest record with all known game balances.
    const successByPhone = new Map();
    rawSuccessRecords.forEach(item => {
        const key = String(item.phone || "");
        if (!key) return;
        const existing = successByPhone.get(key);
        if (!existing) {
            successByPhone.set(key, { ...item, games: Array.isArray(item.games) ? item.games.slice() : [], game_balances: { ...(item.game_balances || {}) } });
            return;
        }
        const merged = successByPhone.get(key);
        const games = Array.isArray(item.games) ? item.games : [];
        games.forEach(g => { if (!merged.games.includes(g)) merged.games.push(g); });
        Object.assign(merged.game_balances, item.game_balances || {});
        merged.success = Math.max(Number(merged.success || 0), Number(item.success || 0));
        merged.live = Boolean(merged.live || item.live);
        merged.time = String(item.time || '') > String(merged.time || '') ? item.time : merged.time;
        if (item.completion) merged.completion = item.completion;
    });
    const successRecords = Array.from(successByPhone.values());
    successRecords.sort((a, b) => String(b.time || '').localeCompare(String(a.time || '')));
    const successTableBody = document.getElementById("successTableBody");
    if (successTableBody) successTableBody.innerHTML = renderSuccessOtpLogs(successRecords);

    if (currentActiveModalType) {
        let activeWorkerCardsHTML = "";
        let modalStreamRows = "", modalAlreadyRows = "", modalCancelRows = "", modalDelayedCancelRows = "";
        let activeCount = 0;

        // OTP-received workers are surfaced first, then newest activity.
        const recentWorkers = Array.isArray(data.recent_activity)
            ? data.recent_activity.slice().sort((a, b) => {
                const aOtp = (a.otp_received === true || /otp received/i.test(String(a.status || '')) || /global route/i.test(String(a.status || ''))) ? 1 : 0;
                const bOtp = (b.otp_received === true || /otp received/i.test(String(b.status || '')) || /global route/i.test(String(b.status || ''))) ? 1 : 0;
                if (aOtp !== bOtp) return bOtp - aOtp;
                return String(b.time || '').localeCompare(String(a.time || ''));
            })
            : [];

        const escapeRT = (value) => String(value ?? '-').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
        const balanceValue = (value) => {
            const text = String(value ?? '₹0');
            return text.includes('₹') ? text : `₹${text}`;
        };
        const gameBalanceRows = (worker) => {
            const map = worker.game_balances && typeof worker.game_balances === 'object' ? worker.game_balances : {};
            const entries = Object.entries(map);
            if (!entries.length) {
                const game = worker.current_game || 'Current Game';
                return `<div class="rt-game-row"><span class="rt-game-dot"></span><span class="rt-game-name">${escapeRT(game)}</span><span class="rt-game-balance">${escapeRT(balanceValue(worker.balance || '₹0'))}</span></div>`;
            }
            return entries.map(([game, bal], index) => {
                const raw = String(bal ?? '₹0');
                const n = parseFloat(raw.replace(/[^0-9.-]/g, ''));
                const cls = Number.isFinite(n) && n <= 0 ? ' bad' : (index === 2 ? ' warn' : '');
                return `<div class="rt-game-row"><span class="rt-game-dot${cls}"></span><span class="rt-game-name">${escapeRT(game)}</span><span class="rt-game-balance">${escapeRT(balanceValue(bal))}</span></div>`;
            }).join('');
        };

        recentWorkers.forEach((worker) => {
            if(worker.status && (worker.status.includes("Release Hold") || worker.status.includes("Terminating Assets"))) {
                modalAlreadyRows += `<tr><td>+91 ${worker.phone}</td><td><span class="badge success-bg" style="background:rgba(251,146,60,0.15); color:#fb923c; border:1px solid #fb923c;">${worker.status}</span>${worker.queue_remaining != null ? ` <b style="color:#fbbf24;">⏱ ${worker.queue_remaining}s</b>` : ""}</td></tr>`;
            }
            else if(worker.status && (worker.status.includes("Cool-off") || worker.status.includes("Released"))) {
                modalCancelRows += `<tr><td>+91 ${worker.phone}</td><td><span class="badge success-bg" style="background:rgba(239,68,68,0.15); color:#ef4444; border:1px solid #ef4444;">${worker.status}</span></td></tr>`;
            }
            else {
                activeCount++;
                const timeout = worker.otp_timeout_remaining != null ? `${worker.otp_timeout_remaining}s` : '--';
                const status = escapeRT(worker.status || 'Running');
                const statusLower = String(worker.status || '').toLowerCase();
                const started = worker.started_at || worker.start_time || worker.started || worker.time || '--';
                const progress = Math.max(0, Math.min(100, Number(worker.progress || 0)));
                const statusIsOtp = /otp waiting/i.test(statusLower);
                const statusClass = statusIsOtp ? 'rt-status-value' : '';
                modalStreamRows += `<tr><td>${activeCount}</td><td>+91 ${escapeRT(worker.phone)}</td><td style="color:${statusColor(worker.status)}">${status}</td><td>${escapeRT(balanceValue(worker.balance || '₹0'))}</td></tr>`;

                activeWorkerCardsHTML += `
                <article class="rt-worker">
                    <div class="rt-worker-head">
                        <div class="rt-worker-name"><span class="rt-worker-num">${activeCount}</span>WORKER ${activeCount}<span class="rt-running"><span class="rt-live-dot"></span>Running</span></div>
                        <div class="rt-started">Started: ${escapeRT(started)}</div>
                        <div class="rt-menu">⋮</div>
                    </div>
                    <div class="rt-worker-body">
                        <div class="rt-panel">
                            <div class="rt-detail-row"><span class="rt-detail-label">☎ <span>Number</span></span><span class="rt-detail-value">+91 ${escapeRT(worker.phone)}</span></div>
                            <div class="rt-detail-row"><span class="rt-detail-label">🎮 <span>Game</span></span><span class="rt-detail-value">${escapeRT(worker.current_game || '--')}</span></div>
                            <div class="rt-detail-row"><span class="rt-detail-label">〽 <span>Status</span></span><span class="rt-detail-value ${statusClass}">${status}</span></div>
                            <div class="rt-detail-row"><span class="rt-detail-label">⟳ <span>Retry</span></span><span class="rt-detail-value">${escapeRT(worker.retry || 1)}/5</span></div>
                            <div class="rt-detail-row"><span class="rt-detail-label">◷ <span>OTP Timeout</span></span><span class="rt-detail-value">${escapeRT(timeout)}</span></div>
                            <div class="rt-detail-row"><span class="rt-detail-label">▣ <span>Wallet</span></span><span class="rt-detail-value">${escapeRT(balanceValue(worker.balance || '₹0'))}</span></div>
                            <div class="rt-progress"><i style="width:${progress}%"></i></div>
                        </div>
                        <div class="rt-panel">
                            <div class="rt-panel-title"><span>🎮 Game Balances (Live)</span><span class="live">● Live &nbsp;⟳</span></div>
                            ${gameBalanceRows(worker)}
                        </div>
                    </div>
                </article>`;
            }
        });

        (data.delayed_cancel_queue || []).forEach((item) => {
            modalDelayedCancelRows += `<tr><td>+91 ${item.phone}</td><td><b style="color:#fbbf24;">⏱ ${item.remaining}s</b></td><td>${item.status || "Waiting"}</td></tr>`;
        });

        if (currentActiveModalType === 'stream') {
            const modalRoot = document.getElementById('popupBody');
            const targetCardsNode = modalRoot ? modalRoot.querySelector("#workerCards") : null;
            const targetTableNode = modalRoot ? modalRoot.querySelector('#streamTableBody') : null;
            if(targetCardsNode) targetCardsNode.innerHTML = activeWorkerCardsHTML || `<p class="rt-empty">No active parallel tasks running.</p>`;
            if(targetTableNode) targetTableNode.innerHTML = modalStreamRows || `<tr><td colspan="4" style="color:#64748b;">No active threads.</td></tr>`;
            const activeText = `${activeCount} Active`;
            const totalThreads = Number(data.total_thread_count || 0);
            const activeEl = modalRoot ? modalRoot.querySelector('#rtActiveWorkers') : null;
            const activeStatEl = modalRoot ? modalRoot.querySelector('#rtStatActive') : null;
            const threadsEl = modalRoot ? modalRoot.querySelector('#rtStatThreads') : null;
            const statusEl = modalRoot ? modalRoot.querySelector('#rtStatStatus') : null;
            const otpEl = modalRoot ? modalRoot.querySelector('#rtStatOtp') : null;
            if(activeEl) activeEl.textContent = activeText;
            const successCount = Number(data.success_otps || 0);
            if(activeStatEl) activeStatEl.textContent = Number.isFinite(successCount) ? successCount : 0;
            if(threadsEl) threadsEl.textContent = `${activeCount}/${totalThreads}`;
            if(statusEl) statusEl.textContent = data.system_status || 'Online';
            if(otpEl) {
                const waits = recentWorkers.map(w => Number(w.otp_timeout_remaining)).filter(n => Number.isFinite(n) && n >= 0);
                otpEl.textContent = waits.length ? `${Math.round(waits.reduce((a,b)=>a+b,0)/waits.length)}s` : '--';
            }
        } else if (currentActiveModalType === 'already') {
            const targetAlreadyNode = document.getElementById('alreadyTableBody');
            if(targetAlreadyNode) targetAlreadyNode.innerHTML = modalAlreadyRows || `<tr><td colspan="2" style="color:#64748b;">Queue empty.</td></tr>`;
        } else if (currentActiveModalType === 'cancel') {
            const targetCancelNode = document.getElementById('cancelTableBody');
            if (targetCancelNode) targetCancelNode.innerHTML = renderCancelLogs(data.cancel_logs);
        } else if (currentActiveModalType === 'cancel-failed') {
            const targetFailedNode = document.getElementById('cancelFailedTableBody');
            if (targetFailedNode) targetFailedNode.innerHTML = renderCancelFailedLogs(data.cancel_logs, data.cancel_failed_numbers_list);
        } else if (currentActiveModalType === 'delayed-cancel') {
            const targetDelayedNode = document.getElementById('delayedCancelTableBody');
            if(targetDelayedNode) targetDelayedNode.innerHTML = modalDelayedCancelRows || `<tr><td colspan="3" style="color:#64748b;">Delayed cancel queue empty.</td></tr>`;
        }
    }

    let timeline = "";
    if (!data.activity_timeline || data.activity_timeline.length === 0) {
        timeline = `<div style="color:#64748b; padding:10px; text-align:center;">Waiting...</div>`;
    } else {
        data.activity_timeline.forEach(item => {
            timeline += `<div class="timeline-item"><b>${item.time}</b><br>+91 ${item.phone}<br><span style="color:#38bdf8;">${item.stage}</span></div>`;
        });
    }
    let timelineBody = document.getElementById("timelineBody");
    if(timelineBody) timelineBody.innerHTML = timeline;
    let modalTimelineBody = document.getElementById("modalTimelineBody");
    if(modalTimelineBody) modalTimelineBody.innerHTML = timeline;
}

async function refreshDashboard() {
    try {
        let data = await api.getLogs(currentFilter, currentPage, pageLimit, selectedDate);
        if (data) {
            appState.setState(data);
            updateDashboard(data);
        }
    } catch(e) {}
}

async function fetch4SimBalance() {
    try {
        let data = await api.get4SimBalance();
        if(data && data.foursim_balance) {
            let el = document.getElementById("homeGatewayBalance");
            if(el) el.innerText = data.foursim_balance;
            let provider = document.getElementById("providerInput").value;
            if(provider === "4sim") {
                let lbl = document.getElementById("lblGatewayBalance");
                if(lbl) lbl.innerText = data.foursim_balance;
            }
        }
    } catch(e) {}
}

async function fetchOtpDoctorBalance() {
    try {
        let data = await api.getOtpDoctorBalance();
        if(data && data.otpdoctor_balance) {
            let el = document.getElementById("homeOtpDoctorBalance");
            if(el) el.innerText = data.otpdoctor_balance;
            let provider = document.getElementById("providerInput").value;
            if(provider === "otpdoctor") {
                let lbl = document.getElementById("lblGatewayBalance");
                if(lbl) lbl.innerText = data.otpdoctor_balance;
            }
        }
    } catch(e) {}
}

async function fetchTempOtpBalance() {
    try {
        let data = await api.getTempOtpBalance();
        if(data && data.tempotp_balance) {
            let el = document.getElementById("homeTempOtpBalance");
            if(el) el.innerText = data.tempotp_balance;
            let provider = document.getElementById("providerInput").value;
            if(provider === "tempotp") {
                let lbl = document.getElementById("lblGatewayBalance");
                if(lbl) lbl.innerText = data.tempotp_balance;
            }
        }
    } catch(e) {}
}

async function fetchTemporaSmsBalance() {
    try {
        let data = await api.getTemporaSmsBalance();
        if(data && data.temporasms_balance) {
            let el = document.getElementById("homeTemporaSmsBalance");
            if(el) el.innerText = data.temporasms_balance;
            let provider = document.getElementById("providerInput").value;
            if(provider === "temporasms") {
                let lbl = document.getElementById("lblGatewayBalance");
                if(lbl) lbl.innerText = data.temporasms_balance;
            }
        }
    } catch(e) {}
}

var activeBalanceTimer = null;
var inactiveBalanceTimer = null;
var dashboardSyncTimer = null;

function startBalanceMonitor() {
    if(activeBalanceTimer) clearInterval(activeBalanceTimer);
    if(inactiveBalanceTimer) clearInterval(inactiveBalanceTimer);
    if(dashboardSyncTimer) clearInterval(dashboardSyncTimer);

    let providerEl = document.getElementById("providerInput");
    let activeProvider = providerEl ? providerEl.value : "4sim";

    refreshDashboard();
    fetch4SimBalance();
    fetchOtpDoctorBalance();
    fetchTempOtpBalance();
    fetchTemporaSmsBalance();

    if(activeProvider === "otpdoctor") {
        activeBalanceTimer = setInterval(fetchOtpDoctorBalance, 10000);
    } else if(activeProvider === "tempotp") {
        activeBalanceTimer = setInterval(fetchTempOtpBalance, 10000);
    } else if(activeProvider === "temporasms") {
        activeBalanceTimer = setInterval(fetchTemporaSmsBalance, 10000);
    } else {
        activeBalanceTimer = setInterval(fetch4SimBalance, 10000);
    }

    dashboardSyncTimer = setInterval(refreshDashboard, 2000);
}

// Start mobile on Home.
showPage('home', '🏠 Home');
startBalanceMonitor();

// Expose functions globally for HTML inline onclick handlers
window.openMenu = openMenu;
window.closeMenu = closeMenu;
window.showPage = showPage;
window.openPopup = openPopup;
window.closePopup = closePopup;
window.closePopupOutside = closePopupOutside;
window.openSpyEyeAccountModal = openSpyEyeAccountModal;
window.openSpyEyeHistoryModal = openSpyEyeHistoryModal;
window.openGameSequenceModal = openGameSequenceModal;
window.savePrimaryGame = savePrimaryGame;
window.saveGameSequence = saveGameSequence;
window.changeSpyEyeDateFilter = changeSpyEyeDateFilter;
window.setSpyEyeQuickDateFilter = setSpyEyeQuickDateFilter;
window.onSpyEyeDateSelected = onSpyEyeDateSelected;
window.changeSpyEyePageLimit = changeSpyEyePageLimit;
window.changeSpyEyeSortOrder = changeSpyEyeSortOrder;
window.loadSpyEyePage = loadSpyEyePage;
window.syncSpyEyeHistory = syncSpyEyeHistory;
window.openOtpHistoryModal = openOtpHistoryModal;
window.startEnginePipeline = startEnginePipeline;
window.stopEnginePipeline = stopEnginePipeline;
window.toggleProviderFields = toggleProviderFields;

document.addEventListener('click', function(event) {
    const button = event.target.closest('[data-action="save-primary-game"]');
    if (!button) return;
    event.preventDefault();
    savePrimaryGame();
});

