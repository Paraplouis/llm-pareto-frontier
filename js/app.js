/**
 * Holds the filter state and re-renders the chart, frontier list, and table when it changes.
 */
import {
    calculateParetoFrontier,
    findCheaperAlternative,
    searchModels,
    uniqueOrganizations,
    visibleModels,
} from './modules/dataProcessor.js';
import { ChartRenderer } from './modules/chartRenderer.js';
import { UIController } from './modules/uiController.js';
import { data as modelData, dataLastUpdated, minElo } from '../data/synthesized_data.js';

export class LLMApp {
    constructor() {
        this.promptTokens = 750;
        this.outputTokens = 250;
        this.organizations = uniqueOrganizations(modelData);
        this.activeOrganizations = new Set(this.organizations);
        this.searchQuery = '';

        this.chart = new ChartRenderer(document.getElementById('chart'), {
            onHover: (model, x, y) => this.showModel(model, x, y),
        });
        this.ui = new UIController({
            onTokensChange: (prompt, output) => {
                this.promptTokens = prompt;
                this.outputTokens = output;
                this.refresh();
            },
            onOrganizationsChange: (organizations) => {
                this.activeOrganizations = organizations;
                this.refresh();
            },
            onSearchChange: (query) => {
                this.searchQuery = query;
                this.refresh();
            },
            onModelFocus: (model) => this.chart.focus(model),
        });
    }

    init() {
        this.ui.init({
            organizationCounts: new Map(this.organizations.map(organization => [
                organization,
                modelData.filter(model => model.organization === organization).length,
            ])),
            promptTokens: this.promptTokens,
            outputTokens: this.outputTokens,
            dataLastUpdated,
            minElo,
        });
        this.refresh();
    }

    refresh() {
        const visible = visibleModels(modelData, this.activeOrganizations, this.promptTokens, this.outputTokens);
        this.frontier = calculateParetoFrontier(visible);
        const matches = searchModels(visible, this.searchQuery);

        this.chart.render(visible, this.frontier, matches);
        this.ui.renderHeadline(this.frontier, visible.length);
        this.ui.renderFrontier(this.frontier);
        this.ui.renderTable(this.searchQuery.trim() ? matches : visible, this.frontier);
        this.ui.updateSummaries({
            visibleCount: visible.length,
            frontierCount: this.frontier.length,
            matchCount: matches.length,
            query: this.searchQuery,
        });
    }

    showModel(model, x, y) {
        if (!model) {
            this.ui.hideTooltip();
            return;
        }
        this.ui.showTooltip(model, x, y, {
            isFrontier: this.frontier.includes(model),
            alternative: findCheaperAlternative(model, this.frontier),
        });
    }
}
