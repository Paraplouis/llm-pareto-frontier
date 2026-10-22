/**
 * Page controls, lede, frontier steps, model table, and tooltip.
 * Model names and metadata come from external data, so they are written with textContent only.
 */
import { eloGap, valuePick, winProbability } from './dataProcessor.js';

const priceFormat = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumSignificantDigits: 3 });
const countFormat = new Intl.NumberFormat('en-US');
const shareFormat = new Intl.NumberFormat('en-US', { style: 'percent', maximumSignificantDigits: 2 });
const multipleFormat = new Intl.NumberFormat('en-US', { maximumSignificantDigits: 2 });
const formatPrice = (value) => priceFormat.format(value);
const formatModels = (count) => `${count} ${count === 1 ? 'model' : 'models'}`;

const DESCENDING_FIRST = new Set(['elo', 'votes']);
// The lede names the cheapest frontier model within this many ELO points of the leader.
const VALUE_GAP = 50;

const gcd = (a, b) => (b === 0 ? a : gcd(b, a % b));

// An empty mix is priced on input alone, like 1:0 (see visibleModels).
function reducedRatio(prompt, output) {
    if (prompt + output === 0) return '1:0';
    const divisor = gcd(prompt, output);
    return `${prompt / divisor}:${output / divisor}`;
}

function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
}

export class UIController {
    constructor({ onTokensChange, onOrganizationsChange, onSearchChange, onModelFocus }) {
        this.onTokensChange = onTokensChange;
        this.onOrganizationsChange = onOrganizationsChange;
        this.onSearchChange = onSearchChange;
        this.onModelFocus = onModelFocus;

        this.inputTokens = document.getElementById('input-tokens');
        this.outputTokens = document.getElementById('output-tokens');
        this.presetButtons = [...document.querySelectorAll('.preset-button')];
        this.orgFilter = document.querySelector('.org-filter');
        this.orgList = document.getElementById('org-filter-list');
        this.orgSummary = document.getElementById('org-filter-summary');
        this.frontierList = document.getElementById('frontier-list');
        this.tableBody = document.querySelector('#model-table tbody');
        this.sortButtons = [...document.querySelectorAll('.sort-button')];
        this.tooltip = document.getElementById('tooltip');
        this.matchLegend = document.getElementById('legend-match');
        this.lede = document.getElementById('lede');
        this.ticker = document.getElementById('ticker');

        this.sortKey = 'elo';
        this.sortDescending = true;
    }

    init({ organizationCounts, promptTokens, outputTokens, dataLastUpdated, minElo }) {
        this.setupThemeToggle();
        this.setupTokenControls(promptTokens, outputTokens);
        this.setupOrganizationFilter(organizationCounts);
        this.setupSearch();
        this.setupTableSorting();

        document.getElementById('edition').textContent = `Edition of ${dataLastUpdated}`;
        this.minElo = minElo;
    }

    setupThemeToggle() {
        const button = document.querySelector('.theme-toggle-button');
        const root = document.documentElement;
        const systemDark = window.matchMedia('(prefers-color-scheme: dark)');
        const isDark = () => (root.dataset.theme ?? (systemDark.matches ? 'dark' : 'light')) === 'dark';
        const syncLabel = () => {
            button.textContent = isDark() ? 'Day' : 'Night';
            button.setAttribute('aria-label', isDark() ? 'Switch to light mode' : 'Switch to dark mode');
        };

        button.addEventListener('click', () => {
            const theme = isDark() ? 'light' : 'dark';
            root.dataset.theme = theme;
            try {
                localStorage.setItem('theme', theme);
            } catch {
                // Storage can be unavailable in private windows; the toggle still applies to this page.
            }
            syncLabel();
        });
        systemDark.addEventListener('change', syncLabel);
        syncLabel();
    }

