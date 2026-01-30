/**
 * Main application for LLM Pareto Frontier
 * Orchestrates data processing, chart rendering, and UI interactions
 */
import { DataProcessor } from './modules/dataProcessor.js';
import { ChartRenderer } from './modules/chartRenderer.js';
import { UIController } from './modules/uiController.js';
import { data as modelData, dataLastUpdated, minElo, excludeFree } from '../data/synthesized_data.js';

export class LLMApp {
    constructor() {
        this.dataProcessor = new DataProcessor();
        this.chartRenderer = new ChartRenderer();
        this.uiController = new UIController();
        this.modelData = modelData;
        this.modelDataLastUpdated = dataLastUpdated;
        this.minElo = minElo;
        this.excludeFree = excludeFree;
        this.activeOrganizations = new Set();

        // Token settings (default 750 in / 250 out)
        this.promptTokens = 750;
        this.outputTokens = 250;

        // Cache DOM elements for token inputs
        this.inputTokenEl = document.getElementById('input-tokens');
        this.outputTokenEl = document.getElementById('output-tokens');

        if (this.inputTokenEl && this.outputTokenEl) {
            this.inputTokenEl.value = this.promptTokens;
            this.outputTokenEl.value = this.outputTokens;
        }

        // Ratio label element (create if missing)
        this.ratioLabelEl = document.getElementById('current-ratio');
        if (!this.ratioLabelEl) {
            const ratioSpan = document.createElement('span');
            ratioSpan.id = 'current-ratio';
            ratioSpan.className = 'ratio-display';
            const tokenControls = document.querySelector('.token-controls .preset-buttons');
            if (tokenControls) {
                tokenControls.appendChild(ratioSpan);
            }
            this.ratioLabelEl = ratioSpan;
        }

        this.presetButtons = Array.from(document.querySelectorAll('.preset-button'));
        this.updateRatioDisplayAndPresets();

        // Bind event handlers
        this.handleResize = this.handleResize.bind(this);
        this.handleOrganizationToggle = this.handleOrganizationToggle.bind(this);
        this.handleSelectAllOrganizations = this.handleSelectAllOrganizations.bind(this);
        this.handleDeselectAllOrganizations = this.handleDeselectAllOrganizations.bind(this);
        this.handleSelectOnlyOrganization = this.handleSelectOnlyOrganization.bind(this);

        // Store bound references for anonymous listeners so destroy() can remove them
        this._handleModelHover = (event) => {
            const { model, x, y, isPareto } = event.detail;
            this.uiController.showTooltip(model, x, y, isPareto);
        };
        this._handleModelUnhover = () => this.uiController.hideTooltip();
    }

    /**
     * Initialize the application
     */
    async init() {
        try {
            // Load provider pricing catalog first for dynamic provider attribution (if available)
            if (typeof this.dataProcessor.loadPriceData === 'function') {
                await this.dataProcessor.loadPriceData();
            }
            const allOrganizations = this.dataProcessor.getUniqueOrganizations(this.modelData);
            this.chartRenderer.setupColorScale(allOrganizations);
            this.activeOrganizations = new Set(allOrganizations);

            this.setupThemeToggle(); // Set theme preference FIRST

            await this.loadAndDisplayData(); // Then load data and render

            this.setupEventListeners();
            this.uiController.setupCollapsibleSections();
        } catch (error) {
            console.error('Failed to initialize app:', error);
            this.uiController.showError('Failed to load application data');
        }
    }

