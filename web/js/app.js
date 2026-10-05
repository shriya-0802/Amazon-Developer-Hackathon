/* ═══════════════════════════════════════════════════════════════════
   LifeSync — App Logic (Amazon-Themed Professional UI)
   Complete rewrite — all buttons functional, real-time reminders,
   interactive calendar, Amazon shopping, mood tracker, focus timer,
   daily streak, quick notes
   ═══════════════════════════════════════════════════════════════════ */

const API_BASE = 'http://localhost:8000/api';

// ── Auth Guard ──────────────────────────────────────────────────────
const storedUser = localStorage.getItem('lifesync_user');
const authToken = localStorage.getItem('lifesync_token');
if (!storedUser || !authToken) {
    window.location.href = '/auth.html';
}
const currentUser = storedUser ? JSON.parse(storedUser) : {};
const userId = currentUser.user_id || 'default';
let sessionId = userId;
let messageCount = 0;
let reminderInterval = null;
let shownReminderIds = new Set();

// ── DOM Elements ────────────────────────────────────────────────────
const chatContainer = document.getElementById('chat-container');
const chatForm = document.getElementById('chat-form');
const messageInput = document.getElementById('message-input');
const contextWidgets = document.getElementById('context-widgets');
const welcomeState = document.getElementById('welcome-state');

// ── Focus Timer State ───────────────────────────────────────────────
let focusTimerInterval = null;
let focusTimeLeft = 25 * 60; // seconds
let focusTotalTime = 25 * 60;
let focusRunning = false;

// ── Calendar State ──────────────────────────────────────────────────
let calCurrentMonth = new Date().getMonth();
let calCurrentYear = new Date().getFullYear();
let calSelectedDate = null;
let calEvents = [];

// ── Notes State ─────────────────────────────────────────────────────
let quickNotes = JSON.parse(localStorage.getItem('lifesync_notes') || '[]');

// ── Mood State ──────────────────────────────────────────────────────
let moodHistory = JSON.parse(localStorage.getItem('lifesync_mood_history') || '[]');
let selectedMood = null;

// ── Streak State ────────────────────────────────────────────────────
let dailyStreak = JSON.parse(localStorage.getItem('lifesync_streak') || '{"count":0,"lastDate":""}');