    setupTokenControls(promptTokens, outputTokens) {
        const apply = (prompt, output) => {
            this.inputTokens.value = prompt;
            this.outputTokens.value = output;
            this.syncPresets(prompt, output);
            this.onTokensChange(prompt, output);
        };
        const readInputs = () => {
            const prompt = Math.max(0, parseInt(this.inputTokens.value, 10) || 0);
            const output = Math.max(0, parseInt(this.outputTokens.value, 10) || 0);
            this.syncPresets(prompt, output);
            this.onTokensChange(prompt, output);
        };

        this.presetButtons.forEach(button => {
            button.addEventListener('click', () => apply(Number(button.dataset.prompt), Number(button.dataset.output)));
        });
        this.inputTokens.addEventListener('input', readInputs);
        this.outputTokens.addEventListener('input', readInputs);

        this.inputTokens.value = promptTokens;
        this.outputTokens.value = outputTokens;
        this.syncPresets(promptTokens, outputTokens);
    }

    syncPresets(prompt, output) {
        const ratio = reducedRatio(prompt, output);
        this.presetButtons.forEach(button => {
            const isActive = reducedRatio(Number(button.dataset.prompt), Number(button.dataset.output)) === ratio;
            button.classList.toggle('active', isActive);
            button.setAttribute('aria-pressed', String(isActive));
        });
        this.ratioLabel = ratio;
    }

