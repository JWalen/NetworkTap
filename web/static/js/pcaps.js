/* NetworkTap - PCAP File Browser with Filtering and Packet Viewer */

const Pcaps = (() => {
    let selectedFile = null;
    let filterVisible = false;

    // Packet viewer state
    let viewerFile = null;

    // Helper to encode file paths for API URLs
    function encodePath(filePath) {
        return filePath.split('/').map(encodeURIComponent).join('/');
    }
    let viewerOffset = 0;
    let viewerLimit = 50;
    let viewerTotal = 0;
    let viewerFilter = '';
    let expandedPacket = null;

    async function render(container) {
        container.innerHTML = `
            <div class="stat-grid">
                <div class="stat-card">
                    <span class="stat-label">Total Files</span>
                    <span class="stat-value" id="pcap-count">--</span>
                </div>
                <div class="stat-card">
                    <span class="stat-label">Total Size</span>
                    <span class="stat-value" id="pcap-total-size">--</span>
                </div>
                <div class="stat-card" style="grid-column: span 2">
                    <span class="stat-label">Storage Usage</span>
                    <div class="storage-bar" style="margin-top:8px">
                        <div class="storage-bar-fill" id="storage-fill" style="width:0%"></div>
                        <span class="storage-bar-label" id="storage-label">0%</span>
                    </div>
                    <span class="stat-sub" id="storage-detail" style="margin-top:8px"></span>
                </div>
            </div>

            <!-- Packet Viewer Panel -->
            <div class="packet-viewer-panel" id="packet-viewer" style="display:none">
                <div class="packet-viewer-header">
                    <div class="packet-viewer-title">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.66 0 3-4.03 3-9s-1.34-9-3-9m0 18c-1.66 0-3-4.03-3-9s1.34-9 3-9m-9 9a9 9 0 019-9"/>
                        </svg>
                        <span>Packet Viewer: <span id="viewer-filename" class="accent-text"></span></span>
                        <span class="packet-viewer-count" id="viewer-count"></span>
                    </div>
                    <div class="packet-viewer-controls">
                        <input type="text" id="viewer-filter" class="packet-filter-input" placeholder="Display filter (e.g. tcp.port == 443)">
                        <button class="btn btn-sm btn-secondary" onclick="Pcaps.applyViewerFilter()">Filter</button>
                        <button class="btn btn-sm btn-secondary" onclick="Pcaps.showStreams()">Streams</button>
                        <button class="btn btn-sm btn-secondary" onclick="Pcaps.closeViewer()">Close</button>
                    </div>
                </div>
                <div class="packet-list-wrapper" id="packet-list">
                    ${skeletonTable(10, 7)}
                </div>
                <div class="packet-viewer-pagination" id="viewer-pagination"></div>
            </div>

            <!-- Stream Viewer Modal -->
            <div class="modal-overlay" id="stream-modal" style="display:none" onclick="Pcaps.closeStreamModal(event)">
                <div class="modal-content stream-modal-content" onclick="event.stopPropagation()">
                    <div class="modal-header">
                        <h3>TCP/UDP Streams</h3>
                        <button class="modal-close" onclick="Pcaps.closeStreamModal()">&times;</button>
                    </div>
                    <div class="modal-body" id="stream-modal-body">
                        <div class="loading"><div class="spinner"></div></div>
                    </div>
                </div>
            </div>

            <!-- Packet Detail Modal -->
            <div class="modal-overlay" id="packet-detail-modal" style="display:none" onclick="Pcaps.closePacketDetail(event)">
                <div class="modal-content packet-detail-content" onclick="event.stopPropagation()">
                    <div class="modal-header">
                        <h3>Packet #<span id="detail-frame-num"></span></h3>
                        <button class="modal-close" onclick="Pcaps.closePacketDetail()">&times;</button>
                    </div>
                    <div class="modal-body" id="packet-detail-body">
                        <div class="loading"><div class="spinner"></div></div>
                    </div>
                </div>
            </div>

            <!-- Filter Panel -->
            <div class="pcap-filter-panel" id="filter-panel" style="display:none">
                <div class="pcap-filter-header">
                    <h3>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>
                        </svg>
                        Filter PCAP: <span id="filter-filename" style="color:var(--accent)"></span>
                    </h3>
                    <button class="btn btn-sm btn-secondary" onclick="Pcaps.hideFilter()">Close</button>
                </div>

                <div class="bpf-builder">
                    <div class="filter-group">
                        <label>Source IP</label>
                        <input type="text" id="filter-src-ip" placeholder="e.g. 192.168.1.1">
                    </div>
                    <div class="filter-group">
                        <label>Destination IP</label>
                        <input type="text" id="filter-dst-ip" placeholder="e.g. 10.0.0.1">
                    </div>
                    <div class="filter-group">
                        <label>Source Port</label>
                        <input type="number" id="filter-src-port" placeholder="e.g. 443">
                    </div>
                    <div class="filter-group">
                        <label>Destination Port</label>
                        <input type="number" id="filter-dst-port" placeholder="e.g. 80">
                    </div>
                    <div class="filter-group">
                        <label>Protocol</label>
                        <select id="filter-protocol">
                            <option value="">Any</option>
                            <option value="tcp">TCP</option>
                            <option value="udp">UDP</option>
                            <option value="icmp">ICMP</option>
                            <option value="arp">ARP</option>
                        </select>
                    </div>
                </div>

                <div class="bpf-or-divider">OR enter raw BPF filter</div>

                <div class="filter-group">
                    <input type="text" id="filter-raw" class="bpf-raw" placeholder="e.g. tcp port 443 and host 192.168.1.1">
                    <div class="form-help" style="margin-top:4px">
                        Raw BPF filter overrides individual fields above.
                        <a href="https://www.tcpdump.org/manpages/pcap-filter.7.html" target="_blank" style="color:var(--accent)">BPF syntax reference</a>
                    </div>
                </div>

                <div class="filter-preview" id="filter-preview" style="display:none">
                    <span class="filter-preview-count" id="preview-count">0</span>
                    <span class="filter-preview-label">packets match filter</span>
                    <div class="filter-preview-actions">
                        <button class="btn btn-secondary btn-sm" onclick="Pcaps.previewFilter()" id="btn-preview">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <circle cx="11" cy="11" r="8"/>
                                <line x1="21" y1="21" x2="16.65" y2="16.65"/>
                            </svg>
                            Preview
                        </button>
                        <button class="btn btn-primary btn-sm" onclick="Pcaps.downloadFiltered()" id="btn-download-filtered" disabled>
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                                <polyline points="7 10 12 15 17 10"/>
                                <line x1="12" y1="15" x2="12" y2="3"/>
                            </svg>
                            Download Filtered
                        </button>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <span class="card-title">Capture Files</span>
                    <button class="btn btn-sm btn-secondary" id="btn-refresh-pcaps">Refresh</button>
                </div>
                <div id="pcap-list">
                    ${skeleton('row', 5)}
                </div>
            </div>
        `;

        document.getElementById('btn-refresh-pcaps').addEventListener('click', refresh);

        // Filter input listeners
        const filterInputs = ['filter-src-ip', 'filter-dst-ip', 'filter-src-port', 'filter-dst-port', 'filter-protocol', 'filter-raw'];
        filterInputs.forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.addEventListener('input', debounce(showPreviewSection, 300));
                el.addEventListener('change', debounce(showPreviewSection, 300));
            }
        });

        // Viewer filter on enter
        document.getElementById('viewer-filter').addEventListener('keydown', e => {
            if (e.key === 'Enter') applyViewerFilter();
        });

        await refresh();
        App.setRefresh(refresh, 15000);
    }

    async function refresh() {
        try {
            const [pcaps, system] = await Promise.all([
                api('/api/pcaps/'),
                api('/api/system/status'),
            ]);

            updateStats(pcaps, system);
            updateFileList(pcaps.files || []);
        } catch (e) {
            console.error('Failed to refresh pcaps:', e);
        }
    }

    function updateStats(pcaps, system) {
        animateValue(document.getElementById('pcap-count'), pcaps.count || 0, v => v.toString());
        animateValue(document.getElementById('pcap-total-size'), pcaps.total_size || 0, formatBytes);

        const sys = system.system;
        if (sys) {
            const pct = Math.round(sys.disk_percent);
            document.getElementById('storage-fill').style.width = pct + '%';
            document.getElementById('storage-label').textContent = pct + '%';
            document.getElementById('storage-detail').textContent =
                `${formatBytes(sys.disk_used)} used of ${formatBytes(sys.disk_total)} (${formatBytes(sys.disk_free)} free)`;
        }
    }

    function updateFileList(files) {
        const el = document.getElementById('pcap-list');

        if (files.length === 0) {
            el.innerHTML = `
                <div class="empty-state">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                    </svg>
                    <h3>No capture files</h3>
                    <p>Start a capture to generate PCAP files</p>
                </div>
            `;
            return;
        }

        el.innerHTML = files.map(f => `
            <div class="file-item">
                <div class="file-icon">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                    </svg>
                </div>
                <div class="file-info">
                    <div class="file-name">${escapeHtml(f.name)}</div>
                    <div class="file-meta">
                        ${formatBytes(f.size)} &middot; ${formatDate(f.modified)}
                    </div>
                </div>
                <button class="btn btn-sm btn-accent" onclick="Pcaps.openViewer('${escapeHtml(f.path)}')" title="View packets">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/>
                        <line x1="2" y1="12" x2="22" y2="12"/>
                        <path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/>
                    </svg>
                    View
                </button>
                <button class="btn btn-sm btn-secondary" onclick="Pcaps.showFilter('${escapeHtml(f.path)}')" title="Filter packets">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>
                    </svg>
                </button>
                <button class="btn btn-sm btn-primary" onclick="Pcaps.download('${escapeHtml(f.path)}')">
                    Download
                </button>
            </div>
        `).join('');
    }

    // ══════════════════════════════════════════════════════════════════════════
    // PACKET VIEWER
    // ══════════════════════════════════════════════════════════════════════════

    async function openViewer(filePath) {
        viewerFile = filePath;
        viewerOffset = 0;
        viewerFilter = '';
        expandedPacket = null;

        const panel = document.getElementById('packet-viewer');
        panel.style.display = 'block';
        document.getElementById('viewer-filename').textContent = filePath.split('/').pop();
        document.getElementById('viewer-filter').value = '';

        panel.scrollIntoView({ behavior: 'smooth', block: 'start' });

        await loadPackets();
    }

    function closeViewer() {
        document.getElementById('packet-viewer').style.display = 'none';
        viewerFile = null;
    }

    async function loadPackets() {
        const listEl = document.getElementById('packet-list');
        listEl.innerHTML = skeletonTable(10, 7);

        try {
            const params = new URLSearchParams({
                offset: viewerOffset,
                limit: viewerLimit,
            });
            if (viewerFilter) params.set('filter', viewerFilter);

            const encodedPath = encodePath(viewerFile);
            const data = await api(`/api/pcaps/${encodedPath}/packets?${params}`);

            viewerTotal = data.total;
            document.getElementById('viewer-count').textContent =
                `(${viewerTotal.toLocaleString()} packets)`;

            renderPacketList(data.packets);
            renderViewerPagination();

        } catch (e) {
            listEl.innerHTML = `<div class="empty-state"><p>Error loading packets: ${escapeHtml(e.message)}</p></div>`;
        }
    }

    function renderPacketList(packets) {
        const listEl = document.getElementById('packet-list');

        if (!packets || packets.length === 0) {
            listEl.innerHTML = `
                <div class="empty-state">
                    <p>No packets ${viewerFilter ? 'match filter' : 'found'}</p>
                </div>
            `;
            return;
        }

        listEl.innerHTML = `
            <table class="packet-table">
                <thead>
                    <tr>
                        <th>No.</th>
                        <th>Time</th>
                        <th>Source</th>
                        <th>Destination</th>
                        <th>Protocol</th>
                        <th>Length</th>
                        <th>Info</th>
                    </tr>
                </thead>
                <tbody>
                    ${packets.map(p => `
                        <tr class="packet-row ${p.protocol ? p.protocol.toLowerCase() : ''}"
                            onclick="Pcaps.showPacketDetail(${p.number})">
                            <td class="pkt-num">${p.number}</td>
                            <td class="pkt-time">${p.time.toFixed(6)}</td>
                            <td class="pkt-addr">${escapeHtml(p.src_ip || '')}${p.src_port ? ':' + p.src_port : ''}</td>
                            <td class="pkt-addr">${escapeHtml(p.dst_ip || '')}${p.dst_port ? ':' + p.dst_port : ''}</td>
                            <td class="pkt-proto"><span class="proto-badge proto-${(p.protocol || '').toLowerCase()}">${escapeHtml(p.protocol || '-')}</span></td>
                            <td class="pkt-len">${p.length}</td>
                            <td class="pkt-info" title="${escapeHtml(p.info || '')}">${escapeHtml((p.info || '').substring(0, 80))}${(p.info || '').length > 80 ? '...' : ''}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    function renderViewerPagination() {
        const totalPages = Math.ceil(viewerTotal / viewerLimit);
        const currentPage = Math.floor(viewerOffset / viewerLimit) + 1;

        renderPagination(
            document.getElementById('viewer-pagination'),
            currentPage,
            totalPages,
            (page) => {
                viewerOffset = (page - 1) * viewerLimit;
                loadPackets();
            }
        );
    }

    function applyViewerFilter() {
        viewerFilter = document.getElementById('viewer-filter').value.trim();
        viewerOffset = 0;
        loadPackets();
    }

    async function showPacketDetail(frameNumber) {
        const modal = document.getElementById('packet-detail-modal');
        const body = document.getElementById('packet-detail-body');

        modal.style.display = 'flex';
        document.getElementById('detail-frame-num').textContent = frameNumber;
        body.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

        try {
            const encodedPath = encodePath(viewerFile);
            const data = await api(`/api/pcaps/${encodedPath}/packets/${frameNumber}`);

            let html = '<div class="packet-detail">';

            // Layer accordion
            html += '<div class="packet-layers">';
            (data.layers || []).forEach((layer, i) => {
                html += `
                    <div class="layer-section">
                        <div class="layer-header" onclick="this.parentElement.classList.toggle('expanded')">
                            <svg class="layer-chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="9 18 15 12 9 6"/>
                            </svg>
                            <span class="layer-name">${escapeHtml(layer.name)}</span>
                            <span class="layer-field-count">${layer.fields.length} fields</span>
                        </div>
                        <div class="layer-fields">
                            ${layer.fields.map(f => `
                                <div class="layer-field">
                                    <span class="field-name">${escapeHtml(f.name)}:</span>
                                    <span class="field-value">${escapeHtml(Array.isArray(f.value) ? f.value.join(', ') : String(f.value))}</span>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                `;
            });
            html += '</div>';

            // Hex dump
            if (data.hex_dump) {
                html += `
                    <div class="hex-dump-section">
                        <h4>Hex Dump</h4>
                        <pre class="hex-dump">${escapeHtml(data.hex_dump)}</pre>
                    </div>
                `;
            }

            html += '</div>';
            body.innerHTML = html;

            // Expand first layer by default
            const firstLayer = body.querySelector('.layer-section');
            if (firstLayer) firstLayer.classList.add('expanded');

        } catch (e) {
            body.innerHTML = `<div class="empty-state"><p>Error: ${escapeHtml(e.message)}</p></div>`;
        }
    }

    function closePacketDetail(event) {
        if (!event || event.target === document.getElementById('packet-detail-modal')) {
            document.getElementById('packet-detail-modal').style.display = 'none';
        }
    }

    // ══════════════════════════════════════════════════════════════════════════
    // STREAM VIEWER
    // ══════════════════════════════════════════════════════════════════════════

    async function showStreams() {
        if (!viewerFile) return;

        const modal = document.getElementById('stream-modal');
        const body = document.getElementById('stream-modal-body');

        modal.style.display = 'flex';
        body.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

        try {
            const encodedPath = encodePath(viewerFile);
            const data = await api(`/api/pcaps/${encodedPath}/streams`);

            if (!data.streams || data.streams.length === 0) {
                body.innerHTML = '<div class="empty-state"><p>No streams found</p></div>';
                return;
            }

            body.innerHTML = `
                <div class="stream-list">
                    <table class="stream-table">
                        <thead>
                            <tr>
                                <th>Type</th>
                                <th>Source</th>
                                <th>Destination</th>
                                <th>Frames</th>
                                <th>Bytes</th>
                                <th></th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.streams.map((s, i) => `
                                <tr>
                                    <td><span class="proto-badge proto-${s.type}">${s.type.toUpperCase()}</span></td>
                                    <td class="stream-addr">${escapeHtml(s.src)}</td>
                                    <td class="stream-addr">${escapeHtml(s.dst)}</td>
                                    <td>${s.frames}</td>
                                    <td>${escapeHtml(s.bytes)}</td>
                                    <td>
                                        <button class="btn btn-xs btn-secondary" onclick="Pcaps.followStream('${s.type}', ${i})">
                                            Follow
                                        </button>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
                <div class="stream-content-wrapper" id="stream-content" style="display:none">
                    <div class="stream-content-header">
                        <h4 id="stream-content-title">Stream Content</h4>
                        <div class="stream-format-selector">
                            <button class="btn btn-xs active" data-format="ascii" onclick="Pcaps.changeStreamFormat('ascii')">ASCII</button>
                            <button class="btn btn-xs" data-format="hex" onclick="Pcaps.changeStreamFormat('hex')">Hex</button>
                        </div>
                    </div>
                    <pre class="stream-content" id="stream-content-pre"></pre>
                </div>
            `;
        } catch (e) {
            body.innerHTML = `<div class="empty-state"><p>Error: ${escapeHtml(e.message)}</p></div>`;
        }
    }

    let currentStreamType = null;
    let currentStreamId = null;

    async function followStream(type, index) {
        currentStreamType = type;
        currentStreamId = index;

        const contentWrapper = document.getElementById('stream-content');
        const contentPre = document.getElementById('stream-content-pre');
        const title = document.getElementById('stream-content-title');

        contentWrapper.style.display = 'block';
        contentPre.textContent = 'Loading...';
        title.textContent = `${type.toUpperCase()} Stream #${index}`;

        try {
            const encodedPath = encodePath(viewerFile);
            const data = await api(`/api/pcaps/${encodedPath}/streams/${type}/${index}?format=ascii`);
            contentPre.textContent = data.content || '(empty)';
        } catch (e) {
            contentPre.textContent = 'Error: ' + e.message;
        }
    }

    async function changeStreamFormat(format) {
        if (currentStreamType === null) return;

        // Update button states
        document.querySelectorAll('.stream-format-selector button').forEach(b => {
            b.classList.toggle('active', b.dataset.format === format);
        });

        const contentPre = document.getElementById('stream-content-pre');
        contentPre.textContent = 'Loading...';

        try {
            const encodedPath = encodePath(viewerFile);
            const data = await api(`/api/pcaps/${encodedPath}/streams/${currentStreamType}/${currentStreamId}?format=${format}`);
            contentPre.textContent = data.content || '(empty)';
        } catch (e) {
            contentPre.textContent = 'Error: ' + e.message;
        }
    }

    function closeStreamModal(event) {
        if (!event || event.target === document.getElementById('stream-modal')) {
            document.getElementById('stream-modal').style.display = 'none';
            currentStreamType = null;
            currentStreamId = null;
        }
    }

    // ══════════════════════════════════════════════════════════════════════════
    // FILTER PANEL (existing functionality)
    // ══════════════════════════════════════════════════════════════════════════

    function showFilter(filePath) {
        selectedFile = filePath;
        const panel = document.getElementById('filter-panel');
        panel.style.display = 'block';
        document.getElementById('filter-filename').textContent = filePath.split('/').pop();

        // Clear previous filter values
        document.getElementById('filter-src-ip').value = '';
        document.getElementById('filter-dst-ip').value = '';
        document.getElementById('filter-src-port').value = '';
        document.getElementById('filter-dst-port').value = '';
        document.getElementById('filter-protocol').value = '';
        document.getElementById('filter-raw').value = '';

        // Reset preview
        document.getElementById('filter-preview').style.display = 'none';
        document.getElementById('preview-count').textContent = '0';
        document.getElementById('btn-download-filtered').disabled = true;

        panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
        filterVisible = true;
    }

    function hideFilter() {
        document.getElementById('filter-panel').style.display = 'none';
        selectedFile = null;
        filterVisible = false;
    }

    function showPreviewSection() {
        const hasFilter = getFilterParams().toString() !== '';
        document.getElementById('filter-preview').style.display = hasFilter ? 'flex' : 'none';
        document.getElementById('btn-download-filtered').disabled = true;
        document.getElementById('preview-count').textContent = '?';
    }

    function getFilterParams() {
        const params = new URLSearchParams();

        const raw = document.getElementById('filter-raw').value.trim();
        if (raw) {
            params.set('filter', raw);
            return params;
        }

        const srcIp = document.getElementById('filter-src-ip').value.trim();
        const dstIp = document.getElementById('filter-dst-ip').value.trim();
        const srcPort = document.getElementById('filter-src-port').value.trim();
        const dstPort = document.getElementById('filter-dst-port').value.trim();
        const protocol = document.getElementById('filter-protocol').value;

        if (srcIp) params.set('src_ip', srcIp);
        if (dstIp) params.set('dst_ip', dstIp);
        if (srcPort) params.set('src_port', srcPort);
        if (dstPort) params.set('dst_port', dstPort);
        if (protocol) params.set('protocol', protocol);

        return params;
    }

    async function previewFilter() {
        if (!selectedFile) return;

        const btn = document.getElementById('btn-preview');
        const countEl = document.getElementById('preview-count');

        btn.disabled = true;
        btn.innerHTML = '<div class="spinner" style="width:14px;height:14px;border-width:2px"></div> Counting...';
        countEl.textContent = '...';

        try {
            const params = getFilterParams();
            const data = await api(`/api/pcaps/${encodeURIComponent(selectedFile)}/count?${params}`);

            countEl.textContent = data.matching_packets.toLocaleString();
            document.getElementById('btn-download-filtered').disabled = data.matching_packets === 0;

            if (data.matching_packets === 0) {
                toast('No packets match the filter', 'warning');
            }
        } catch (e) {
            countEl.textContent = 'Error';
            toast('Failed to count packets: ' + e.message, 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = `
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="11" cy="11" r="8"/>
                    <line x1="21" y1="21" x2="16.65" y2="16.65"/>
                </svg>
                Preview
            `;
        }
    }

    async function downloadFiltered() {
        if (!selectedFile) return;

        const params = getFilterParams();
        const url = `/api/pcaps/${encodeURIComponent(selectedFile)}/filter?${params}`;

        await downloadWithAuth(url, `filtered_${selectedFile.split('/').pop()}`);
    }

    function download(path) {
        const url = `/api/pcaps/${encodeURIComponent(path)}/download`;
        downloadWithAuth(url, path.split('/').pop());
    }

    async function downloadWithAuth(url, filename) {
        const config = Settings.getCredentials();
        const auth = btoa(config.user + ':' + config.pass);

        try {
            const resp = await fetch(url, {
                headers: { 'Authorization': 'Basic ' + auth },
            });

            if (!resp.ok) {
                throw new Error('Download failed: ' + resp.statusText);
            }

            const blob = await resp.blob();
            const blobUrl = URL.createObjectURL(blob);

            const a = document.createElement('a');
            a.href = blobUrl;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(blobUrl);

            toast('Download started', 'success');
        } catch (e) {
            toast('Download failed: ' + e.message, 'error');
        }
    }

    return {
        render,
        download,
        showFilter,
        hideFilter,
        previewFilter,
        downloadFiltered,
        openViewer,
        closeViewer,
        applyViewerFilter,
        showPacketDetail,
        closePacketDetail,
        showStreams,
        closeStreamModal,
        followStream,
        changeStreamFormat,
    };
})();