// ── Initialize ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {

    // ── Update streak ──
    updateStreak();

    // ── Voice Input (Mic) ──
    document.getElementById('btn-voice')?.addEventListener('click', () => {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            alert('Your browser does not support Speech Recognition.');
            return;
        }
        const recognition = new SpeechRecognition();
        recognition.lang = 'en-US';
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;
        
        const btn = document.getElementById('btn-voice');
        const icon = btn.querySelector('i');
        icon.classList.remove('fa-microphone');
        icon.classList.add('fa-spinner', 'fa-spin');
        
        recognition.start();

        recognition.onresult = (event) => {
            const speechResult = event.results[0][0].transcript;
            document.getElementById('message-input').value = speechResult;
            sendMessage(speechResult);
        };

        recognition.onspeechend = () => {
            recognition.stop();
        };

        recognition.onend = () => {
            icon.classList.remove('fa-spinner', 'fa-spin');
            icon.classList.add('fa-microphone');
        };

        recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            alert('Speech recognition failed: ' + event.error);
            icon.classList.remove('fa-spinner', 'fa-spin');
            icon.classList.add('fa-microphone');
        };
    });

    // ── System Buttons ──
    document.getElementById('btn-reset-db')?.addEventListener('click', async () => {
        if (!confirm('Are you sure you want to reset all your data? This cannot be undone.')) return;
        try {
            await fetch(`${API_BASE}/users/${userId}/reset`, { method: 'POST' });
            localStorage.removeItem('lifesync_notes');
            localStorage.removeItem('lifesync_mood_history');
            localStorage.removeItem('lifesync_streak');
            alert('Data reset successfully! Refreshing...');
            window.location.reload();
        } catch (e) {
            console.error('Failed to reset DB:', e);
            alert('Failed to reset data.');
        }
    });

    document.getElementById('btn-delete-account')?.addEventListener('click', async () => {
        if (!confirm('Are you sure you want to completely delete your account?')) return;
        try {
            await fetch(`${API_BASE}/users/${userId}`, { method: 'DELETE' });
            localStorage.clear();
            alert('Account deleted. Redirecting to login...');
            window.location.href = '/auth.html';
        } catch (e) {
            console.error('Failed to delete account:', e);
            alert('Failed to delete account.');
        }
    });

    // ── Request browser notification permission ──
    if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission();
    }

    // ── Quick Action Cards ──────────────────────────────────────────
    document.querySelectorAll('.quick-action-card').forEach(card => {
        card.addEventListener('click', () => {
            const query = card.getAttribute('data-query');
            sendMessage(query);
        });
    });

    // ── Sidebar Navigation ──────────────────────────────────────────
    const sidebarItems = document.querySelectorAll('.sidebar-item');
    sidebarItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            sidebarItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');

            const tab = item.getAttribute('data-tab');

            // Calendar tab opens the calendar modal
            if (tab === 'schedule') {
                openCalendarModal();
                return;
            }

            // Shopping opens the Amazon modal
            if (tab === 'shopping') {
                openShoppingModal();
                return;
            }

            // Mood tracker modal
            if (tab === 'mood') {
                openMoodModal();
                return;
            }

            // Quick Notes modal
            if (tab === 'notes') {
                openNotesModal();
                return;
            }

            const queries = {
                'assistant': 'Hello, LifeSync!',
                'tasks': 'List my pending tasks',
                'fitness': 'What is my fitness status?',
                'memory': 'What do you remember about me?',
                'analytics': 'Give me a weekly productivity summary',
            };
            if (queries[tab]) sendMessage(queries[tab]);
        });
    });

    // ── Sidebar Toggle ──────────────────────────────────────────────
    document.getElementById('sidebar-toggle').addEventListener('click', () => {
        document.getElementById('sidebar').classList.toggle('collapsed');
    });

    // ── Context Panel Toggle ────────────────────────────────────────
    const ctxToggle = document.getElementById('btn-toggle-context');
    const ctxPanel = document.getElementById('context-panel');
    ctxToggle.addEventListener('click', () => {
        ctxPanel.classList.toggle('collapsed');
        const icon = ctxToggle.querySelector('i');
        icon.classList.toggle('fa-chevron-right');
        icon.classList.toggle('fa-chevron-left');
    });

    // ── Notifications Panel ─────────────────────────────────────────
    const notifBtn = document.getElementById('btn-notifications');
    const notifPanel = document.getElementById('notification-panel');
    const notifClose = document.getElementById('notif-close');
    notifBtn.addEventListener('click', () => {
        notifPanel.classList.toggle('hidden');
        const badge = notifBtn.querySelector('.notif-badge');
        if (badge) badge.style.display = 'none';
    });
    notifClose.addEventListener('click', () => notifPanel.classList.add('hidden'));

    // ── Settings Modal ──────────────────────────────────────────────
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

    // ── Browser Notifications Toggle ────────────────────────────────
    const browserNotifToggle = document.getElementById('toggle-browser-notif');
    if (browserNotifToggle) {
        browserNotifToggle.addEventListener('change', () => {
            if (browserNotifToggle.checked) {
                Notification.requestPermission().then(perm => {
                    if (perm !== 'granted') {
                        browserNotifToggle.checked = false;
                        addSystemMessage('⚠️ Browser notification permission denied. Please enable it in your browser settings.');
                    }
                });
            }
        });
    }

    // ── New Session ─────────────────────────────────────────────────
    document.getElementById('btn-new-session').addEventListener('click', () => {
        sessionId = 'session_' + Math.random().toString(36).substring(2, 9);
        document.getElementById('session-display').textContent = sessionId;
        chatContainer.innerHTML = '';
        chatContainer.appendChild(welcomeState);
        welcomeState.style.display = 'flex';
        messageCount = 0;
        addSystemMessage('New session started. Memory cleared.');
    });

    // ── Onboarding Modal (Save & Continue) ──────────────────────────
    const onboardingModal = document.getElementById('onboarding-modal');
    if (onboardingModal) {
        const isNewUser = localStorage.getItem('lifesync_is_new_user');
        if (isNewUser === 'true') {
            onboardingModal.classList.remove('hidden');
        }

        const onboardingClose = document.getElementById('onboarding-close');
        if (onboardingClose) {
            onboardingClose.addEventListener('click', () => {
                onboardingModal.classList.add('hidden');
                localStorage.removeItem('lifesync_is_new_user');
            });
        }

        // Onboarding mood buttons
        document.querySelectorAll('#onboarding-mood-selector .mood-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('#onboarding-mood-selector .mood-btn').forEach(b => {
                    b.style.borderColor = 'var(--border-medium)';
                    b.style.background = 'var(--bg-input)';
                });
                btn.style.borderColor = 'var(--amazon-orange)';
                btn.style.background = 'rgba(255,153,0,0.1)';
                selectedMood = btn.getAttribute('data-mood');
            });
        });

        const onboardingForm = document.getElementById('onboarding-form');
        if (onboardingForm) {
            onboardingForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const btn = onboardingForm.querySelector('button[type="submit"]');
                btn.innerHTML = '<span class="spinner" style="display:inline-block;width:16px;height:16px;border:2px solid transparent;border-top-color:#000;border-radius:50%;animation:spin 0.6s linear infinite;margin-right:6px;vertical-align:middle;"></span> Setting up...';
                btn.disabled = true;

                const title = document.getElementById('onboarding-event-title').value.trim();
                const time = document.getElementById('onboarding-event-time').value;
                const notes = document.getElementById('onboarding-notes').value.trim();

                try {
                    // Save event to the calendar
                    if (title) {
                        await fetch(`${API_BASE}/events/${userId}`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                title: title,
                                start_time: time || new Date().toISOString(),
                                description: notes || '',
                                event_type: 'personal'
                            })
                        });
                    }

                    // Store notes as memory
                    if (notes) {
                        await fetch(`${API_BASE}/chat`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                message: `Remember: ${notes}`,
                                session_id: sessionId
                            })
                        });
                    }

                    // Save mood
                    if (selectedMood) {
                        saveMood(selectedMood, 'Onboarding mood');
                    }
                } catch (err) {
                    console.error('Onboarding save error:', err);
                }

                // Always close modal and show confirmation
                onboardingModal.classList.add('hidden');
                localStorage.removeItem('lifesync_is_new_user');
                btn.innerHTML = '<i class="fa-solid fa-bolt"></i> Activate LifeSync';
                btn.disabled = false;

                if (welcomeState) welcomeState.style.display = 'none';
                addSystemMessage(`🔔 <strong>Alexa+ Activated:</strong> Welcome to LifeSync! I've saved your event "${title || 'your event'}". I'll remind you proactively when the time approaches — just like Alexa!`);

                if (selectedMood) {
                    addSystemMessage(`😊 Mood logged: <strong>${selectedMood}</strong>. I'll track your emotional patterns over time.`);
                }

                // Update context panel
                updateContextPanel();
            });
        }
    }

    // ── Calendar Modal ──────────────────────────────────────────────
    initCalendarModal();

    // ── Focus Timer ─────────────────────────────────────────────────
    initFocusTimer();

    // ── Shopping Modal ──────────────────────────────────────────────
    initShoppingModal();

    // ── Mood Modal ──────────────────────────────────────────────────
    initMoodModal();

    // ── Notes Modal ─────────────────────────────────────────────────
    initNotesModal();

    // ── Dark Mode ───────────────────────────────────────────────────
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

    // ── Voice Button ────────────────────────────────────────────────
    document.getElementById('btn-voice').addEventListener('click', () => {
        const voiceBtn = document.getElementById('btn-voice');
        voiceBtn.classList.add('listening');
        messageInput.placeholder = '🎤 Listening...';
        messageInput.disabled = true;
        setTimeout(() => {
            voiceBtn.classList.remove('listening');
            messageInput.disabled = false;
            messageInput.placeholder = 'Ask LifeSync anything...';
            messageInput.value = 'What should I focus on today?';
            messageInput.focus();
        }, 2000);
    });

    // ── Attach Button ───────────────────────────────────────────────
    document.getElementById('btn-attach').addEventListener('click', () => {
        addSystemMessage('📎 File attachment is a simulated feature for the hackathon demo.');
    });

    // ── User Menu (Logout) ──────────────────────────────────────────
    const userMenu = document.getElementById('user-menu-toggle');
    userMenu.innerHTML = `<img src="${currentUser.avatar_url || 'https://ui-avatars.com/api/?name=User&background=FF9900&color=fff'}" alt="User" title="${currentUser.name || 'User'} (${currentUser.role || 'user'})">`;
    userMenu.addEventListener('click', () => {
        if (confirm(`Logout of ${currentUser.name || 'your'} account?`)) {
            localStorage.removeItem('lifesync_token');
            localStorage.removeItem('lifesync_user');
            localStorage.removeItem('lifesync_is_new_user');
            window.location.href = '/auth.html';
        }
    });

    // ── AI Engine Select ────────────────────────────────────────────
    document.getElementById('ai-engine-select').addEventListener('change', (e) => {
        const engine = e.target.value;
        addSystemMessage(`🔄 AI Engine switched to: ${engine === 'bedrock' ? 'AWS Bedrock (Claude)' : 'Google Gemini'}`);
    });

    // ── Alexa Toast Dismiss ─────────────────────────────────────────
    document.getElementById('alexa-toast-dismiss').addEventListener('click', () => {
        document.getElementById('alexa-toast').classList.add('hidden');
    });

    // ── Initial Load ────────────────────────────────────────────────
    updateContextPanel();
    startReminderPolling();
});

