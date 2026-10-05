/* ═══════════════════════════════════════════════════════════════════
   LifeSync — App Logic (Amazon-Themed Professional UI)
   ═══════════════════════════════════════════════════════════════════ */

const API_BASE = 'http://localhost:8000/api';

// ── Auth Guard ──────────────────────────────────────────────────────
const storedUser = localStorage.getItem('lifesync_user');
const authToken = localStorage.getItem('lifesync_token');
if (!storedUser || !authToken) {
    window.location.href = '/auth.html';
}
const currentUser = storedUser ? JSON.parse(storedUser) : {};
let sessionId = currentUser.user_id || 'session_' + Math.random().toString(36).substring(2, 9);
let messageCount = 0;

// ── DOM Elements ────────────────────────────────────────────────────
const chatContainer = document.getElementById('chat-container');
const chatForm = document.getElementById('chat-form');
const messageInput = document.getElementById('message-input');
const contextWidgets = document.getElementById('context-widgets');
const welcomeState = document.getElementById('welcome-state');

// ── Initialize ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {

    // Quick Action Cards
    document.querySelectorAll('.quick-action-card').forEach(card => {
        card.addEventListener('click', () => {
            const query = card.getAttribute('data-query');
            sendMessage(query);
        });
    });

    // Sidebar Navigation Tabs
    const sidebarItems = document.querySelectorAll('.sidebar-item');
    sidebarItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            sidebarItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');

            const tab = item.getAttribute('data-tab');
            const queries = {
                'assistant': 'Hello, LifeSync!',
                'schedule': 'Show my schedule for today',
                'tasks': 'List my pending tasks',
                'fitness': 'What is my fitness status?',
                'shopping': 'Do I need to reorder anything?',
                'memory': 'What do you remember about me?',
                'analytics': 'Give me a weekly productivity summary',
            };
            if (queries[tab]) sendMessage(queries[tab]);
        });
    });

    // Sidebar Toggle
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const sidebar = document.getElementById('sidebar');
    sidebarToggle.addEventListener('click', () => {
        sidebar.classList.toggle('collapsed');
    });

    // Context Panel Toggle
    const ctxToggle = document.getElementById('btn-toggle-context');
    const ctxPanel = document.getElementById('context-panel');
    ctxToggle.addEventListener('click', () => {
        ctxPanel.classList.toggle('collapsed');
        const icon = ctxToggle.querySelector('i');
        icon.classList.toggle('fa-chevron-right');
        icon.classList.toggle('fa-chevron-left');
    });

    // Notifications Panel
    const notifBtn = document.getElementById('btn-notifications');
    const notifPanel = document.getElementById('notification-panel');
    const notifClose = document.getElementById('notif-close');
    notifBtn.addEventListener('click', () => {
        notifPanel.classList.toggle('hidden');
        // Clear badge
        const badge = notifBtn.querySelector('.notif-badge');
        if (badge) badge.style.display = 'none';
    });
    notifClose.addEventListener('click', () => notifPanel.classList.add('hidden'));

    // Settings Modal
    const settingsBtn = document.getElementById('btn-settings');
    const settingsModal = document.getElementById('settings-modal');
    const settingsClose = document.getElementById('settings-close');
    settingsBtn.addEventListener('click', () => {
        document.getElementById('session-display').textContent = sessionId;
        settingsModal.classList.remove('hidden');
    });
    settingsClose.addEventListener('click', () => settingsModal.classList.add('hidden'));
    settingsModal.addEventListener('click', (e) => {
        if (e.target === settingsModal) settingsModal.classList.add('hidden');
    });

    // New Session Button
    document.getElementById('btn-new-session').addEventListener('click', () => {
        sessionId = 'session_' + Math.random().toString(36).substring(2, 9);
        document.getElementById('session-display').textContent = sessionId;
        chatContainer.innerHTML = '';
        chatContainer.appendChild(welcomeState);
        welcomeState.style.display = 'flex';
        messageCount = 0;
        addSystemMessage('New session started. Memory cleared.');
    });

    // Dark Mode Toggle (cosmetic — already dark by default)
    const darkModeBtn = document.getElementById('btn-dark-mode');
    darkModeBtn.addEventListener('click', () => {
        const icon = darkModeBtn.querySelector('i');
        if (icon.classList.contains('fa-moon')) {
            icon.classList.replace('fa-moon', 'fa-sun');
            document.documentElement.style.setProperty('--bg-primary', '#F7F8FA');
            document.documentElement.style.setProperty('--bg-secondary', '#FFFFFF');
            document.documentElement.style.setProperty('--bg-card', '#F0F2F5');
            document.documentElement.style.setProperty('--bg-card-hover', '#E8EAED');
            document.documentElement.style.setProperty('--bg-elevated', '#FFFFFF');
            document.documentElement.style.setProperty('--bg-input', '#F0F2F5');
            document.documentElement.style.setProperty('--text-primary', '#0F1111');
            document.documentElement.style.setProperty('--text-secondary', '#565959');
            document.documentElement.style.setProperty('--text-muted', '#9AA0A6');
            document.documentElement.style.setProperty('--border-subtle', 'rgba(0,0,0,0.08)');
            document.documentElement.style.setProperty('--border-medium', 'rgba(0,0,0,0.12)');
        } else {
            icon.classList.replace('fa-sun', 'fa-moon');
            document.documentElement.style.setProperty('--bg-primary', '#0F1111');
            document.documentElement.style.setProperty('--bg-secondary', '#1A1E23');
            document.documentElement.style.setProperty('--bg-card', '#1F2937');
            document.documentElement.style.setProperty('--bg-card-hover', '#283141');
            document.documentElement.style.setProperty('--bg-elevated', '#232F3E');
            document.documentElement.style.setProperty('--bg-input', '#1A1E23');
            document.documentElement.style.setProperty('--text-primary', '#E8EAED');
            document.documentElement.style.setProperty('--text-secondary', '#9AA0A6');
            document.documentElement.style.setProperty('--text-muted', '#6B7280');
            document.documentElement.style.setProperty('--border-subtle', 'rgba(255,255,255,0.08)');
            document.documentElement.style.setProperty('--border-medium', 'rgba(255,255,255,0.12)');
        }
    });

    // Voice Button
    const voiceBtn = document.getElementById('btn-voice');
    voiceBtn.addEventListener('click', () => {
        voiceBtn.classList.add('listening');
        messageInput.placeholder = '🎤 Listening...';
        messageInput.disabled = true;
        setTimeout(() => {
            voiceBtn.classList.remove('listening');
            messageInput.disabled = false;
            messageInput.placeholder = 'Ask LifeSync anything...';
            messageInput.value = 'What should I focus on this week?';
            messageInput.focus();
        }, 2000);
    });

    // Attach Button (cosmetic)
    document.getElementById('btn-attach').addEventListener('click', () => {
        addSystemMessage('📎 File attachment is a simulated feature for the hackathon demo.');
    });

    // User menu
    const userMenu = document.getElementById('user-menu-toggle');
    userMenu.innerHTML = `<img src="${currentUser.avatar_url || 'https://ui-avatars.com/api/?name=User&background=FF9900&color=fff'}" alt="User" title="${currentUser.name} (${currentUser.role})">`;
    userMenu.addEventListener('click', () => {
        if (confirm(`Logout of ${currentUser.name}'s account?`)) {
            localStorage.removeItem('lifesync_token');
            localStorage.removeItem('lifesync_user');
            window.location.href = '/auth.html';
        }
    });

    // AI Engine select
    document.getElementById('ai-engine-select').addEventListener('change', (e) => {
        const engine = e.target.value;
        addSystemMessage(`🔄 AI Engine switched to: ${engine === 'bedrock' ? 'AWS Bedrock (Claude)' : 'Google Gemini'}`);
    });

    // Initial context load
    updateContextPanel();
});

