/* ═══════════════════════════════════════════════
   MEDI CARE — CHATBOT JAVASCRIPT
   ═══════════════════════════════════════════════ */

let chatContext = {};
let chatStep = 'initial';
let isTyping = false;

const messagesEl = document.getElementById('chatMessages');
const inputEl = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');

// ─── PARSE BOLD TEXT ──────────────────────────────
function parseBold(text) {
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>');
}

// ─── GET TIME ─────────────────────────────────────
function getTime() {
  return new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
}

// ─── ADD MESSAGE ──────────────────────────────────
function addMessage(text, sender = 'bot', severity = null, showDisclaimer = false, extraHtml = '') {
  const el = document.createElement('div');
  el.className = `message ${sender}`;

  const avatarEl = document.createElement('div');
  avatarEl.className = 'message-avatar';
  avatarEl.textContent = sender === 'bot' ? '🤖' : '👤';

  let bubbleClass = 'bubble';
  if (severity) bubbleClass += ` severity-${severity}`;

  const contentEl = document.createElement('div');
  contentEl.className = 'message-content';

  let disclaimerHtml = '';
  if (showDisclaimer) {
    disclaimerHtml = `<div class="bubble-disclaimer">⚕️ This is an AI-based assistant and not a real doctor. Please consult a qualified physician for medical advice.</div>`;
  }

  contentEl.innerHTML = `
    <div class="${bubbleClass}">${parseBold(text)}${disclaimerHtml}${extraHtml}</div>
    <span class="message-time">${getTime()}</span>
  `;

  el.appendChild(avatarEl);
  el.appendChild(contentEl);
  messagesEl.appendChild(el);
  scrollToBottom();
  return el;
}

// ─── SHOW TYPING ──────────────────────────────────
function showTyping() {
  removeTyping();
  const el = document.createElement('div');
  el.className = 'typing-indicator';
  el.id = 'typingIndicator';
  const avatarEl = document.createElement('div');
  avatarEl.className = 'message-avatar';
  avatarEl.textContent = '🤖';
  el.innerHTML = `
    <div class="message-avatar">🤖</div>
    <div class="typing-dots">
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
    </div>
  `;
  messagesEl.appendChild(el);
  scrollToBottom();
}

function removeTyping() {
  const el = document.getElementById('typingIndicator');
  if (el) el.remove();
}

// ─── SCROLL ───────────────────────────────────────
function scrollToBottom() {
  setTimeout(() => {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }, 50);
}

// ─── SEND MESSAGE ─────────────────────────────────
async function sendMessage(overrideText = null) {
  const text = (overrideText || inputEl.value).trim();
  if (!text || isTyping) return;

  inputEl.value = '';
  addMessage(text, 'user');
  setLoading(true);
  showTyping();

  // Simulate thinking delay (realistic)
  const thinkTime = 800 + Math.random() * 700;
  await new Promise(r => setTimeout(r, thinkTime));

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, context: chatContext, step: chatStep })
    });
    const data = await res.json();
    removeTyping();
    handleResponse(data);
  } catch (err) {
    removeTyping();
    addMessage('Sorry, I encountered an error. Please try again.', 'bot');
  }

  setLoading(false);
}

