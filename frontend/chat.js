/* ============================================================
   Chat.js — Conversational query interface
   ============================================================ */

let conversationHistory = [];
let isProcessing = false;

function initChat() {
    const input = document.getElementById('chat-input');
    const sendBtn = document.getElementById('btn-send');

    // Send on button click
    sendBtn.addEventListener('click', () => sendMessage());

    // Send on Enter (Shift+Enter for new line)
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Auto-resize textarea
    input.addEventListener('input', () => {
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 120) + 'px';
    });

    // Suggested query buttons
    document.querySelectorAll('.suggestion').forEach(btn => {
        btn.addEventListener('click', () => {
            input.value = btn.dataset.query;
            sendMessage();
        });
    });
}


async function sendMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();

    if (!message || isProcessing) return;

    isProcessing = true;
    input.value = '';
    input.style.height = 'auto';

    // Add user message
    addMessage('user', message);

    // Show loading
    const loadingId = addLoadingMessage();

    try {
        const response = await api.sendMessage(message, conversationHistory);

        // Remove loading
        removeMessage(loadingId);

        // Build response content
        let content = '';

        if (response.is_guardrail_blocked) {
            content = `<div class="guardrail-message">${escapeHtml(response.answer)}</div>`;
        } else {
            content = `<p>${formatAnswer(response.answer)}</p>`;

            // Show SQL query if available
            if (response.sql_query) {
                content += `<div class="sql-block">${escapeHtml(response.sql_query)}</div>`;
            }

            // Show results table if available
            if (response.query_results && response.query_results.length > 0) {
                content += buildResultsTable(response.query_results);
            }
        }

        addMessage('assistant', content, true);

        // Highlight referenced nodes in graph
        if (response.referenced_nodes && response.referenced_nodes.length > 0) {
            highlightNodes(response.referenced_nodes);
        }

        // Update conversation history
        conversationHistory.push(
            { role: 'user', content: message },
            { role: 'assistant', content: response.answer }
        );

        // Keep history manageable
        if (conversationHistory.length > 20) {
            conversationHistory = conversationHistory.slice(-20);
        }

    } catch (e) {
        removeMessage(loadingId);
        addMessage('assistant', `<p class="guardrail-message">Error: ${escapeHtml(e.message)}</p>`, true);
    }

    isProcessing = false;
}


function addMessage(role, content, isHtml = false) {
    const container = document.getElementById('chat-messages');
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}-message`;

    const avatarSvg = role === 'user'
        ? '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>'
        : '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><circle cx="5" cy="6" r="2"/><circle cx="19" cy="6" r="2"/><line x1="9.5" y1="10.5" x2="6.5" y2="7.5"/><line x1="14.5" y1="10.5" x2="17.5" y2="7.5"/></svg>';

    msgDiv.innerHTML = `
        <div class="message-avatar ${role === 'user' ? 'user-avatar' : 'system-avatar'}">
            ${avatarSvg}
        </div>
        <div class="message-content">
            ${isHtml ? content : `<p>${escapeHtml(content)}</p>`}
        </div>
    `;

    container.appendChild(msgDiv);
    container.scrollTop = container.scrollHeight;
    return msgDiv;
}


function addLoadingMessage() {
    const container = document.getElementById('chat-messages');
    const id = 'loading-' + Date.now();
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message assistant-message';
    msgDiv.id = id;
    msgDiv.innerHTML = `
        <div class="message-avatar system-avatar">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="3"/><circle cx="5" cy="6" r="2"/><circle cx="19" cy="6" r="2"/>
                <line x1="9.5" y1="10.5" x2="6.5" y2="7.5"/>
                <line x1="14.5" y1="10.5" x2="17.5" y2="7.5"/>
            </svg>
        </div>
        <div class="message-content">
            <div class="loading-dots">
                <span></span><span></span><span></span>
            </div>
        </div>
    `;
    container.appendChild(msgDiv);
    container.scrollTop = container.scrollHeight;
    return id;
}


function removeMessage(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}


function buildResultsTable(results) {
    if (!results || results.length === 0) return '';

    const keys = Object.keys(results[0]);
    const displayResults = results.slice(0, 10); // Show max 10 rows

    let html = '<div style="overflow-x:auto;"><table class="results-table">';
    html += '<thead><tr>';
    for (const key of keys) {
        html += `<th>${escapeHtml(key)}</th>`;
    }
    html += '</tr></thead><tbody>';

    for (const row of displayResults) {
        html += '<tr>';
        for (const key of keys) {
            const val = row[key];
            html += `<td>${val !== null && val !== undefined ? escapeHtml(String(val)) : '—'}</td>`;
        }
        html += '</tr>';
    }
    html += '</tbody></table></div>';

    if (results.length > 10) {
        html += `<p style="font-size:11px;color:var(--text-muted);margin-top:4px;">Showing 10 of ${results.length} results</p>`;
    }

    return html;
}


function formatAnswer(text) {
    if (!text) return '';

    // Convert markdown-like formatting
    let formatted = escapeHtml(text);

    // Bold
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // Code inline
    formatted = formatted.replace(/`(.*?)`/g, '<code style="font-family:var(--font-mono);font-size:11px;background:var(--bg-surface);padding:1px 4px;border-radius:3px;">$1</code>');

    // Line breaks
    formatted = formatted.replace(/\n/g, '<br>');

    return formatted;
}


function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
