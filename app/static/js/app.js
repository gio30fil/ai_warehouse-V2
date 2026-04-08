/* ═══════════════════════════════════════════════════════════
   IFSAS AI Warehouse v2 — Main JavaScript
   AJAX search, toast notifications, offer management
   ═══════════════════════════════════════════════════════════ */

// ── Toast Notifications ──────────────────────────────────

function showToast(message, type = 'info') {
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icons = { success: '✅', error: '❌', info: 'ℹ️' };
    toast.innerHTML = `
        <span>${icons[type] || 'ℹ️'}</span>
        <span>${message}</span>
        <button class="toast-close" onclick="this.parentElement.remove()">×</button>
    `;

    container.appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
}


// ── AJAX Search ──────────────────────────────────────────

async function performSearch() {
    const queryInput = document.getElementById('searchQuery');
    const categorySelect = document.getElementById('searchCategory');
    const searchBtn = document.getElementById('searchBtn');
    const resultsContainer = document.getElementById('resultsContainer');
    const advisorContainer = document.getElementById('advisorContainer');

    if (!queryInput) return;

    const query = queryInput.value.trim();
    if (!query) return;

    // Show loading state
    searchBtn.disabled = true;
    searchBtn.innerHTML = '<span class="spinner"></span> Αναζήτηση...';

    resultsContainer.innerHTML = `
        <div class="skeleton skeleton-card"></div>
        <div class="skeleton skeleton-card"></div>
        <div class="skeleton skeleton-card"></div>
    `;
    advisorContainer.innerHTML = '';

    try {
        const res = await fetch('/api/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: query,
                category: categorySelect ? categorySelect.value : 'all',
            }),
        });

        const data = await res.json();

        if (!data.success) {
            showToast(data.error || 'Σφάλμα αναζήτησης', 'error');
            resultsContainer.innerHTML = '';
            return;
        }

        if (data.not_related) {
            resultsContainer.innerHTML = `
                <div class="empty-state">
                    <span class="icon">🤔</span>
                    <h3>Η αναζήτηση δεν σχετίζεται με προϊόντα</h3>
                    <p class="text-dim mt-md">Δοκιμάστε μια αναζήτηση σχετική με συστήματα ασφαλείας, π.χ. "κάμερα dome 4mp"</p>
                </div>
            `;
            return;
        }

        if (!data.products || data.products.length === 0) {
            resultsContainer.innerHTML = `
                <div class="empty-state">
                    <span class="icon">🔍</span>
                    <h3>Δεν βρέθηκαν προϊόντα</h3>
                    <p class="text-dim mt-md">Δοκιμάστε διαφορετικούς όρους αναζήτησης.</p>
                </div>
            `;
            return;
        }

        // Render products
        renderProducts(data.products, resultsContainer);

        // Load advisor asynchronously (non-blocking)
        loadAdvisor(query, data.products, advisorContainer);

    } catch (err) {
        showToast('Σφάλμα σύνδεσης', 'error');
        resultsContainer.innerHTML = '';
    } finally {
        searchBtn.disabled = false;
        searchBtn.innerHTML = '🔎 Αναζήτηση';
    }
}