// ── Form Submission ─────────────────────────────────────────────────
chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = messageInput.value.trim();
    if (!text) return;

    // Hide welcome state
    if (welcomeState) welcomeState.style.display = 'none';

    messageInput.value = '';
    messageCount++;

    addMessage(text, 'user');
    const typingId = showTypingIndicator();

    try {
        const response = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, session_id: sessionId })
        });

        const data = await response.json();
        removeMessage(typingId);
        addMessage(data.text, 'assistant', data.cards);

        // Proactive suggestions
        if (data.proactive_suggestions && data.proactive_suggestions.length > 0) {
            setTimeout(() => {
                const sugg = data.proactive_suggestions[0];
                addMessage(sugg.text, 'assistant', [{
                    title: '💡 Proactive Insight',
                    type: 'action_card',
                    body: '',
                    actions: sugg.actions
                }]);
            }, 1500);
        }

        updateContextPanel();

    } catch (error) {
        removeMessage(typingId);
        addMessage('⚠️ Unable to connect to the server. Please check that the FastAPI backend is running on port 8000.', 'assistant');
        console.error(error);
    }
});

// ── Add Message ─────────────────────────────────────────────────────
function addMessage(text, role, cards = []) {
    const template = document.getElementById('message-template');
    const clone = template.content.cloneNode(true);
    const msgDiv = clone.querySelector('.message');

    msgDiv.classList.add(role);
    msgDiv.id = 'msg_' + Date.now();

    // Format text
    let formatted = text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');

    clone.querySelector('.message-bubble').innerHTML = formatted;

    // Timestamp
    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    clone.querySelector('.message-timestamp').textContent = timeStr;

    // Cards
    if (cards && cards.length > 0) {
        const cardsContainer = clone.querySelector('.message-cards');
        cards.forEach(card => cardsContainer.appendChild(renderCard(card)));
    }

    chatContainer.appendChild(clone);
    scrollToBottom();
    return msgDiv.id;
}