    setupOrganizationFilter(organizationCounts) {
        this.organizations = [...organizationCounts.keys()];
        this.orgCheckboxes = new Map();

        organizationCounts.forEach((count, organization) => {
            const item = element('li', 'org-option');
            const label = element('label');
            const checkbox = element('input');
            checkbox.type = 'checkbox';
            checkbox.checked = true;
            checkbox.addEventListener('change', () => this.emitOrganizations());
            label.append(checkbox, element('span', null, organization), element('span', 'org-count', count));

            const only = element('button', 'org-only', 'Only');
            only.type = 'button';
            only.setAttribute('aria-label', `Show only ${organization}`);
            only.addEventListener('click', () => this.setOrganizations(new Set([organization])));

            item.append(label, only);
            this.orgList.append(item);
            this.orgCheckboxes.set(organization, checkbox);
        });

        document.getElementById('org-select-all').addEventListener('click', () => this.setOrganizations(new Set(this.organizations)));
        document.getElementById('org-select-none').addEventListener('click', () => this.setOrganizations(new Set()));

        document.addEventListener('click', (event) => {
            if (this.orgFilter.open && !this.orgFilter.contains(event.target)) this.orgFilter.open = false;
        });
        this.orgFilter.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                this.orgFilter.open = false;
                this.orgFilter.querySelector('summary').focus();
            }
        });
        this.updateOrganizationSummary();
    }

    setOrganizations(selected) {
        this.orgCheckboxes.forEach((checkbox, organization) => {
            checkbox.checked = selected.has(organization);
        });
        this.emitOrganizations();
    }

    emitOrganizations() {
        const selected = new Set(this.organizations.filter(organization => this.orgCheckboxes.get(organization).checked));
        this.updateOrganizationSummary(selected);
        this.onOrganizationsChange(selected);
    }

    updateOrganizationSummary(selected = new Set(this.organizations)) {
        let summary = `${selected.size} selected`;
        if (selected.size === this.organizations.length) summary = `All (${selected.size})`;
        else if (selected.size === 0) summary = 'None';
        else if (selected.size === 1) summary = [...selected][0];
        this.orgSummary.textContent = summary;
    }

    setupSearch() {
        const search = document.getElementById('model-search');
        search.addEventListener('input', () => this.onSearchChange(search.value));
    }

    setupTableSorting() {
        this.sortButtons.forEach(button => {
            button.addEventListener('click', () => {
                const key = button.dataset.sort;
                this.sortDescending = key === this.sortKey ? !this.sortDescending : DESCENDING_FIRST.has(key);
                this.sortKey = key;
                this.renderTableRows();
            });
        });
    }

    updateSummaries({ visibleCount, frontierCount, matchCount, query }) {
        this.matchLegend.hidden = matchCount === 0;
        document.getElementById('chart-summary').textContent =
            `${formatModels(visibleCount)} · ${frontierCount} on the frontier · prices blended at ${this.ratioLabel} input:output · `
            + `ELO ≥ ${this.minElo} · log price scale`;

        const tableSummary = query.trim()
            ? `${matchCount} of ${formatModels(visibleCount)} match “${query.trim()}”`
            : `${formatModels(visibleCount)}, click a column to sort`;
        document.getElementById('table-summary').textContent = tableSummary;
    }

    renderHeadline(frontier, visibleCount) {
        if (frontier.length === 0) {
            this.lede.textContent = 'No model matches the current filters.';
            this.renderTicker([['Models priced', '0'], ['On the frontier', '0'], ['Entry price', '—'], ['Top score', '—']]);
            return;
        }

        const { leader, value } = valuePick(frontier, VALUE_GAP);
        const entry = frontier.at(-1);
        this.lede.replaceChildren(element('strong', null, leader.model), ` leads the board at ${leader.elo}`);
        if (value === leader) {
            this.lede.append(`, and no cheaper model comes within ${VALUE_GAP} points.`);
        } else {
            const deficit = leader.elo - value.elo;
            this.lede.append(
                '. ',
                element('strong', null, value.model),
                ` trails by ${deficit} points, so the leader wins ${shareFormat.format(winProbability(deficit))} of their head-to-head votes, at `,
                element('span', 'figure-value', shareFormat.format(value.price / leader.price)),
                ' of the leader’s price.',
            );
        }

        this.renderTicker([
            ['Models priced', countFormat.format(visibleCount)],
            ['On the frontier', String(frontier.length)],
            ['Entry price', formatPrice(entry.price), '/MTok'],
            ['Top score', String(leader.elo), ` at ${formatPrice(leader.price)}`],
        ]);
    }

    renderTicker(cells) {
        this.ticker.replaceChildren(...cells.map(([term, value, unit]) => {
            const cell = element('div');
            const description = element('dd', null, value);
            if (unit) description.append(element('small', null, unit));
            cell.append(element('dt', null, term), description);
            return cell;
        }));
    }

    renderFrontier(frontier) {
        const byPrice = [...frontier].sort((a, b) => a.price - b.price);
        if (byPrice.length === 0) {
            this.frontierList.replaceChildren(element('li', 'frontier-empty', 'Select at least one organization.'));
            return;
        }

        this.frontierList.replaceChildren(...byPrice.map((model, index) => {
            const item = element('li', 'frontier-item');
            item.tabIndex = 0;
            const name = element('span', 'frontier-name', model.model);
            name.title = model.model;
            const comparedTo = (rank) => {
                const base = byPrice[rank - 1];
                return `+${model.elo - base.elo} ELO for ×${multipleFormat.format(model.price / base.price)} the price of #${rank}`;
            };
            const step = element('span', 'frontier-step');
            if (index === 0) step.append(element('span', null, 'Cheapest entry on the board'));
            if (index >= 2) step.append(element('span', null, comparedTo(index)));
            if (index >= 1) step.append(element('span', null, comparedTo(1)));
            item.append(
                element('span', 'frontier-rank', index + 1),
                name,
                element('span', 'frontier-elo', model.elo),
                element('span', 'frontier-org', model.organization),
                element('span', 'frontier-price', `${formatPrice(model.price)}/MTok`),
                step,
            );
            const focus = () => {
                item.classList.add('focused');
                this.onModelFocus(model);
            };
            const blur = () => {
                item.classList.remove('focused');
                this.onModelFocus(null);
            };
            item.addEventListener('pointerenter', focus);
            item.addEventListener('pointerleave', blur);
            item.addEventListener('focus', focus);
            item.addEventListener('blur', blur);
            return item;
        }));
    }

    renderTable(models, frontier) {
        this.tableModels = models;
        this.tableFrontier = new Set(frontier);
        this.tableGaps = new Map(models.map(model => [model, eloGap(model, frontier)]));
        this.renderTableRows();
    }

    renderTableRows() {
        this.sortButtons.forEach(button => {
            const header = button.closest('th');
            if (button.dataset.sort === this.sortKey) {
                header.setAttribute('aria-sort', this.sortDescending ? 'descending' : 'ascending');
            } else {
                header.removeAttribute('aria-sort');
            }
        });

        if (this.tableModels.length === 0) {
            const row = element('tr');
            const cell = element('td', 'table-empty', 'No models match the current filters.');
            cell.colSpan = this.sortButtons.length;
            row.append(cell);
            this.tableBody.replaceChildren(row);
            return;
        }

        const key = this.sortKey;
        const value = key === 'gap' ? (model) => this.tableGaps.get(model) : (model) => model[key];
        const compare = typeof value(this.tableModels[0]) === 'string'
            ? (a, b) => value(a).localeCompare(value(b))
            : (a, b) => value(a) - value(b);
        const sorted = [...this.tableModels].sort(this.sortDescending ? (a, b) => compare(b, a) : compare);

        this.tableBody.replaceChildren(...sorted.map(model => {
            const row = element('tr', this.tableFrontier.has(model) ? 'frontier-row' : '');
            const nameCell = element('td');
            nameCell.append(element('span', 'model-cell', model.model));
            const gap = this.tableGaps.get(model);
            row.append(
                nameCell,
                element('td', 'secondary', model.organization),
                element('td', 'numeric', model.elo),
                element('td', 'numeric secondary', gap === 0 ? '—' : `−${gap}`),
                element('td', 'numeric secondary', countFormat.format(model.votes)),
                element('td', 'numeric', formatPrice(model.price)),
                element('td', 'numeric secondary', formatPrice(model.input_price)),
                element('td', 'numeric secondary', formatPrice(model.output_price)),
            );
            return row;
        }));
    }

    showTooltip(model, clientX, clientY, { isFrontier, alternative }) {
        const stats = element('dl', 'tooltip-stats');
        [
            ['ELO score', `${model.elo} (${countFormat.format(model.votes)} votes)`],
            [`Blended at ${this.ratioLabel}`, `${formatPrice(model.price)}/MTok`],
            ['Input', `${formatPrice(model.input_price)}/MTok`],
            ['Output', `${formatPrice(model.output_price)}/MTok`],
        ].forEach(([term, value]) => stats.append(element('dt', null, term), element('dd', null, value)));

        const note = element('p', 'tooltip-note');
        if (isFrontier) {
            note.append(element('span', 'tooltip-badge', '◆ On the frontier'));
        } else {
            const saving = Math.round((1 - alternative.price / model.price) * 100);
            const cost = saving > 0 ? `${saving}% cheaper` : 'same price';
            note.append(
                'Better value: ',
                element('strong', null, alternative.model),
                ` scores ${alternative.elo} at ${formatPrice(alternative.price)} (${cost}).`,
            );
        }

        this.tooltip.replaceChildren(
            element('p', 'tooltip-title', model.model),
            element('p', 'tooltip-subtitle', model.organization),
            stats,
            note,
        );
        this.tooltip.hidden = false;

        const { width, height } = this.tooltip.getBoundingClientRect();
        const gap = 14;
        const left = clientX + gap + width > window.innerWidth - 8 ? clientX - gap - width : clientX + gap;
        const top = Math.min(Math.max(8, clientY - height / 2), window.innerHeight - height - 8);
        this.tooltip.style.left = `${Math.max(8, left)}px`;
        this.tooltip.style.top = `${top}px`;
    }

    hideTooltip() {
        this.tooltip.hidden = true;
    }
}
