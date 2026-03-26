/* ============================================================
   Graph.js — Cytoscape.js graph visualization
   ============================================================ */

// Entity color map
const ENTITY_COLORS = {
    Customer: '#6366f1',
    SalesOrder: '#f59e0b',
    Delivery: '#10b981',
    BillingDocument: '#ec4899',
    JournalEntry: '#8b5cf6',
    Payment: '#06b6d4',
    Material: '#f97316',
    Plant: '#84cc16',
    OrderItem: '#fb923c',
};

const DEFAULT_COLOR = '#64748b';

// Entity shapes
const ENTITY_SHAPES = {
    Customer: 'ellipse',
    SalesOrder: 'round-rectangle',
    Delivery: 'diamond',
    BillingDocument: 'round-rectangle',
    JournalEntry: 'octagon',
    Payment: 'star',
    Material: 'triangle',
    Plant: 'hexagon',
    OrderItem: 'round-rectangle',
};

let selectedNode = null;
let activeFilter = 'all';

function initGraph() {
    window.cy = cytoscape({
        container: document.getElementById('cy'),
        style: [
            {
                selector: 'node',
                style: {
                    'label': 'data(displayName)',
                    'text-valign': 'bottom',
                    'text-halign': 'center',
                    'font-size': '10px',
                    'font-family': "'Inter', sans-serif",
                    'color': '#9898b0',
                    'text-margin-y': 6,
                    'text-max-width': '80px',
                    'text-wrap': 'ellipsis',
                    'background-color': 'data(color)',
                    'shape': 'data(shape)',
                    'width': 30,
                    'height': 30,
                    'border-width': 2,
                    'border-color': 'data(color)',
                    'border-opacity': 0.3,
                    'overlay-padding': 6,
                    'transition-property': 'border-width, border-opacity, width, height',
                    'transition-duration': '0.2s',
                },
            },
            {
                selector: 'node:selected',
                style: {
                    'border-width': 3,
                    'border-opacity': 1,
                    'border-color': '#ffffff',
                    'width': 38,
                    'height': 38,
                },
            },
            {
                selector: 'node.highlighted',
                style: {
                    'border-width': 3,
                    'border-opacity': 1,
                    'border-color': '#fbbf24',
                    'width': 36,
                    'height': 36,
                    'z-index': 100,
                },
            },
            {
                selector: 'node.faded',
                style: {
                    'opacity': 0.2,
                },
            },
            {
                selector: 'edge',
                style: {
                    'width': 1.5,
                    'line-color': 'rgba(255, 255, 255, 0.12)',
                    'target-arrow-color': 'rgba(255, 255, 255, 0.25)',
                    'target-arrow-shape': 'triangle',
                    'arrow-scale': 0.8,
                    'curve-style': 'bezier',
                    'label': 'data(type)',
                    'font-size': '8px',
                    'font-family': "'Inter', sans-serif",
                    'color': 'rgba(255,255,255,0.15)',
                    'text-rotation': 'autorotate',
                    'text-margin-y': -8,
                    'transition-property': 'line-color, target-arrow-color',
                    'transition-duration': '0.2s',
                },
            },
            {
                selector: 'edge.highlighted',
                style: {
                    'line-color': 'rgba(251, 191, 36, 0.5)',
                    'target-arrow-color': 'rgba(251, 191, 36, 0.7)',
                    'width': 2.5,
                    'z-index': 100,
                },
            },
            {
                selector: 'edge.faded',
                style: {
                    'opacity': 0.1,
                },
            },
        ],
        layout: { name: 'preset' },
        wheelSensitivity: 0.3,
        minZoom: 0.1,
        maxZoom: 5,
    });

    // Node click handler
    window.cy.on('tap', 'node', function (e) {
        const node = e.target;
        selectedNode = node;
        showNodeDetail(node);
    });

    // Background click — close detail
    window.cy.on('tap', function (e) {
        if (e.target === window.cy) {
            hideNodeDetail();
            selectedNode = null;
            window.cy.elements().removeClass('highlighted faded');
        }
    });

    // Node hover
    window.cy.on('mouseover', 'node', function (e) {
        const node = e.target;
        node.connectedEdges().addClass('highlighted');
        node.neighborhood().nodes().addClass('highlighted');
    });

    window.cy.on('mouseout', 'node', function (e) {
        if (!selectedNode) {
            window.cy.elements().removeClass('highlighted');
        }
    });

    // Setup controls
    setupGraphControls();

    // Load graph
    loadGraph();
}


