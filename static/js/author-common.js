/*
 * Shared by the author profile (templates/author.html) and the author works
 * page (templates/author_works.html): HTML helpers, work rendering, links to
 * the filtered works page and the "view all" facet dialog.
 */

const MAX_LISTED_AUTHORS = 6;

const svgIcon = paths => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths}</svg>`;
const ICONS = {
    pdf: svgIcon('<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>'),
    external: svgIcon('<path d="M15 3h6v6M10 14 21 3M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5"/>'),
    search: svgIcon('<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>'),
    alert: svgIcon('<circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/>'),
    arrowRight: svgIcon('<path d="M5 12h14M12 5l7 7-7 7"/>'),
    network: svgIcon('<circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="8" r="2.5"/><circle cx="10" cy="18" r="2.5"/><path d="M8.3 7 15.6 7.6M7 8.3 9.1 15.6M16.4 10 11.8 16.2"/>'),
    close: svgIcon('<path d="M18 6 6 18M6 6l12 12"/>'),
    tag: svgIcon('<path d="M20.59 13.41 13.42 20.6a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><path d="M7 7h.01"/>'),
    file: svgIcon('<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/>'),
    calendar: svgIcon('<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>'),
    unlock: svgIcon('<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/>')
};

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function formatType(type) {
    if (!type) return '';
    const text = type.replace(/[-_]/g, ' ');
    return text.charAt(0).toUpperCase() + text.slice(1);
}

function emptyState(icon, html) {
    return `<div class="empty-state"><div class="empty-state-icon">${ICONS[icon]}</div><div class="empty-state-text">${html}</div></div>`;
}

/** Link to an author's works filtered by topics and/or types. */
function authorWorksUrl(orcidId, { topics = [], types = [] } = {}) {
    const params = new URLSearchParams();
    topics.forEach(t => params.append('topic', t));
    types.forEach(t => params.append('type', t));
    const query = params.toString();
    return `/author/${encodeURIComponent(orcidId)}/works${query ? `?${query}` : ''}`;
}

/** One work row. extraHtml (trusted markup) is added under the authors line. */
/**
 * Collaboration page for an author over their whole publishing period, opened
 * on their direct collaborators. Returns null when no publication year is known.
 */
function authorCollaborationUrl(orcidId, firstYear, lastYear) {
    if (!firstYear || !lastYear) return null;
    const params = new URLSearchParams({ orcid: orcidId, startYear: firstYear, endYear: lastYear, view: 'direct', from: 'author' });
    return `/network/collaboration?${params}`;
}

function renderWork(work, extraHtml = '') {
    if (typeof extraHtml !== 'string') extraHtml = '';  // when used directly as an Array.map callback
    const title = escapeHtml(work.title || 'Untitled work');
    const titleHtml = work.doi
        ? `<a href="https://doi.org/${encodeURI(work.doi)}" target="_blank" rel="noopener noreferrer">${title}<span class="visually-hidden"> (opens in a new tab)</span></a>`
        : title;
    const meta = [work.publication_year, formatType(work.type)].filter(Boolean).map(escapeHtml);
    if (work.journal_title) meta.push(`<em>${escapeHtml(work.journal_title)}</em>`);

    const names = work.contributors;
    let authors = names.slice(0, MAX_LISTED_AUTHORS).join(', ');
    if (names.length > MAX_LISTED_AUTHORS) authors += ` +${names.length - MAX_LISTED_AUTHORS} more`;

    // Only direct PDF/download links get a button; open-access landing pages
    // are still reachable through the title's DOI link.
    let action = '';
    if (work.oa_url && work.oa_is_pdf) {
        action = `
            <a class="btn btn-secondary btn-sm work-oa-btn" href="${escapeHtml(work.oa_url)}" target="_blank" rel="noopener noreferrer"
               aria-label="PDF: ${title} (opens in a new tab)">
                ${ICONS.pdf}PDF${ICONS.external}
            </a>`;
    }

    return `
        <li class="work-item">
            <div class="work-main">
                <h3 class="work-title">${titleHtml}</h3>
                ${meta.length ? `<div class="work-meta">${meta.join(' · ')}</div>` : ''}
                ${authors ? `<div class="work-authors">${escapeHtml(authors)}</div>` : ''}
                ${extraHtml}
            </div>
            ${action}
        </li>`;
}

/**
 * Modal list of every value of a facet (topics or types) with a search box and
 * checkboxes. Built on <dialog>: Escape closes it, focus stays inside while it
 * is open and returns to the opening button afterwards.
 *
 * @param {object} options
 * @param {string} options.noun        plural label, e.g. "topics"
 * @param {{value: string, count: number}[]} options.items  all values, most frequent first
 * @param {string[]} [options.selected] values checked when the dialog opens
 * @param {(value: string) => string} [options.format] display label for a value
 * @param {boolean} [options.allowEmpty] allow Apply with nothing checked (clears the filter)
 * @param {(values: string[]) => void} options.onApply
 */
function openFacetDialog({ noun, items, selected = [], format = v => v, allowEmpty = false, onApply }) {
    const opener = document.activeElement;
    const chosen = new Set(selected);
    const dialog = document.createElement('dialog');
    dialog.className = 'facet-dialog';
    dialog.setAttribute('aria-labelledby', 'facetDialogTitle');
    dialog.innerHTML = `
        <form method="dialog" class="facet-dialog-form">
            <div class="facet-dialog-search">
                ${ICONS.search}
                <input type="search" class="facet-dialog-input" placeholder="Search ${escapeHtml(noun)}"
                       aria-label="Search ${escapeHtml(noun)}" autocomplete="off">
                <button type="button" class="icon-btn" data-close aria-label="Close">${ICONS.close}</button>
            </div>
            <div class="facet-dialog-body">
                <h2 class="facet-dialog-heading" id="facetDialogTitle">
                    All ${escapeHtml(noun)} <span class="facet-dialog-total">(${items.length.toLocaleString()})</span>
                </h2>
                <ul class="facet-options" role="list"></ul>
                <p class="facet-dialog-empty" hidden></p>
            </div>
            <div class="facet-dialog-footer">
                <span class="status-text" aria-live="polite" data-count></span>
                <div class="facet-dialog-actions">
                    <button type="button" class="btn btn-secondary" data-close>Cancel</button>
                    <button type="submit" class="btn btn-primary" data-apply>Apply</button>
                </div>
            </div>
        </form>`;
    document.body.appendChild(dialog);

    const list = dialog.querySelector('.facet-options');
    const input = dialog.querySelector('.facet-dialog-input');
    const empty = dialog.querySelector('.facet-dialog-empty');
    const count = dialog.querySelector('[data-count]');
    const apply = dialog.querySelector('[data-apply]');

    list.innerHTML = items.map((item, i) => `
        <li data-search="${escapeHtml(format(item.value).toLowerCase())}">
            <label class="facet-option">
                <input type="checkbox" class="option-checkbox" value="${escapeHtml(item.value)}" ${chosen.has(item.value) ? 'checked' : ''}>
                <span class="option-checkbox-custom" aria-hidden="true"></span>
                <span class="facet-option-label">${escapeHtml(format(item.value))}</span>
                <span class="facet-option-count">${item.count.toLocaleString()}</span>
            </label>
        </li>`).join('');

    const updateCount = () => {
        count.textContent = chosen.size ? `${chosen.size} selected` : '';
        apply.disabled = !allowEmpty && chosen.size === 0;
    };
    updateCount();

    list.addEventListener('change', e => {
        if (e.target.checked) chosen.add(e.target.value);
        else chosen.delete(e.target.value);
        updateCount();
    });

    input.addEventListener('input', () => {
        const query = input.value.trim().toLowerCase();
        let shown = 0;
        list.querySelectorAll('li').forEach(li => {
            const match = !query || li.dataset.search.includes(query);
            li.hidden = !match;
            if (match) shown++;
        });
        empty.hidden = shown > 0;
        empty.textContent = shown ? '' : `No ${noun} match “${input.value.trim()}”. Try a shorter search.`;
    });

    dialog.querySelectorAll('[data-close]').forEach(btn => btn.addEventListener('click', () => dialog.close('cancel')));
    // Click on the backdrop (outside the panel) closes like Cancel
    dialog.addEventListener('click', e => { if (e.target === dialog) dialog.close('cancel'); });
    dialog.addEventListener('submit', e => {
        e.preventDefault();
        // Keep the order of the list (most frequent first)
        const values = items.map(item => item.value).filter(v => chosen.has(v));
        dialog.close('apply');
        onApply(values);
    });
    dialog.addEventListener('close', () => {
        dialog.remove();
        if (opener && document.contains(opener)) opener.focus();
    });

    dialog.showModal();
    input.focus();
}
