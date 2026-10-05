/*
 * Remembers which constellations the user has opened from the network page,
 * so the network can shade them when the user comes back.
 *
 * Stored per network query (the filters that built the graph, e.g.
 * "startYear=2020&endYear=2026&type=book"), as the researchers whose details
 * were opened. The network page shades each of them and the rest of their
 * constellation. Kept in localStorage, so it survives reloads in this browser
 * only; the most recent MAX_QUERIES networks are kept.
 */
const NetworkViewed = (() => {
    const KEY = 'uaeh:network:viewed';
    const MAX_QUERIES = 20;

    function readAll() {
        try {
            return JSON.parse(localStorage.getItem(KEY)) || {};
        } catch {
            return {};
        }
    }

    function writeAll(all) {
        try {
            localStorage.setItem(KEY, JSON.stringify(all));
        } catch { /* storage full or blocked: viewed shading is only a convenience */ }
    }

    return {
        /** ORCID iDs opened from the network built by this query. */
        get(query) {
            return new Set(readAll()[query]?.focus || []);
        },

        /** Record that the constellation of orcidId was opened from this query's network. */
        add(query, orcidId) {
            const all = readAll();
            const entry = all[query] || { focus: [] };
            if (!entry.focus.includes(orcidId)) entry.focus.push(orcidId);
            entry.at = Date.now();
            all[query] = entry;
            // Keep only the most recently used networks
            const keep = Object.entries(all).sort((a, b) => (b[1].at || 0) - (a[1].at || 0)).slice(0, MAX_QUERIES);
            writeAll(Object.fromEntries(keep));
        },

        clear(query) {
            const all = readAll();
            delete all[query];
            writeAll(all);
        }
    };
})();