function renderProducts(products, container) {
    container.innerHTML = '';

    products.forEach((p, index) => {
        const stockVal = p.stock !== null ? parseFloat(p.stock) : 0;
        // If available_stock is null/undefined, it means we don't have info, 
        // but we should check if the field itself is missing.
        const availableStockVal = (p.available_stock !== null && p.available_stock !== undefined) ? parseFloat(p.available_stock) : stockVal;
        
        let stockBadge = '';
        if (stockVal > 10) {
            stockBadge = `<span class="badge badge-stock-high">Phys: ${stockVal.toFixed(0)} | Avail: ${availableStockVal.toFixed(0)}</span>`;
        } else if (stockVal > 0) {
            stockBadge = `<span class="badge badge-stock-low">Phys: ${stockVal.toFixed(0)} | Avail: ${availableStockVal.toFixed(0)}</span>`;
        } else {
            stockBadge = `<span class="badge badge-stock-none">Out of Stock</span>`;
        }

        const card = document.createElement('div');
        card.className = 'product-card';
        card.style.animationDelay = `${index * 0.05}s`;
        card.style.animation = 'slideIn 0.4s ease-out backwards';

        card.innerHTML = `
            <div class="product-header">
                <div class="product-info">
                    <div class="product-meta">S1 Code: ${p.kodikos} | Factory: ${p.factory_code}</div>
                    <h4>${p.description}</h4>
                    <div class="product-category">${p.category} / ${p.subcategory}</div>
                </div>
                <div class="text-right">
                    <div class="product-score">Score: ${p.score.toFixed(3)}</div>
                    <a href="javascript:void(0)" class="stock-link" onclick="goToStock('${p.kodikos}')">
                        ${stockBadge}
                    </a>
                </div>
            </div>
            <div class="product-actions">
                <button class="btn btn-success btn-sm"
                        data-factory="${p.factory_code}"
                        data-description="${p.description}"
                        onclick="handleAddOffer(this)">
                    ➕ Προσθήκη
                </button>
            </div>
        `;

        container.appendChild(card);
    });
}


async function loadAdvisor(query, products, container) {
    try {
        const res = await fetch('/api/advisor', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, products: products.slice(0, 5) }),
        });
        const data = await res.json();

        if (data.advisor) {
            container.innerHTML = `
                <div class="advisor-box">
                    <div class="advisor-header">
                        <span>🤖</span>
                        <span>AI Σύμβουλος</span>
                    </div>
                    ${data.advisor}
                </div>
            `;
        }
    } catch (e) {
        // Advisor is optional, fail silently
    }
}


// ── Navigation ───────────────────────────────────────────

function goToStock(code) {
    window.location.href = `/admin/stock?search=${code}`;
}


// ── Stock Modal ──────────────────────────────────────────

function showStockModal() {
    const modal = document.getElementById('stockModal');
    if (modal) {
        modal.classList.add('active');
        loadLocalProducts();
    }
}

function closeModal() {
    const modal = document.getElementById('stockModal');
    if (modal) modal.classList.remove('active');
}

async function loadLocalProducts() {
    const body = document.getElementById('stockTableBody');
    if (!body) return;

    body.innerHTML = '<tr><td colspan="3" class="text-center" style="padding: 3rem;">Φόρτωση δεδομένων...</td></tr>';

    try {
        const res = await fetch('/api/products');
        const data = await res.json();
        renderStockTable(data);
    } catch (err) {
        body.innerHTML = '<tr><td colspan="3" class="text-center" style="color: var(--accent-red);">Σφάλμα φόρτωσης.</td></tr>';
    }
}

function renderStockTable(products) {
    const body = document.getElementById('stockTableBody');
    if (!body) return;
    body.innerHTML = '';

    if (products.length === 0) {
        body.innerHTML = '<tr><td colspan="3" class="text-center" style="padding: 3rem;">Δεν βρέθηκαν προϊόντα.</td></tr>';
        return;
    }

    products.forEach(p => {
        const row = body.insertRow();
        const stockVal = p.stock !== null ? parseFloat(p.stock) : 0;
        const availableStockVal = (p.available_stock !== null && p.available_stock !== undefined) ? parseFloat(p.available_stock) : stockVal;

        let stockBadge = '';
        if (stockVal > 10) stockBadge = `<span class="badge badge-stock-high">Phys: ${stockVal.toFixed(0)} | Avail: ${availableStockVal.toFixed(0)}</span>`;
        else if (stockVal > 0) stockBadge = `<span class="badge badge-stock-low">Phys: ${stockVal.toFixed(0)} | Avail: ${availableStockVal.toFixed(0)}</span>`;
        else stockBadge = `<span class="badge" style="background: rgba(255,255,255,0.05); color: var(--text-muted);">Phys: 0 | Avail: 0</span>`;

        row.innerHTML = `
            <td><span class="badge badge-code">${p.code}</span></td>
            <td class="fw-500">${p.description}</td>
            <td class="text-center">${stockBadge}</td>
        `;
    });
}