// ── Chat Form Submission ────────────────────────────────────────────
chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = messageInput.value.trim();
    if (!text) return;

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

        if (data.trigger_notification) {
            setTimeout(() => { showSimulatedDeviceNotification('Email', 'Fitness time blocked successfully.'); }, 1000);
            setTimeout(() => { showSimulatedDeviceNotification('SMS', 'Fitness time blocked successfully.'); }, 2500);
            setTimeout(() => { 
                showSimulatedDeviceNotification('Voice', 'Incoming call from LifeSync...'); 
                if ('speechSynthesis' in window) {
                    const utterance = new SpeechSynthesisUtterance("This is LifeSync. Your fitness time has been blocked successfully.");
                    window.speechSynthesis.speak(utterance);
                }
            }, 4000);
        }

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
        addMessage('⚠️ Unable to connect to the server. Make sure the FastAPI backend is running on port 8000.', 'assistant');
        console.error('Chat error:', error);
    }
});

// ── Add Message ─────────────────────────────────────────────────────
function addMessage(text, role, cards = []) {
    const template = document.getElementById('message-template');
    const clone = template.content.cloneNode(true);
    const msgDiv = clone.querySelector('.message');
    msgDiv.classList.add(role);
    msgDiv.id = 'msg_' + Date.now();

    let formatted = text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');
    clone.querySelector('.message-bubble').innerHTML = formatted;

    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    clone.querySelector('.message-timestamp').textContent = timeStr;

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
            <div class="message-bubble" style="font-size: 13px; opacity: 0.9;">${text}</div>
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

    if (card.image) {
        html += `<img src="${card.image}" style="width:100%; height:auto; border-radius:8px; margin-bottom:12px; display:block;">`;
    }

    let isFitnessCard = card.title && card.title.includes("Today's Fitness");
    let uniqueId = Math.random().toString(36).substr(2, 9);
    let bodyId = isFitnessCard ? "live-fitness-body-" + uniqueId : "";
    let progBarId = isFitnessCard ? "live-fitness-bar-" + uniqueId : "";
    let progTextId = isFitnessCard ? "live-fitness-text-" + uniqueId : "";

    if (card.body) {
        html += `<div class="card-body" ${isFitnessCard ? 'id="'+bodyId+'"' : ''}>${card.body.replace(/\n/g, '<br>')}</div>`;
    }

    if (card.price) {
        html += `<div style="font-size: 16px; font-weight: bold; color: var(--amazon-orange); margin-top: 5px;">$${card.price}</div>`;
    }

    if (card.progress !== undefined) {
        html += `
            <div style="margin-top: 10px; height: 5px; background: rgba(255,255,255,0.08); border-radius: 3px; overflow: hidden;">
                <div ${isFitnessCard ? 'id="'+progBarId+'"' : ''} style="height: 100%; width: ${card.progress}%; background: var(--amazon-green); transition: width 1s ease;"></div>
            </div>
            <div ${isFitnessCard ? 'id="'+progTextId+'"' : ''} style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">${card.progress}% complete</div>
        `;
    }

    if (isFitnessCard) {
        // Start a live ticking simulation for this card
        setTimeout(() => {
            if (window.fitnessLiveInterval) clearInterval(window.fitnessLiveInterval);
            let parts = card.body.split('/');
            let currentSteps = parseInt(parts[0].replace(/,/g, '').replace(/steps/g, '').trim());
            let goalSteps = parts.length > 1 ? parseInt(parts[1].replace(/steps/g, '').replace(/,/g, '').trim()) : 10000;
            
            // Initialize real device motion pedometer if not already done
            if (typeof window.sensorSteps === 'undefined') {
                window.sensorSteps = 0;
                window.lastShake = 0;
                
                window.addEventListener('devicemotion', (event) => {
                    if (!event.accelerationIncludingGravity) return;
                    let acc = event.accelerationIncludingGravity;
                    // Calculate total acceleration magnitude
                    let magnitude = Math.sqrt(acc.x * acc.x + acc.y * acc.y + acc.z * acc.z);
                    // Standard gravity is ~9.8, so anything over 12 implies a strong shake/step
                    if (magnitude > 12) {
                        let now = Date.now();
                        // Debounce step count (max 2 steps per second)
                        if (now - window.lastShake > 400) {
                            window.sensorSteps += 1;
                            window.lastShake = now;
                            console.log("Real step detected from sensor! Total extra:", window.sensorSteps);
                        }
                    }
                });
            }
            
            // Start the UI update loop
            let baseSteps = currentSteps;
            let lastSensorSteps = window.sensorSteps;
            
            window.fitnessLiveInterval = setInterval(() => {
                let elBody = document.getElementById(bodyId);
                let elBar = document.getElementById(progBarId);
                let elText = document.getElementById(progTextId);
                
                if (elBody && currentSteps < goalSteps) {
                    // Update steps based on ACTUAL sensor shakes, or fallback to +1 if we just want a demo tick
                    // If sensor has registered new steps, use those! Otherwise, just add a simulated +1 occasionally for demo.
                    let newSensorSteps = window.sensorSteps - lastSensorSteps;
                    
                    if (newSensorSteps > 0) {
                        currentSteps += newSensorSteps;
                        lastSensorSteps = window.sensorSteps;
                    } else if (Math.random() > 0.8) {
                        // fallback tiny ambient movement
                        currentSteps += 1; 
                    }
                    
                    let pct = Math.min(100, Math.round((currentSteps / goalSteps) * 100));
                    elBody.innerHTML = parts.length > 1 
                        ? `${currentSteps.toLocaleString()} / ${goalSteps.toLocaleString()} steps`
                        : `${currentSteps.toLocaleString()} steps`;
                        
                    if (elBar) elBar.style.width = pct + '%';
                    if (elText) elText.innerText = pct + '% complete';
                }
            }, 1000); // UI updates every 1 sec
        }, 100);
    }

    if (card.actions && card.actions.length > 0) {
        html += `<div class="card-actions">`;
        card.actions.forEach((btn, idx) => {
            const cls = idx === 0 ? 'primary' : '';
            // If the action value is a URL, open it directly
            if (btn.value && (btn.value.startsWith('http') || btn.value.startsWith('/'))) {
                html += `<a href="${btn.value}" target="_blank" class="card-btn ${cls}" style="text-decoration:none; text-align:center;">${btn.label}</a>`;
            } else {
                html += `<button class="card-btn ${cls}" onclick="handleCardAction('${btn.value}')">${btn.label}</button>`;
            }
        });
        html += `</div>`;
    }

    if (card.url) {
        html += `<a href="${card.url}" target="_blank" style="display:block; width:100%; padding:10px; text-align:center; background:var(--amazon-orange); color:black; font-weight:bold; border-radius:5px; margin-top:10px; text-decoration:none;"><i class="fa-brands fa-amazon"></i> View on Amazon</a>`;
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

// ══════════════════════════════════════════════════════════════════════
//  REAL-TIME ALEXA-STYLE REMINDER POLLING
// ══════════════════════════════════════════════════════════════════════

function startReminderPolling() {
    // Check every 30 seconds for upcoming event reminders
    checkReminders(); // Check immediately on load
    reminderInterval = setInterval(checkReminders, 30000);
}

async function checkReminders() {
    try {
        const res = await fetch(`${API_BASE}/reminders/${userId}`);
        if (!res.ok) return;
        const data = await res.json();

        if (data.reminders && data.reminders.length > 0) {
            data.reminders.forEach(reminder => {
                // Only show each reminder once
                if (!shownReminderIds.has(reminder.id + '_' + reminder.type)) {
                    shownReminderIds.add(reminder.id + '_' + reminder.type);
                    triggerAlexaReminder(reminder);
                }
            });
        }
    } catch (e) {
        // Silently fail — server might not be ready
    }
}

function triggerAlexaReminder(reminder) {
    // Push notification into the panel
    const panel = document.getElementById('notification-panel');
    const list = panel.querySelector('.notif-list');

    const div = document.createElement('div');
    div.className = 'notif-item unread fade-in';
    div.innerHTML = `
        <div class="notif-icon" style="background:#FF9900;"><i class="fa-solid fa-bell"></i></div>
        <div class="notif-body">
            <strong>Alexa+ Reminder</strong>
            <p>${reminder.message}</p>
            <span class="notif-time">Just now</span>
        </div>
    `;
    list.prepend(div);

    // Update badge
    const badge = document.querySelector('.notif-badge');
    if (badge) {
        badge.style.display = 'inline-flex';
        badge.textContent = parseInt(badge.textContent || '0') + 1;
    }

    // Show Alexa Toast
    showAlexaToast(reminder.message);

    // Show in chat
    addSystemMessage(`🔔 <strong>Alexa+ Reminder:</strong> ${reminder.message}`);

    // Browser notification
    if ('Notification' in window && Notification.permission === 'granted') {
        new Notification('LifeSync — Alexa+ Reminder', {
            body: reminder.message.replace(/[⏰📅]/g, ''),
            icon: 'https://ui-avatars.com/api/?name=LS&background=FF9900&color=fff&bold=true&size=64',
        });
    }

    // Trigger explicit device notification simulation (Email, SMS, Voice)
    if (typeof window.showSimulatedDeviceNotification === 'function') {
        const cleanMsg = reminder.message.replace(/[⏰📅]/g, '');
        window.showSimulatedDeviceNotification('Email', 'Alexa+ Reminder: ' + cleanMsg);
        setTimeout(() => window.showSimulatedDeviceNotification('SMS', cleanMsg), 1500);
        setTimeout(() => window.showSimulatedDeviceNotification('Voice', 'Incoming Alexa+ Reminder...'), 3000);
    }
}

function showAlexaToast(message) {
    const toast = document.getElementById('alexa-toast');
    const msgEl = document.getElementById('alexa-toast-msg');
    const cleanMsg = message.replace(/[⏰📅"]/g, '');
    msgEl.textContent = cleanMsg;
    toast.classList.remove('hidden');
    
    // Voice Output via SpeechSynthesis
    if ('speechSynthesis' in window) {
        const utterance = new SpeechSynthesisUtterance(cleanMsg);
        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        window.speechSynthesis.speak(utterance);
    }

    // Auto-dismiss after 8 seconds
    setTimeout(() => {
        toast.classList.add('hidden');
    }, 8000);
}

// ══════════════════════════════════════════════════════════════════════
//  INTERACTIVE CALENDAR MODAL
// ══════════════════════════════════════════════════════════════════════

function initCalendarModal() {
    const calModal = document.getElementById('calendar-modal');
    if (!calModal) return;

    document.getElementById('calendar-close').addEventListener('click', () => {
        calModal.classList.add('hidden');
    });
    calModal.addEventListener('click', (e) => {
        if (e.target === calModal) calModal.classList.add('hidden');
    });

    // Calendar navigation
    document.getElementById('cal-prev-month').addEventListener('click', () => {
        calCurrentMonth--;
        if (calCurrentMonth < 0) { calCurrentMonth = 11; calCurrentYear--; }
        renderCalendar();
    });
    document.getElementById('cal-next-month').addEventListener('click', () => {
        calCurrentMonth++;
        if (calCurrentMonth > 11) { calCurrentMonth = 0; calCurrentYear++; }
        renderCalendar();
    });

    // Add Event form
    document.getElementById('add-event-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const title = document.getElementById('cal-event-title').value.trim();
        const time = document.getElementById('cal-event-time').value;
        const desc = document.getElementById('cal-event-desc').value.trim();
        const eventType = document.getElementById('cal-event-type').value;

        if (!title) return;

        const btn = e.target.querySelector('button[type="submit"]');
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Adding...';
        btn.disabled = true;

        try {
            await fetch(`${API_BASE}/events/${userId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title,
                    start_time: time || new Date().toISOString(),
                    description: desc,
                    event_type: eventType
                })
            });

            // Reset form
            document.getElementById('cal-event-title').value = '';
            document.getElementById('cal-event-time').value = '';
            document.getElementById('cal-event-desc').value = '';

            // Refresh calendar
            await loadCalendarEventsForMonth();
            renderCalendar();
            if (calSelectedDate) showEventsForDate(calSelectedDate);

            addSystemMessage(`📅 Event added: <strong>${title}</strong>. I'll remind you when it's time — like Alexa!`);
        } catch (err) {
            console.error('Add event error:', err);
        }

        btn.innerHTML = '<i class="fa-solid fa-plus"></i> Add Event';
        btn.disabled = false;
    });
}

function openCalendarModal() {
    const modal = document.getElementById('calendar-modal');
    if (modal) {
        modal.classList.remove('hidden');
        calCurrentMonth = new Date().getMonth();
        calCurrentYear = new Date().getFullYear();
        loadCalendarEventsForMonth().then(() => renderCalendar());
    }
}

async function loadCalendarEventsForMonth() {
    try {
        const res = await fetch(`${API_BASE}/events/${userId}`);
        if (!res.ok) return;
        const data = await res.json();
        calEvents = data.events || [];
    } catch (err) {
        calEvents = [];
        console.error('Load events error:', err);
    }
}

function renderCalendar() {
    const grid = document.getElementById('calendar-grid');
    const titleEl = document.getElementById('cal-month-title');
    const months = ['January','February','March','April','May','June','July','August','September','October','November','December'];
    
    titleEl.textContent = `${months[calCurrentMonth]} ${calCurrentYear}`;

    const firstDay = new Date(calCurrentYear, calCurrentMonth, 1).getDay();
    const daysInMonth = new Date(calCurrentYear, calCurrentMonth + 1, 0).getDate();
    const daysInPrevMonth = new Date(calCurrentYear, calCurrentMonth, 0).getDate();
    const today = new Date();

    let html = '';

    // Previous month trailing days
    for (let i = firstDay - 1; i >= 0; i--) {
        const day = daysInPrevMonth - i;
        html += `<div class="cal-day other-month">${day}</div>`;
    }

    // Current month days
    for (let day = 1; day <= daysInMonth; day++) {
        const dateStr = `${calCurrentYear}-${String(calCurrentMonth + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        const isToday = today.getDate() === day && today.getMonth() === calCurrentMonth && today.getFullYear() === calCurrentYear;
        const isSelected = calSelectedDate === dateStr;
        const hasEvents = calEvents.some(evt => evt.start_time && evt.start_time.startsWith(dateStr));

        let classes = 'cal-day';
        if (isToday) classes += ' today';
        if (isSelected) classes += ' selected';
        if (hasEvents) classes += ' has-events';

        html += `<div class="${classes}" data-date="${dateStr}" onclick="selectCalendarDay('${dateStr}')">${day}</div>`;
    }

    // Next month leading days
    const totalCells = firstDay + daysInMonth;
    const remaining = totalCells % 7 === 0 ? 0 : 7 - (totalCells % 7);
    for (let i = 1; i <= remaining; i++) {
        html += `<div class="cal-day other-month">${i}</div>`;
    }

    grid.innerHTML = html;

    // Auto-select today
    if (!calSelectedDate) {
        const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
        selectCalendarDay(todayStr);
    }
}

window.selectCalendarDay = function(dateStr) {
    calSelectedDate = dateStr;
    // Re-render to update selection
    const grid = document.getElementById('calendar-grid');
    grid.querySelectorAll('.cal-day').forEach(d => {
        d.classList.remove('selected');
        if (d.getAttribute('data-date') === dateStr) d.classList.add('selected');
    });
    showEventsForDate(dateStr);
};

function showEventsForDate(dateStr) {
    const listEl = document.getElementById('calendar-events-list');
    const labelEl = document.getElementById('cal-day-label');
    const date = new Date(dateStr + 'T00:00:00');
    labelEl.textContent = `Events for ${date.toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' })}`;

    const dayEvents = calEvents.filter(evt => evt.start_time && evt.start_time.startsWith(dateStr));

    if (dayEvents.length === 0) {
        listEl.innerHTML = '<p style="color: var(--text-muted); text-align:center; padding: 16px; font-size: 13px;">No events on this day</p>';
        return;
    }

    const typeIcons = { meeting: '🏢', personal: '🏠', health: '💊', social: '🎉', deadline: '⏰' };

    let html = '';
    dayEvents.forEach(evt => {
        const timeStr = evt.start_time ? new Date(evt.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
        const icon = typeIcons[evt.event_type] || '📅';
        html += `
            <div class="notif-item" style="border-left: 3px solid var(--amazon-orange); margin-bottom: 8px; padding: 10px; border-radius: 6px; background: rgba(255,255,255,0.03);">
                <div class="notif-icon" style="background: var(--amazon-orange); min-width:32px; height:32px; border-radius:6px; display:flex; align-items:center; justify-content:center; font-size: 16px;">
                    ${icon}
                </div>
                <div class="notif-body" style="flex:1;">
                    <strong>${evt.title}</strong>
                    <p style="margin:2px 0; font-size: 12px; color: var(--text-secondary);">🕐 ${timeStr} ${evt.location ? '📍 ' + evt.location : ''}</p>
                    ${evt.description ? `<p style="margin:0; font-size: 11px; color: var(--text-muted);">${evt.description}</p>` : ''}
                </div>
            </div>
        `;
    });

    listEl.innerHTML = html;
}

// ══════════════════════════════════════════════════════════════════════
//  FOCUS TIMER (POMODORO)
// ══════════════════════════════════════════════════════════════════════

function initFocusTimer() {
    const modal = document.getElementById('focus-timer-modal');
    const closeBtn = document.getElementById('focus-timer-close');
    const triggerBtn = document.getElementById('btn-focus-timer');
    const startBtn = document.getElementById('focus-start');
    const pauseBtn = document.getElementById('focus-pause');
    const resetBtn = document.getElementById('focus-reset');

    triggerBtn.addEventListener('click', () => modal.classList.remove('hidden'));
    closeBtn.addEventListener('click', () => modal.classList.add('hidden'));
    modal.addEventListener('click', (e) => { if (e.target === modal) modal.classList.add('hidden'); });

    // Preset buttons
    document.querySelectorAll('.focus-preset').forEach(btn => {
        btn.addEventListener('click', () => {
            if (focusRunning) return;
            document.querySelectorAll('.focus-preset').forEach(b => {
                b.style.borderColor = 'var(--border-medium)';
                b.style.background = 'var(--bg-input)';
                b.style.color = 'var(--text-primary)';
                b.style.fontWeight = '400';
                b.classList.remove('active');
            });
            btn.style.borderColor = 'var(--amazon-orange)';
            btn.style.background = 'rgba(255,153,0,0.1)';
            btn.style.color = 'var(--amazon-orange)';
            btn.style.fontWeight = '600';
            btn.classList.add('active');

            const mins = parseInt(btn.getAttribute('data-min'));
            focusTimeLeft = mins * 60;
            focusTotalTime = mins * 60;
            updateTimerDisplay();
        });
    });

    startBtn.addEventListener('click', () => {
        if (focusRunning) return;
        focusRunning = true;
        startBtn.style.display = 'none';
        pauseBtn.style.display = 'inline-flex';

        focusTimerInterval = setInterval(() => {
            focusTimeLeft--;
            updateTimerDisplay();
            if (focusTimeLeft <= 0) {
                clearInterval(focusTimerInterval);
                focusRunning = false;
                startBtn.style.display = 'inline-flex';
                pauseBtn.style.display = 'none';
                addSystemMessage('⏰ <strong>Focus Timer Complete!</strong> Great work! Take a 5 minute break. 🎉');
                showAlexaToast('Focus Timer Complete! Time for a break.');
                if ('Notification' in window && Notification.permission === 'granted') {
                    new Notification('LifeSync — Focus Timer', { body: 'Time\'s up! Take a break.' });
                }
            }
        }, 1000);
    });

    pauseBtn.addEventListener('click', () => {
        clearInterval(focusTimerInterval);
        focusRunning = false;
        startBtn.style.display = 'inline-flex';
        pauseBtn.style.display = 'none';
    });

    resetBtn.addEventListener('click', () => {
        clearInterval(focusTimerInterval);
        focusRunning = false;
        focusTimeLeft = focusTotalTime;
        updateTimerDisplay();
        startBtn.style.display = 'inline-flex';
        pauseBtn.style.display = 'none';
    });

    updateTimerDisplay();
}

function updateTimerDisplay() {
    const mins = Math.floor(focusTimeLeft / 60);
    const secs = focusTimeLeft % 60;
    document.getElementById('focus-timer-text').textContent = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;

    // Update SVG circle
    const circle = document.getElementById('focus-timer-circle');
    const circumference = 2 * Math.PI * 90; // r=90
    const progress = focusTotalTime > 0 ? focusTimeLeft / focusTotalTime : 1;
    circle.setAttribute('stroke-dashoffset', circumference * (1 - progress));
}

// ══════════════════════════════════════════════════════════════════════
//  AMAZON SHOPPING MODAL
// ══════════════════════════════════════════════════════════════════════

function initShoppingModal() {
    const modal = document.getElementById('shopping-modal');
    const closeBtn = document.getElementById('shopping-close');

    closeBtn.addEventListener('click', () => modal.classList.add('hidden'));
    modal.addEventListener('click', (e) => { if (e.target === modal) modal.classList.add('hidden'); });

    // Search
    document.getElementById('amazon-search-btn').addEventListener('click', () => {
        const query = document.getElementById('amazon-search-input').value.trim();
        loadAmazonProducts(query);
    });
    document.getElementById('amazon-search-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            loadAmazonProducts(e.target.value.trim());
        }
    });

    // Category buttons
    document.querySelectorAll('.amazon-cat-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            loadAmazonProducts(btn.getAttribute('data-cat'));
        });
    });
}

function openShoppingModal() {
    const modal = document.getElementById('shopping-modal');
    modal.classList.remove('hidden');
    loadAmazonProducts('');
    loadShoppingList();
}

async function loadAmazonProducts(query) {
    const grid = document.getElementById('amazon-product-grid');
    grid.innerHTML = '<div class="ctx-widget skeleton-widget" style="height:200px;"></div><div class="ctx-widget skeleton-widget" style="height:200px;"></div>';

    try {
        const res = await fetch(`${API_BASE}/amazon/search?q=${encodeURIComponent(query || '')}`);
        const data = await res.json();

        if (!data.products || data.products.length === 0) {
            grid.innerHTML = '<p style="color: var(--text-muted); text-align:center; padding: 40px; grid-column: span 2;">No products found</p>';
            return;
        }

        let html = '';
        data.products.forEach(product => {
            html += `
                <div class="amazon-product-card fade-in">
                    <img src="${product.image}" alt="${product.title}" onerror="this.style.display='none'">
                    <div class="product-title">${product.title}</div>
                    <div class="product-price">$${product.price.toFixed(2)}</div>
                    <div class="product-rating">
                        ${'★'.repeat(Math.floor(product.rating))}${'☆'.repeat(5 - Math.floor(product.rating))} 
                        ${product.rating} (${product.reviews.toLocaleString()} reviews)
                    </div>
                    ${product.prime ? '<span class="prime-badge">✓ prime</span>' : ''}
                    <a href="${product.url}" target="_blank" class="amazon-buy-btn">
                        <i class="fa-brands fa-amazon"></i> Buy on Amazon
                    </a>
                </div>
            `;
        });

        grid.innerHTML = html;
    } catch (err) {
        grid.innerHTML = '<p style="color: var(--amazon-red); text-align:center; padding: 40px; grid-column: span 2;">Failed to load products</p>';
        console.error('Amazon search error:', err);
    }
}

async function loadShoppingList() {
    const listEl = document.getElementById('shopping-list-items');
    try {
        const res = await fetch(`${API_BASE}/shopping/${userId}`);
        const data = await res.json();

        if (!data.items || data.items.length === 0) {
            listEl.innerHTML = '<p style="color: var(--text-muted); font-size: 13px; text-align: center; padding: 10px;">Your shopping list is empty</p>';
            return;
        }

        let html = '';
        data.items.forEach(item => {
            html += `
                <div class="notif-item" style="margin-bottom: 6px; border-radius: 6px; background: rgba(255,255,255,0.02); padding: 10px; ${item.is_purchased ? 'opacity: 0.5; text-decoration: line-through;' : ''}">
                    <input type="checkbox" ${item.is_purchased ? 'checked' : ''} 
                        onchange="toggleShoppingItem('${item.id}')"
                        style="accent-color: var(--amazon-orange); margin-right: 8px; cursor: pointer;">
                    <div class="notif-body" style="flex:1;">
                        <strong style="font-size: 13px;">${item.product_name}</strong>
                        <p style="font-size: 11px; color: var(--text-muted);">${item.category} • Qty: ${item.quantity}${item.estimated_price ? ' • $' + item.estimated_price : ''}</p>
                    </div>
                    ${item.amazon_url ? `<a href="${item.amazon_url}" target="_blank" style="color: var(--amazon-orange); font-size: 13px; text-decoration: none;"><i class="fa-brands fa-amazon"></i></a>` : ''}
                </div>
            `;
        });

        listEl.innerHTML = html;
    } catch (err) {
        listEl.innerHTML = '<p style="color: var(--amazon-red); font-size: 13px;">Failed to load shopping list</p>';
    }
}

window.toggleShoppingItem = async function(itemId) {
    try {
        await fetch(`${API_BASE}/shopping/toggle/${itemId}`, { method: 'PUT' });
        loadShoppingList();
    } catch (err) {
        console.error('Toggle error:', err);
    }
};

// ══════════════════════════════════════════════════════════════════════
//  MOOD TRACKER
// ══════════════════════════════════════════════════════════════════════

function initMoodModal() {
    const modal = document.getElementById('mood-modal');
    const closeBtn = document.getElementById('mood-close');
    const saveBtn = document.getElementById('mood-save-btn');

    closeBtn.addEventListener('click', () => modal.classList.add('hidden'));
    modal.addEventListener('click', (e) => { if (e.target === modal) modal.classList.add('hidden'); });

    // Mood selection
    document.querySelectorAll('#mood-selector .mood-option').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#mood-selector .mood-option').forEach(b => b.classList.remove('selected'));
            btn.classList.add('selected');
            selectedMood = btn.getAttribute('data-mood');
            saveBtn.disabled = false;
            saveBtn.textContent = `Save mood: ${selectedMood}`;
        });
    });

    saveBtn.addEventListener('click', () => {
        if (!selectedMood) return;
        const note = document.getElementById('mood-note').value.trim();
        saveMood(selectedMood, note);
        selectedMood = null;
        document.querySelectorAll('#mood-selector .mood-option').forEach(b => b.classList.remove('selected'));
        document.getElementById('mood-note').value = '';
        saveBtn.disabled = true;
        saveBtn.textContent = 'Select a mood to save';
        renderMoodHistory();
        addSystemMessage(`😊 Mood logged: <strong>${moodHistory[moodHistory.length - 1]?.mood}</strong>. Keep tracking — I'll provide insights over time!`);
    });
}