// ─── HANDLE RESPONSE ──────────────────────────────
function handleResponse(data) {
  if (data.type === 'followup') {
    chatContext.symptom = data.symptom;
    chatStep = 'followup';
    addMessage(data.message, 'bot');

    // Show option buttons
    const optEl = document.createElement('div');
    optEl.className = 'message bot';
    optEl.innerHTML = `
      <div class="message-avatar">🤖</div>
      <div class="message-content">
        <div class="quick-options">
          <button class="quick-option-btn" onclick="sendMessage('a')">a) First option</button>
          <button class="quick-option-btn" onclick="sendMessage('b')">b) Second option</button>
          <button class="quick-option-btn" onclick="sendMessage('c')">c) Third option</button>
        </div>
      </div>
    `;
    messagesEl.appendChild(optEl);
    scrollToBottom();

  } else if (data.type === 'diagnosis') {
    chatStep = 'initial';
    chatContext = {};
    addMessage(data.message, 'bot', data.severity, true);

    if (data.severity === 'emergency') {
      // Show emergency alert
      const alertEl = document.createElement('div');
      alertEl.className = 'message bot';
      alertEl.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div class="message-content">
          <div class="bubble severity-emergency" style="text-align:center;">
            <div style="font-size:2rem; margin-bottom:8px;">🚨</div>
            <strong style="font-size:1.1rem; color: var(--accent-red);">CALL 108 IMMEDIATELY</strong><br>
            <a href="tel:108" style="display:inline-block; margin-top:10px; padding:10px 24px; background: var(--gradient-danger); color:white; border-radius:10px; text-decoration:none; font-weight:700;">📞 CALL 108</a>
          </div>
        </div>
      `;
      messagesEl.appendChild(alertEl);
      scrollToBottom();
    }

    // Follow-up suggestions
    setTimeout(() => {
      addSuggestions();
    }, 500);

  } else if (data.type === 'greeting' || data.type === 'help') {
    chatStep = 'initial';
    addMessage(data.message, 'bot');
    addSymptomChips();

  } else {
    chatStep = 'initial';
    chatContext = {};
    addMessage(data.message, 'bot', data.severity || null);
  }
}

// ─── SYMPTOM CHIPS ────────────────────────────────
function addSymptomChips() {
  const symptoms = ['🤒 Fever', '😷 Cough', '🤕 Headache', '💔 Chest Pain', '🤢 Stomach Pain', '🤧 Cold', '🔙 Back Pain', '🔄 Dizziness'];
  const el = document.createElement('div');
  el.className = 'message bot';
  el.innerHTML = `
    <div class="message-avatar">🤖</div>
    <div class="message-content">
      <div class="suggestion-chips">
        ${symptoms.map(s => `<button class="chip" onclick="sendMessage('${s.split(' ').slice(1).join(' ')}')">${s}</button>`).join('')}
      </div>
    </div>
  `;
  messagesEl.appendChild(el);
  scrollToBottom();
}

// ─── FOLLOW-UP SUGGESTIONS ────────────────────────
function addSuggestions() {
  const el = document.createElement('div');
  el.className = 'message bot';
  el.innerHTML = `
    <div class="message-avatar">🤖</div>
    <div class="message-content">
      <div class="bubble">Do you have any other symptoms?</div>
      <div class="quick-options" style="margin-top: 8px;">
        <button class="quick-option-btn" onclick="sendMessage('fever')">🤒 Check Fever</button>
        <button class="quick-option-btn" onclick="sendMessage('cough')">😷 Check Cough</button>
        <button class="quick-option-btn" onclick="window.location.href='/book-appointment'">📅 Book Appointment</button>
      </div>
    </div>
  `;
  messagesEl.appendChild(el);
  scrollToBottom();
}

// ─── LOADING STATE ────────────────────────────────
function setLoading(loading) {
  isTyping = loading;
  sendBtn.disabled = loading;
  if (loading) {
    sendBtn.innerHTML = '<div class="spinner" style="width:16px;height:16px;"></div>';
  } else {
    sendBtn.innerHTML = '➤';
  }
}

// ─── CLEAR CHAT ───────────────────────────────────
function clearChat() {
  messagesEl.innerHTML = '';
  chatContext = {};
  chatStep = 'initial';
  initBotGreeting();
  showToast('Chat cleared', 'info');
}

// ─── INIT GREETING ────────────────────────────────
function initBotGreeting() {
  addMessage("Hello! 👋 I'm **MediBot**, your AI health assistant.\n\nI can help you analyze symptoms and suggest basic remedies. What symptoms are you experiencing today?", 'bot');
  setTimeout(() => addSymptomChips(), 300);
}

// ─── INPUT HANDLERS ───────────────────────────────
inputEl.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

sendBtn.addEventListener('click', () => sendMessage());

// ─── INIT ─────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initBotGreeting();
});