    /**
     * Load and display the data
     */
    async loadAndDisplayData() {
        const isDarkMode = document.body.classList.contains('dark-mode');
        const validData = this.dataProcessor.getValidData(
            this.modelData,
            this.activeOrganizations,
            this.excludeFree,
            this.promptTokens,
            this.outputTokens
        );

        // Compute Pareto once
        const paretoData = this.dataProcessor.calculateParetoFrontier(validData);

        await this.renderChart(validData, paretoData, isDarkMode);
        this.updateLegendAndParetoInfo(validData, paretoData);
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Window resize handler
        window.addEventListener('resize', this.handleResize);

        // Tooltip event handlers
        document.addEventListener('modelHover', this._handleModelHover);
        document.addEventListener('modelUnhover', this._handleModelUnhover);

        // Organization toggle event handler
        document.addEventListener('organizationToggle', this.handleOrganizationToggle);

        // Select all / Deselect all / Select only handlers
        document.addEventListener('selectAllOrganizations', this.handleSelectAllOrganizations);
        document.addEventListener('deselectAllOrganizations', this.handleDeselectAllOrganizations);
        document.addEventListener('selectOnlyOrganization', this.handleSelectOnlyOrganization);

        // Token input handlers
        if (this.inputTokenEl) {
            this.inputTokenEl.addEventListener('input', (e) => {
                this.promptTokens = Math.max(0, parseInt(e.target.value || 0, 10));
                this.updateRatioDisplayAndPresets();
                this.refreshChart();
            });
        }

        if (this.outputTokenEl) {
            this.outputTokenEl.addEventListener('input', (e) => {
                this.outputTokens = Math.max(0, parseInt(e.target.value || 0, 10));
                this.updateRatioDisplayAndPresets();
                this.refreshChart();
            });
        }

        // Preset ratio buttons
        const presetButtons = document.querySelectorAll('.preset-button');
        presetButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                const prompt = parseInt(btn.dataset.prompt || 0, 10);
                const output = parseInt(btn.dataset.output || 0, 10);
                this.promptTokens = prompt;
                this.outputTokens = output;

                if (this.inputTokenEl) this.inputTokenEl.value = prompt;
                if (this.outputTokenEl) this.outputTokenEl.value = output;

                this.refreshChart();
                this.updateRatioDisplayAndPresets();
            });
        });

        // Add a Reset Ratio button if missing
        const presetButtonsContainer = document.querySelector('.token-controls .preset-buttons');
        if (presetButtonsContainer && !presetButtonsContainer.querySelector('.ratio-reset')) {
            const resetBtn = document.createElement('button');
            resetBtn.className = 'preset-button reset-button ratio-reset';
            resetBtn.type = 'button';
            resetBtn.textContent = 'Reset ratio';
            resetBtn.title = 'Reset prompt/output ratio to 3:1 (750/250)';
            resetBtn.setAttribute('aria-label', 'Reset prompt/output ratio to default 3 to 1');
            resetBtn.addEventListener('click', () => {
                this.promptTokens = 750;
                this.outputTokens = 250;
                if (this.inputTokenEl) this.inputTokenEl.value = 750;
                if (this.outputTokenEl) this.outputTokenEl.value = 250;
                this.refreshChart();
                this.updateRatioDisplayAndPresets();
            });
            presetButtonsContainer.appendChild(resetBtn);
        }
    }

    /**
     * Handle window resize
     */
    handleResize() {
        // Debounce resize events
        clearTimeout(this.resizeTimeout);
        this.resizeTimeout = setTimeout(() => this.refreshChart(), 250);
    }

    /**
     * Handle organization toggle event
     */
    handleOrganizationToggle(event) {
        const { organization, isChecked } = event.detail;
        if (isChecked) {
            this.activeOrganizations.add(organization);
        } else {
            this.activeOrganizations.delete(organization);
        }
        this.refreshChart();
    }

    /**
     * Handle select all organizations event
     */
    handleSelectAllOrganizations() {
        const allOrganizations = this.dataProcessor.getUniqueOrganizations(this.modelData);
        this.activeOrganizations = new Set(allOrganizations);
        this.refreshChart();
    }

    /**
     * Handle deselect all organizations event
     */
    handleDeselectAllOrganizations() {
        this.activeOrganizations = new Set();
        this.refreshChart();
    }

    /**
     * Handle select only one organization event (option-click)
     */
    handleSelectOnlyOrganization(event) {
        const { organization } = event.detail;
        this.activeOrganizations = new Set([organization]);
        this.refreshChart();
    }

    /**
     * Refresh the chart with current data
     */
    async refreshChart() {
        const isDarkMode = document.body.classList.contains('dark-mode');
        const validData = this.dataProcessor.getValidData(
            this.modelData,
            this.activeOrganizations,
            this.excludeFree,
            this.promptTokens,
            this.outputTokens
        );
        const paretoData = validData.length > 0
            ? this.dataProcessor.calculateParetoFrontier(validData)
            : [];
        await this.renderChart(validData, paretoData, isDarkMode);
        this.updateLegendAndParetoInfo(validData, paretoData);
        this.updateRatioDisplayAndPresets();
    }

    /**
     * Render the chart with processed data
     */
    async renderChart(data, paretoData, isDarkMode) {
        try {
            await this.chartRenderer.render(data, paretoData, isDarkMode);

        } catch (error) {
            console.error('Error rendering chart:', error);
            this.uiController.showError('Failed to render chart');
        }
    }

    /**
     * Update legend and Pareto information
     */
    updateLegendAndParetoInfo(data, paretoData) {
        const organizations = this.dataProcessor.getUniqueOrganizations(this.modelData);
        if (this.chartRenderer.colorScale) {
            this.uiController.setColorScale(this.chartRenderer.colorScale);
        }
        this.uiController.updateChartInfo(
            data.length,
            paretoData.length,
            this.modelDataLastUpdated,
            this.minElo,
            this.excludeFree
        );
        this.uiController.updateLegend(organizations, this.activeOrganizations);
        this.uiController.updateParetoInfo([...paretoData]); // pass copy to avoid mutation
    }

    /**
     * Update the ratio display and preset buttons
     */
    updateRatioDisplayAndPresets() {
        const gcd = (a, b) => b === 0 ? a : gcd(b, a % b);
        if (this.ratioLabelEl) {
            const divisor = gcd(this.promptTokens, this.outputTokens) || 1;
            const simpleIn = this.promptTokens / divisor;
            const simpleOut = this.outputTokens / divisor;
            this.ratioLabelEl.textContent = `${simpleIn}:${simpleOut}`;
        }
        const curDiv = gcd(this.promptTokens, this.outputTokens) || 1;
        const curIn = this.promptTokens / curDiv;
        const curOut = this.outputTokens / curDiv;
        this.presetButtons.forEach(btn => {
            const prompt = parseInt(btn.dataset.prompt || 0, 10);
            const output = parseInt(btn.dataset.output || 0, 10);
            const d = gcd(prompt, output) || 1;
            const simpIn = prompt / d;
            const simpOut = output / d;
            const isActive = simpIn === curIn && simpOut === curOut;
            btn.classList.toggle('active', isActive);
        });
    }

    /**
     * Remove all event listeners registered by the app.
     * Call this if the app instance needs to be torn down.
     */
    destroy() {
        window.removeEventListener('resize', this.handleResize);
        document.removeEventListener('organizationToggle', this.handleOrganizationToggle);
        document.removeEventListener('selectAllOrganizations', this.handleSelectAllOrganizations);
        document.removeEventListener('deselectAllOrganizations', this.handleDeselectAllOrganizations);
        document.removeEventListener('selectOnlyOrganization', this.handleSelectOnlyOrganization);
        document.removeEventListener('modelHover', this._handleModelHover);
        document.removeEventListener('modelUnhover', this._handleModelUnhover);
        clearTimeout(this.resizeTimeout);
    }

    /**
     * Setup theme toggle
     */
    setupThemeToggle() {
        const themeToggleButton = document.querySelector('.theme-toggle-button');
        const body = document.body;

        const applyTheme = (theme) => {
            if (theme === 'dark') {
                body.classList.add('dark-mode');
            } else {
                body.classList.remove('dark-mode');
            }
            if (themeToggleButton) {
                themeToggleButton.setAttribute('aria-pressed', theme === 'dark' ? 'true' : 'false');
                themeToggleButton.setAttribute('aria-label', theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
                themeToggleButton.setAttribute('title', theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
            }
        };

        const toggleTheme = () => {
            const currentTheme = body.classList.contains('dark-mode') ? 'light' : 'dark';
            localStorage.setItem('theme', currentTheme);
            applyTheme(currentTheme);
            this.refreshChart();
        };

        themeToggleButton.addEventListener('click', toggleTheme);

        // Always follow the OS / browser preference on page load.
        // localStorage only keeps the toggle override within a session.
        const darkMQ = window.matchMedia('(prefers-color-scheme: dark)');
        applyTheme(darkMQ.matches ? 'dark' : 'light');

        // React to live OS preference changes (e.g. user toggles system dark mode)
        darkMQ.addEventListener('change', (e) => {
            localStorage.removeItem('theme');
            applyTheme(e.matches ? 'dark' : 'light');
            this.refreshChart();
        });
    }
}