async function loadGraph() {
    try {
        const data = await api.getGraphOverview(300);
        renderGraph(data);
    } catch (e) {
        console.error('Failed to load graph:', e);
    }
}


function renderGraph(data) {
    const elements = [];

    // Add nodes
    for (const node of data.nodes) {
        elements.push({
            data: {
                id: node.id,
                label: node.label,
                displayName: truncate(node.display_name || node.id, 16),
                fullName: node.display_name || node.id,
                color: ENTITY_COLORS[node.label] || DEFAULT_COLOR,
                shape: ENTITY_SHAPES[node.label] || 'ellipse',
                properties: node.properties,
                nodeType: node.label,
            },
        });
    }

    // Add edges
    for (const edge of data.edges) {
        elements.push({
            data: {
                id: `edge-${edge.source}-${edge.target}-${edge.type}`,
                source: edge.source,
                target: edge.target,
                type: edge.type,
            },
        });
    }

    window.cy.elements().remove();
    window.cy.add(elements);

    // Apply layout
    window.cy.layout({
        name: 'cose',
        animate: true,
        animationDuration: 800,
        nodeOverlap: 20,
        idealEdgeLength: 80,
        edgeElasticity: 100,
        nestingFactor: 1.2,
        gravity: 0.25,
        numIter: 1000,
        randomize: true,
        componentSpacing: 100,
    }).run();

    // Update stats
    updateStats();
}


function addNodesToGraph(data) {
    const existingIds = new Set(window.cy.nodes().map(n => n.id()));
    const elements = [];

    for (const node of data.nodes) {
        if (!existingIds.has(node.id)) {
            elements.push({
                group: 'nodes',
                data: {
                    id: node.id,
                    label: node.label,
                    displayName: truncate(node.display_name || node.id, 16),
                    fullName: node.display_name || node.id,
                    color: ENTITY_COLORS[node.label] || DEFAULT_COLOR,
                    shape: ENTITY_SHAPES[node.label] || 'ellipse',
                    properties: node.properties,
                    nodeType: node.label,
                },
            });
        }
    }

    const existingEdges = new Set(window.cy.edges().map(e => e.id()));
    for (const edge of data.edges) {
        const edgeId = `edge-${edge.source}-${edge.target}-${edge.type}`;
        if (!existingEdges.has(edgeId)) {
            const srcExists = existingIds.has(edge.source) || elements.some(e => e.data.id === edge.source);
            const tgtExists = existingIds.has(edge.target) || elements.some(e => e.data.id === edge.target);
            if (srcExists && tgtExists) {
                elements.push({
                    group: 'edges',
                    data: {
                        id: edgeId,
                        source: edge.source,
                        target: edge.target,
                        type: edge.type,
                    },
                });
            }
        }
    }

    if (elements.length > 0) {
        const added = window.cy.add(elements);
        // Animate new nodes to position
        added.layout({
            name: 'cose',
            animate: true,
            animationDuration: 500,
            fit: false,
            randomize: false,
        }).run();
    }

    updateStats();
}


function showNodeDetail(cyNode) {
    const panel = document.getElementById('node-detail-panel');
    const title = document.getElementById('detail-title');
    const content = document.getElementById('detail-content');

    const data = cyNode.data();
    const label = data.label || 'Unknown';
    const color = data.color || DEFAULT_COLOR;

    title.innerHTML = `<span style="color:${color}">●</span> ${label}`;

    // Build properties table
    let html = '<table>';
    const props = data.properties || {};
    for (const [key, value] of Object.entries(props)) {
        if (value && value !== '' && value !== 'nan' && value !== 'NaN') {
            html += `<tr><td>${key}</td><td>${value}</td></tr>`;
        }
    }
    html += '</table>';
    content.innerHTML = html;

    panel.classList.add('visible');

    // Highlight connected nodes
    window.cy.elements().removeClass('highlighted faded');
    cyNode.addClass('highlighted');
    cyNode.connectedEdges().addClass('highlighted');
    cyNode.neighborhood().nodes().addClass('highlighted');

    // Fade others
    window.cy.elements().not(cyNode).not(cyNode.neighborhood()).not(cyNode.connectedEdges()).addClass('faded');
}


