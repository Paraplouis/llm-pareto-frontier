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
        this.activeProviders = new Set(); // Store currently active providers
        
        // Bind event handlers
        this.handleResize = this.handleResize.bind(this);
        this.handleProviderToggle = this.handleProviderToggle.bind(this);
    }

    /**
     * Initialize the application
     */
    async init() {
        try {
            // Get all unique providers
            const allProviders = this.dataProcessor.getUniqueProviders(this.modelData);

            // Setup color scale once
            this.chartRenderer.setupColorScale(allProviders);

            // Initialize activeProviders with all unique providers
            this.activeProviders = new Set(allProviders);

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
        const validData = this.dataProcessor.getValidData(this.modelData, this.activeProviders);

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

        // Provider toggle event handler
        document.addEventListener('providerToggle', this.handleProviderToggle);
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
     * Handle provider toggle event
     */
    handleProviderToggle(event) {
        const { provider, isChecked } = event.detail;
        if (isChecked) {
            this.activeProviders.add(provider);
        } else {
            this.activeProviders.delete(provider);
        }
        this.refreshChart();
    }

    /**
     * Refresh the chart with current data
     */
    async refreshChart() {
        const validData = this.dataProcessor.getValidData(this.modelData, this.activeProviders);
        await this.renderChart(validData);
        
        // Update legend and Pareto info
        this.updateLegendAndParetoInfo(validData);
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
        const providers = this.dataProcessor.getUniqueProviders(this.modelData);
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
        
        // Update legend, passing all providers and the set of active ones
        this.uiController.updateLegend(providers, this.activeProviders);
        
        // Update Pareto information
        this.uiController.updateParetoInfo(paretoData);
    }
}