function openMoodModal() {
    const modal = document.getElementById('mood-modal');
    modal.classList.remove('hidden');
    renderMoodHistory();
}

function saveMood(mood, note = '') {
    const entry = {
        mood,
        note,
        timestamp: new Date().toISOString(),
        date: new Date().toLocaleDateString(),
    };
    moodHistory.push(entry);
    if (moodHistory.length > 30) moodHistory = moodHistory.slice(-30);
    localStorage.setItem('lifesync_mood_history', JSON.stringify(moodHistory));
}

function renderMoodHistory() {
    const container = document.getElementById('mood-history');
    if (!container) return;
    
    const moodEmojis = { great: '😄', good: '🙂', neutral: '😐', low: '😔', stressed: '😰' };
    
    if (moodHistory.length === 0) {
        container.innerHTML = '<p style="color: var(--text-muted); font-size: 12px;">No mood entries yet</p>';
        return;
    }

    let html = '';
    moodHistory.slice(-14).reverse().forEach(entry => {
        html += `<div class="mood-chip" title="${entry.date}: ${entry.mood}${entry.note ? ' - ' + entry.note : ''}">
            <span>${moodEmojis[entry.mood] || '😐'}</span>
            <span>${entry.date.split('/').slice(0, 2).join('/')}</span>
        </div>`;
    });

    container.innerHTML = html;
}