function hideNodeDetail() {
    document.getElementById('node-detail-panel').classList.remove('visible');
}


function updateStats() {
    document.getElementById('stat-nodes').textContent = `${window.cy.nodes().length} nodes`;
    document.getElementById('stat-edges').textContent = `${window.cy.edges().length} edges`;
}


function setupGraphControls() {
    // Close detail
    document.getElementById('close-detail').addEventListener('click', () => {
        hideNodeDetail();
        selectedNode = null;
        window.cy.elements().removeClass('highlighted faded');
    });

    // Expand node
    document.getElementById('btn-expand-node').addEventListener('click', async () => {
        if (!selectedNode) return;
        try {
            const nodeId = parseInt(selectedNode.id());
            const data = await api.expandNode(nodeId);
            addNodesToGraph(data);
        } catch (e) {
            console.error('Failed to expand node:', e);
        }
    });

    // Trace flow
    document.getElementById('btn-trace-flow').addEventListener('click', async () => {
        if (!selectedNode) return;
        const data = selectedNode.data();
        const label = data.label;
        const props = data.properties || {};

        // Find the appropriate ID
        let entityId = null;
        let entityType = label;

        for (const key of Object.keys(props)) {
            if (key.includes('_id') || key.includes('_no') || key === 'id') {
                entityId = props[key];
                break;
            }
        }

        if (entityId) {
            try {
                const flowData = await api.traceFlow(entityType, entityId);
                addNodesToGraph(flowData);
            } catch (e) {
                console.error('Failed to trace flow:', e);
            }
        }
    });

    // Refresh
    document.getElementById('btn-refresh').addEventListener('click', () => {
        window.cy.elements().remove();
        loadGraph();
    });

    // Search
    let searchTimeout;
    document.getElementById('graph-search').addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        const query = e.target.value.trim();

        if (query.length < 2) {
            window.cy.elements().removeClass('highlighted faded');
            return;
        }

        searchTimeout = setTimeout(async () => {
            try {
                const results = await api.searchNodes(query, activeFilter !== 'all' ? activeFilter : null);
                const matchIds = new Set(results.map(r => r.id));

                window.cy.elements().removeClass('highlighted faded');
                window.cy.nodes().forEach(node => {
                    if (matchIds.has(node.id())) {
                        node.addClass('highlighted');
                    } else {
                        node.addClass('faded');
                    }
                });
                window.cy.edges().addClass('faded');
            } catch (e) {
                console.error('Search failed:', e);
            }
        }, 300);
    });

    // Filter chips
    document.querySelectorAll('.chip').forEach(chip => {
        chip.addEventListener('click', () => {
            document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            activeFilter = chip.dataset.type;

            if (activeFilter === 'all') {
                window.cy.elements().removeClass('faded');
            } else {
                window.cy.nodes().forEach(node => {
                    if (node.data('nodeType') === activeFilter) {
                        node.removeClass('faded');
                        node.connectedEdges().removeClass('faded');
                    } else {
                        node.addClass('faded');
                    }
                });
            }
        });
    });
}


// Highlight nodes referenced in chat response
function highlightNodes(nodeIds) {
    if (!nodeIds || nodeIds.length === 0) return;

    window.cy.elements().removeClass('highlighted faded');

    const matchSet = new Set(nodeIds.map(String));
    let matched = false;

    window.cy.nodes().forEach(node => {
        const props = node.data('properties') || {};
        const isMatch = Object.values(props).some(v => matchSet.has(String(v)));
        if (isMatch) {
            node.addClass('highlighted');
            node.connectedEdges().addClass('highlighted');
            matched = true;
        }
    });

    if (matched) {
        // Fade non-highlighted
        window.cy.elements().not('.highlighted').addClass('faded');
    }
}


function truncate(str, maxLen) {
    if (!str) return '';
    str = String(str);
    return str.length > maxLen ? str.substring(0, maxLen) + '…' : str;
}