function addSystemMessage(text) {
    const div = document.createElement('div');
    div.className = 'message assistant fade-in';
    div.id = 'sys_' + Date.now();
    div.innerHTML = `
        <div class="message-avatar"></div>
        <div class="message-content">
            <div class="message-bubble" style="font-size: 13px; opacity: 0.8;">${text}</div>
            <div class="message-timestamp">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
        </div>
    `;
    if (welcomeState) welcomeState.style.display = 'none';
    chatContainer.appendChild(div);
    scrollToBottom();
}

// ── Render Card ─────────────────────────────────────────────────────
function renderCard(card) {
    const div = document.createElement('div');
    div.className = 'rich-card fade-in';

    let html = `<h4>${card.title}</h4>`;

    if (card.body) {
        html += `<div class="card-body">${card.body.replace(/\n/g, '<br>')}</div>`;
    }

    if (card.progress !== undefined) {
        html += `
            <div style="margin-top: 10px; height: 5px; background: rgba(255,255,255,0.08); border-radius: 3px; overflow: hidden;">
                <div style="height: 100%; width: ${card.progress}%; background: var(--amazon-green); transition: width 1s ease;"></div>
            </div>
            <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">${card.progress}% complete</div>
        `;
    }

    if (card.actions && card.actions.length > 0) {
        html += `<div class="card-actions">`;
        card.actions.forEach((btn, idx) => {
            const cls = idx === 0 ? 'primary' : '';
            html += `<button class="card-btn ${cls}" onclick="handleCardAction('${btn.value}')">${btn.label}</button>`;
        });
        html += `</div>`;
    }

    div.innerHTML = html;
    return div;
}

// ── Typing Indicator ────────────────────────────────────────────────
function showTypingIndicator() {
    const id = 'typing_' + Date.now();
    const html = `
        <div class="message assistant fade-in" id="${id}">
            <div class="message-avatar"></div>
            <div class="message-content">
                <div class="message-bubble" style="padding: 12px 18px;">
                    <div class="typing-indicator">
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                    </div>
                </div>
            </div>
        </div>
    `;
    chatContainer.insertAdjacentHTML('beforeend', html);
    scrollToBottom();
    return id;
}

function removeMessage(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function scrollToBottom() {
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// ── Global Handlers ─────────────────────────────────────────────────
window.handleCardAction = (actionValue) => {
    sendMessage(`Do: ${actionValue}`);
};

function sendMessage(text) {
    messageInput.value = text;
    chatForm.dispatchEvent(new Event('submit'));
}

// ── Context Panel ───────────────────────────────────────────────────
async function updateContextPanel() {
    try {
        const response = await fetch(`${API_BASE}/memory/${sessionId}`);
        if (!response.ok) return;
        const data = await response.json();

        let html = '';

        // Profile
        if (data.preferences) {
            html += `<div class="ctx-widget fade-in">
                <h4>👤 Profile</h4>
                <div class="ctx-row"><span>Name</span><span class="ctx-val">${data.preferences.name || 'Unknown'}</span></div>
                <div class="ctx-row"><span>Fitness Goal</span><span class="ctx-val">${data.preferences.fitness_goal || 'None'}</span></div>
                <div class="ctx-row"><span>Diet</span><span class="ctx-val">${data.preferences.diet_preference || 'N/A'}</span></div>
            </div>`;
        }

        // Patterns
        if (data.patterns && data.patterns.morning_routine) {
            html += `<div class="ctx-widget fade-in">
                <h4>🔄 Patterns</h4>
                <div class="ctx-row"><span>Coffee</span><span class="ctx-val">${data.patterns.morning_routine.coffee_time}</span></div>
                <div class="ctx-row"><span>Peak Focus</span><span class="ctx-val">${data.patterns.productivity_peak.best_hours}</span></div>
            </div>`;
        }

        // Memory Graph
        html += `<div class="ctx-widget fade-in">
            <h4>🧠 Memory Graph</h4>
            <div class="ctx-row"><span>Interactions</span><span class="ctx-val">${data.interactions_count || 0}</span></div>
            <div class="ctx-row"><span>Status</span><span class="ctx-val" style="color: var(--amazon-green);">Syncing</span></div>
        </div>`;

        // AWS Status
        html += `<div class="ctx-widget fade-in">
            <h4><i class="fa-brands fa-aws" style="color:var(--amazon-orange);"></i> AWS Status</h4>
            <div class="ctx-row"><span>Bedrock</span><span class="ctx-val" style="color:var(--amazon-green);">Active</span></div>
            <div class="ctx-row"><span>MCP Spec</span><span class="ctx-val">2025-11-25</span></div>
            <div class="ctx-row"><span>Transport</span><span class="ctx-val">Streamable HTTP</span></div>
        </div>`;

        contextWidgets.innerHTML = html;

    } catch (e) {
        console.error('Context panel error:', e);
    }
}
