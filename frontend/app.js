/* ============================================================
   App.js — Core application logic and API layer
   ============================================================ */

   const API_BASE = "https://dodge-graph-based-data-modeling-query.onrender.com";

const api = {
    async get(endpoint) {
        const response = await fetch(`${API_BASE}${endpoint}`);
        if (!response.ok) throw new Error(`API error: ${response.status}`);
        return response.json();
    },

    async post(endpoint, data) {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        if (!response.ok) throw new Error(`API error: ${response.status}`);
        return response.json();
    },

    // Graph endpoints
    getGraphOverview: (limit = 200) => api.get(`/api/graph/overview?limit=${limit}`),
    getNodeDetail: (nodeId) => api.get(`/api/graph/node/${nodeId}`),
    expandNode: (nodeId, limit = 50) => api.get(`/api/graph/expand/${nodeId}?limit=${limit}`),
    searchNodes: (query, nodeType = null) => {
        let url = `/api/graph/search?q=${encodeURIComponent(query)}`;
        if (nodeType) url += `&node_type=${nodeType}`;
        return api.get(url);
    },
    traceFlow: (entityType, entityId) => api.get(`/api/graph/flow/${entityType}/${entityId}`),
    getBrokenFlows: () => api.get('/api/graph/broken-flows'),
    getStatistics: () => api.get('/api/graph/statistics'),

    // Chat endpoints
    sendMessage: (message, history = []) => api.post('/api/chat', { message, conversation_history: history }),

    // Data endpoints
    ingestData: () => api.post('/api/ingest'),
    getSchema: () => api.get('/api/schema'),
};


// ============ Resize Handle ============
function initResize() {
    const handle = document.getElementById('resize-handle');
    const graphPanel = document.getElementById('graph-panel');
    const chatPanel = document.getElementById('chat-panel');
    let isResizing = false;

    handle.addEventListener('mousedown', (e) => {
        isResizing = true;
        handle.classList.add('active');
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
    });

    document.addEventListener('mousemove', (e) => {
        if (!isResizing) return;
        const containerWidth = document.querySelector('.main-content').offsetWidth;
        const newGraphWidth = e.clientX;
        const newChatWidth = containerWidth - newGraphWidth - 4; // 4px handle

        if (newGraphWidth > 300 && newChatWidth > 300) {
            graphPanel.style.flex = 'none';
            graphPanel.style.width = `${newGraphWidth}px`;
            chatPanel.style.width = `${newChatWidth}px`;
        }
    });

    document.addEventListener('mouseup', () => {
        if (isResizing) {
            isResizing = false;
            handle.classList.remove('active');
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
            // Trigger Cytoscape resize
            if (window.cy) window.cy.resize();
        }
    });
}


// ============ Statistics Modal ============
function initStatsModal() {
    const btn = document.getElementById('btn-statistics');
    const modal = document.getElementById('stats-modal');
    const closeBtn = document.getElementById('close-stats-modal');

    btn.addEventListener('click', async () => {
        modal.classList.add('visible');
        const content = document.getElementById('stats-content');
        content.innerHTML = '<p class="loading-text">Loading statistics...</p>';

        try {
            const stats = await api.getStatistics();
            let html = '<h4>Node Counts</h4>';
            for (const [label, count] of Object.entries(stats.node_counts || {})) {
                html += `<div class="stat-row"><span class="stat-label">${label}</span><span class="stat-value">${count.toLocaleString()}</span></div>`;
            }
            html += '<h4>Relationship Counts</h4>';
            for (const [type, count] of Object.entries(stats.relationship_counts || {})) {
                html += `<div class="stat-row"><span class="stat-label">${type}</span><span class="stat-value">${count.toLocaleString()}</span></div>`;
            }
            html += '<h4>Totals</h4>';
            html += `<div class="stat-row"><span class="stat-label">Total Nodes</span><span class="stat-value">${(stats.total_nodes || 0).toLocaleString()}</span></div>`;
            html += `<div class="stat-row"><span class="stat-label">Total Relationships</span><span class="stat-value">${(stats.total_relationships || 0).toLocaleString()}</span></div>`;
            content.innerHTML = html;
        } catch (e) {
            content.innerHTML = `<p class="loading-text">Failed to load statistics: ${e.message}</p>`;
        }
    });

    closeBtn.addEventListener('click', () => modal.classList.remove('visible'));
    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.classList.remove('visible');
    });
}


// ============ Init ============
document.addEventListener('DOMContentLoaded', () => {
    initResize();
    initStatsModal();
    initGraph();
    initChat();
});
