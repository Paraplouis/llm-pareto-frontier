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
        this.activeOrganizations = new Set(); // Store currently active organizations

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

        // Ratio label element
        this.ratioLabelEl = document.getElementById('current-ratio');
        this.presetButtons = Array.from(document.querySelectorAll('.preset-button'));
        this.updateRatioDisplayAndPresets();
        
        // Bind event handlers
        this.handleResize = this.handleResize.bind(this);
        this.handleOrganizationToggle = this.handleOrganizationToggle.bind(this);
        this.handleResetOrganizations = this.handleResetOrganizations.bind(this);
    }

    /**
     * Initialize the application
     */
    async init() {
        try {
            // Get all unique organizations
            const allOrganizations = this.dataProcessor.getUniqueOrganizations(this.modelData);

            // Setup color scale once
            this.chartRenderer.setupColorScale(allOrganizations);

            // Initialize activeOrganizations with all unique organizations
            this.activeOrganizations = new Set(allOrganizations);

            // Process and display data
            await this.loadAndDisplayData();
            
            // Setup event listeners
            this.setupEventListeners();

            // Setup collapsible sections
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
        const validData = this.dataProcessor.getValidData(this.modelData, this.activeOrganizations, this.excludeFree, this.promptTokens, this.outputTokens);

        // Render chart with filtered data
        await this.renderChart(validData);
        
        // Update legend with providers and their active state
        this.updateLegendAndParetoInfo(validData);
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Window resize handler
        window.addEventListener('resize', this.handleResize);
        
        // Tooltip event handlers
        document.addEventListener('modelHover', (event) => {
            const { model, x, y, isPareto } = event.detail;
            this.uiController.showTooltip(model, x, y, isPareto);
        });
        
        document.addEventListener('modelUnhover', () => {
            this.uiController.hideTooltip();
        });

        // Organization toggle event handler
        document.addEventListener('organizationToggle', this.handleOrganizationToggle);
        
        // Reset organizations event handler
        document.addEventListener('resetOrganizations', this.handleResetOrganizations);

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
    }

    /**
     * Handle window resize
     */
    handleResize() {
        // Debounce resize events
        clearTimeout(this.resizeTimeout);
        this.resizeTimeout = setTimeout(() => {
            this.refreshChart();
        }, 250);
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
     * Handle reset organizations event
     */
    handleResetOrganizations() {
        const allOrganizations = this.dataProcessor.getUniqueOrganizations(this.modelData);
        this.activeOrganizations = new Set(allOrganizations);
        this.refreshChart();
    }
    
    /**
     * Refresh the chart with current data
     */
    async refreshChart() {
        const validData = this.dataProcessor.getValidData(this.modelData, this.activeOrganizations, this.excludeFree, this.promptTokens, this.outputTokens);
        await this.renderChart(validData);
        
        // Update legend and Pareto info
        this.updateLegendAndParetoInfo(validData);
        this.updateRatioDisplayAndPresets();
    }

    /**
     * Render the chart with processed data
     */
    async renderChart(data) {
        try {
            // Calculate Pareto frontier
            const paretoData = this.dataProcessor.calculateParetoFrontier(data);
            
            // Render the chart
            await this.chartRenderer.render(data, paretoData);
            
        } catch (error) {
            console.error('Error rendering chart:', error);
            this.uiController.showError('Failed to render chart');
        }
    }

    /**
     * Update legend and Pareto information
     */
    updateLegendAndParetoInfo(data) {
        const organizations = this.dataProcessor.getUniqueOrganizations(this.modelData);
        const paretoData = this.dataProcessor.calculateParetoFrontier(data);
        
        // Set color scale in UI controller
        if (this.chartRenderer.colorScale) {
            this.uiController.setColorScale(this.chartRenderer.colorScale);
        }
        
        // Update chart info display
        this.uiController.updateChartInfo(
            data.length,
            paretoData.length,
            this.modelDataLastUpdated,
            this.minElo,
            this.excludeFree
        );
        
        // Update legend, passing all organizations and the set of active ones
        this.uiController.updateLegend(organizations, this.activeOrganizations);
        
        // Update Pareto information
        this.uiController.updateParetoInfo(paretoData);
    }

    /**
     * Update the ratio display and preset buttons
     */
    updateRatioDisplayAndPresets() {
        if (this.ratioLabelEl) {
            const gcd = (a, b) => b === 0 ? a : gcd(b, a % b);
            const divisor = gcd(this.promptTokens, this.outputTokens);
            const simpleIn = divisor ? this.promptTokens / divisor : this.promptTokens;
            const simpleOut = divisor ? this.outputTokens / divisor : this.outputTokens;
            this.ratioLabelEl.textContent = `${simpleIn}:${simpleOut}`;
        }

        const currentGCD = (a, b) => b === 0 ? a : currentGCD(b, a % b);
        const curDiv = currentGCD(this.promptTokens, this.outputTokens);
        const curIn = curDiv ? this.promptTokens / curDiv : this.promptTokens;
        const curOut = curDiv ? this.outputTokens / curDiv : this.outputTokens;

        this.presetButtons.forEach(btn => {
            const prompt = parseInt(btn.dataset.prompt || 0, 10);
            const output = parseInt(btn.dataset.output || 0, 10);
            const gcd = currentGCD(prompt, output);
            const simpIn = gcd ? prompt / gcd : prompt;
            const simpOut = gcd ? output / gcd : output;
            const isActive = simpIn === curIn && simpOut === curOut;
            btn.classList.toggle('active', isActive);
        });
    }
}