// ══════════════════════════════════════════════════════════════════════
//  QUICK NOTES
// ══════════════════════════════════════════════════════════════════════

function initNotesModal() {
    const modal = document.getElementById('notes-modal');
    const closeBtn = document.getElementById('notes-close');
    const addBtn = document.getElementById('note-add-btn');
    const input = document.getElementById('note-input');

    closeBtn.addEventListener('click', () => modal.classList.add('hidden'));
    modal.addEventListener('click', (e) => { if (e.target === modal) modal.classList.add('hidden'); });

    addBtn.addEventListener('click', () => addNote());
    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); addNote(); }
    });
}

function openNotesModal() {
    const modal = document.getElementById('notes-modal');
    modal.classList.remove('hidden');
    renderNotes();
}

function addNote() {
    const input = document.getElementById('note-input');
    const text = input.value.trim();
    if (!text) return;

    quickNotes.unshift({
        id: Date.now(),
        text,
        timestamp: new Date().toISOString(),
    });
    localStorage.setItem('lifesync_notes', JSON.stringify(quickNotes));
    input.value = '';
    renderNotes();
}

window.deleteNote = function(id) {
    quickNotes = quickNotes.filter(n => n.id !== id);
    localStorage.setItem('lifesync_notes', JSON.stringify(quickNotes));
    renderNotes();
};