function filterModalTable() {
    const input = document.getElementById('modalSearch');
    const filter = input.value.toUpperCase();
    const table = document.getElementById('stockTable');
    const tr = table.getElementsByTagName('tr');

    for (let i = 1; i < tr.length; i++) {
        const text = tr[i].textContent.toUpperCase();
        tr[i].style.display = text.indexOf(filter) > -1 ? '' : 'none';
    }
}


// ── Live Stock Fetch ─────────────────────────────────────

async function fetchLiveStock() {
    const btn = document.getElementById('fetchStockBtn');
    if (!btn) return;

    const originalContent = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Ενημέρωση...';

    try {
        const res = await fetch('/api/fetch_stock', { method: 'POST' });
        const data = await res.json();

        if (data.success) {
            showToast(data.message, 'success');
            loadLocalProducts();
        } else {
            showToast('Σφάλμα: ' + data.error, 'error');
        }
    } catch (err) {
        showToast('Σφάλμα σύνδεσης', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalContent;
    }
}


// ── SoftOne Sync ─────────────────────────────────────────

async function syncSoftOne() {
    const btn = document.getElementById('syncBtn');
    if (!btn) return;

    const defaultDate = new Date();
    defaultDate.setDate(defaultDate.getDate() - 30); // Default to last 30 days
    const defaultDateStr = defaultDate.toISOString().split('T')[0];

    const upddate_from = prompt("Εισάγετε ημερομηνία από την οποία θα αντληθούν τα προϊόντα (ΕΕΕΕ-ΜΜ-ΗΗ):", defaultDateStr);
    if (upddate_from === null) return; // User cancelled
    
    // Basic format validation
    if (!/^\d{4}-\d{2}-\d{2}$/.test(upddate_from)) {
        showToast("Μη έγκυρη μορφή ημερομηνίας. Πρέπει να είναι ΕΕΕΕ-ΜΜ-ΗΗ.", "error");
        return;
    }

    const payloadDate = upddate_from + "T00:00:00";

    const originalContent = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Syncing...';

    try {
        const res = await fetch('/api/sync', { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ upddate_from: payloadDate })
        });
        const data = await res.json();

        if (data.success) {
            showToast(data.message, 'success');
        } else {
            showToast('Error: ' + data.error, 'error');
        }
    } catch (err) {
        showToast('Connection error', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalContent;
    }
}

async function generateEmbeddings() {
    const btn = document.getElementById('embedBtn');
    if (!btn) return;

    if (!confirm('Θέλετε να δημιουργήσετε AI embeddings για τα νέα προϊόντα; Αυτή η διαδικασία παρασκηνίου μπορεί να πάρει κάποιο χρόνο (μέσω OpenAI API).')) {
        return;
    }

    const originalContent = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Working...';

    try {
        showToast('Η δημιουργία AI embeddings ξεκίνησε. Μπορείτε να δείτε την πρόοδο στην κονσόλα.', 'info');
        const res = await fetch('/api/generate_embeddings', { method: 'POST' });
        const data = await res.json();

        if (data.success) {
            showToast(data.message, 'success');
        } else {
            showToast('Error: ' + data.error, 'error');
        }
    } catch (err) {
        showToast('Connection error', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalContent;
    }
}

// ── Offer Functions ──────────────────────────────────────

function handleAddOffer(btn) {
    const factory = btn.getAttribute('data-factory');
    const desc = btn.getAttribute('data-description');
    addToOffer(factory, desc);
}

function addToOffer(code, desc) {
    const list = document.getElementById('offerList');
    const emptyState = document.getElementById('offerEmptyState');
    if (!list) return;

    const li = document.createElement('li');
    li.className = 'offer-item';
    li.innerHTML = `
        <div>
            <strong style="color: var(--primary);">${code}</strong> — ${desc}
        </div>
        <button class="remove-btn" onclick="removeItem(this)">✕</button>
    `;
    list.appendChild(li);
    if (emptyState) emptyState.style.display = 'none';
}

function removeItem(button) {
    button.parentElement.remove();
    const list = document.getElementById('offerList');
    const emptyState = document.getElementById('offerEmptyState');
    if (list && list.children.length === 0 && emptyState) {
        emptyState.style.display = 'block';
    }
}

function clearOffer() {
    const list = document.getElementById('offerList');
    const emptyState = document.getElementById('offerEmptyState');
    if (list) list.innerHTML = '';
    if (emptyState) emptyState.style.display = 'block';
}


// ── PDF Export ────────────────────────────────────────────

async function exportPdf() {
    const items = document.querySelectorAll('#offerList .offer-item');
    if (items.length === 0) {
        showToast('Η λίστα είναι άδεια!', 'error');
        return;
    }

    const btn = document.getElementById('exportPdfBtn');
    if (btn) btn.disabled = true;

    const products = [];
    items.forEach(i => {
        const clone = i.cloneNode(true);
        clone.querySelector('.remove-btn').remove();
        products.push(clone.textContent.trim());
    });

    try {
        const res = await fetch('/export_pdf', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(products),
        });
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'προσφορά.pdf';
        a.click();
        showToast('PDF εξαγωγή ολοκληρώθηκε!', 'success');
    } catch (err) {
        showToast('Σφάλμα εξαγωγής PDF', 'error');
    } finally {
        if (btn) btn.disabled = false;
    }
}


// ── Event Listeners ──────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    // Search form submit
    const searchForm = document.getElementById('searchForm');
    if (searchForm) {
        searchForm.addEventListener('submit', (e) => {
            e.preventDefault();
            performSearch();
        });
    }

    // Enter key on search input
    const searchQuery = document.getElementById('searchQuery');
    if (searchQuery) {
        searchQuery.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                performSearch();
            }
        });
    }

    // PDF export button
    const exportBtn = document.getElementById('exportPdfBtn');
    if (exportBtn) {
        exportBtn.addEventListener('click', exportPdf);
    }

    // Modal close on outside click
    const modal = document.getElementById('stockModal');
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) closeModal();
        });
    }

    // Stock list page auto-search
    const inventorySearch = document.getElementById('inventorySearch');
    if (inventorySearch) {
        inventorySearch.addEventListener('input', function (e) {
            const term = e.target.value.toLowerCase();
            const rows = document.querySelectorAll('#inventoryTable tbody tr');
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(term) ? '' : 'none';
            });
        });

        // Auto-search from URL parameter
        const urlParams = new URLSearchParams(window.location.search);
        const searchTerm = urlParams.get('search');
        if (searchTerm) {
            inventorySearch.value = searchTerm;
            inventorySearch.dispatchEvent(new Event('input'));
            const firstMatch = document.querySelector('#inventoryTable tbody tr:not([style*="display: none"])');
            if (firstMatch) {
                firstMatch.scrollIntoView({ behavior: 'smooth', block: 'center' });
                firstMatch.style.backgroundColor = 'rgba(99, 102, 241, 0.1)';
                setTimeout(() => {
                    firstMatch.style.transition = 'background-color 2s';
                    firstMatch.style.backgroundColor = '';
                }, 2000);
            }
        }
    }

    // Global search (softone data page)
    const globalSearch = document.getElementById('globalSearch');
    if (globalSearch) {
        globalSearch.addEventListener('input', function (e) {
            const term = e.target.value.toLowerCase();
            const rows = document.querySelectorAll('tbody tr');
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(term) ? '' : 'none';
            });
        });
    }
});