function renderNotes() {
    const container = document.getElementById('notes-list');
    if (!container) return;

    if (quickNotes.length === 0) {
        container.innerHTML = '<p style="color: var(--text-muted); text-align: center; padding: 20px; font-size: 13px;">No notes yet. Start jotting things down!</p>';
        return;
    }

    let html = '';
    quickNotes.forEach(note => {
        const time = new Date(note.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const date = new Date(note.timestamp).toLocaleDateString([], { month: 'short', day: 'numeric' });
        html += `
            <div class="note-item fade-in">
                <div class="note-text">${note.text}</div>
                <div class="note-time">${date} ${time}</div>
                <button class="note-delete" onclick="deleteNote(${note.id})" title="Delete"><i class="fa-solid fa-trash-can"></i></button>
            </div>
        `;
    });

    container.innerHTML = html;
}

// ══════════════════════════════════════════════════════════════════════
//  DAILY STREAK
// ══════════════════════════════════════════════════════════════════════

function updateStreak() {
    const today = new Date().toDateString();
    const yesterday = new Date(Date.now() - 86400000).toDateString();

    if (dailyStreak.lastDate === today) {
        // Already counted today
    } else if (dailyStreak.lastDate === yesterday) {
        // Consecutive day
        dailyStreak.count++;
        dailyStreak.lastDate = today;
    } else if (dailyStreak.lastDate === '') {
        // First time
        dailyStreak.count = 1;
        dailyStreak.lastDate = today;
    } else {
        // Streak broken
        dailyStreak.count = 1;
        dailyStreak.lastDate = today;
    }

    localStorage.setItem('lifesync_streak', JSON.stringify(dailyStreak));
    document.getElementById('streak-count').textContent = dailyStreak.count;
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
                <div class="ctx-row"><span>Name</span><span class="ctx-val">${data.preferences.name || currentUser.name || 'User'}</span></div>
                <div class="ctx-row"><span>Fitness Goal</span><span class="ctx-val">${data.preferences.fitness_goal || '10,000 steps'}</span></div>
                <div class="ctx-row"><span>Diet</span><span class="ctx-val">${data.preferences.diet_preference || 'N/A'}</span></div>
            </div>`;
        }

        // Daily Streak
        html += `<div class="ctx-widget fade-in">
            <h4>🔥 Daily Streak</h4>
            <div class="ctx-row"><span>Current Streak</span><span class="ctx-val">${dailyStreak.count} day${dailyStreak.count !== 1 ? 's' : ''}</span></div>
            <div class="ctx-row"><span>Last Active</span><span class="ctx-val">${dailyStreak.lastDate ? new Date(dailyStreak.lastDate).toLocaleDateString([], {month:'short', day:'numeric'}) : 'Today'}</span></div>
        </div>`;

        // Mood Summary
        if (moodHistory.length > 0) {
            const latest = moodHistory[moodHistory.length - 1];
            const moodEmojis = { great: '😄', good: '🙂', neutral: '😐', low: '😔', stressed: '😰' };
            html += `<div class="ctx-widget fade-in">
                <h4>😊 Mood</h4>
                <div class="ctx-row"><span>Latest</span><span class="ctx-val">${moodEmojis[latest.mood] || '😐'} ${latest.mood}</span></div>
                <div class="ctx-row"><span>Entries</span><span class="ctx-val">${moodHistory.length}</span></div>
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
            <div class="ctx-row"><span>Notes</span><span class="ctx-val">${quickNotes.length}</span></div>
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

// ══════════════════════════════════════════════════════════════════════
//  SIMULATED DEVICE NOTIFICATIONS (SMS/Email/Voice)
// ══════════════════════════════════════════════════════════════════════

window.showSimulatedDeviceNotification = function(type, message) {
    const notif = document.createElement('div');
    notif.className = 'simulated-notif';
    
    let icon = 'fa-comment';
    let color = '#34C759'; // SMS Green
    
    if (type === 'Email') {
        icon = 'fa-envelope';
        color = '#007AFF'; // Email Blue
    } else if (type === 'Voice') {
        icon = 'fa-phone';
        color = '#FF3B30'; // Phone Red
    }
    
    notif.innerHTML = `
        <div class="sim-notif-icon" style="background: ${color}">
            <i class="fa-solid ${icon}"></i>
        </div>
        <div class="sim-notif-content">
            <strong>${type} from LifeSync</strong>
            <p>${message}</p>
        </div>
    `;
    
    document.body.appendChild(notif);
    
    // Animate in
    setTimeout(() => { notif.classList.add('visible'); }, 10);
    
    // Auto remove
    setTimeout(() => {
        notif.classList.remove('visible');
        setTimeout(() => notif.remove(), 300);
    }, 6000);
};
