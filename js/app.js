/**
 * Main application for LLM Pareto Frontier
 * Orchestrates data processing, chart rendering, and UI interactions
 */
import { DataProcessor } from './modules/dataProcessor.js';
import { ChartRenderer } from './modules/chartRenderer.js';
import { UIController } from './modules/uiController.js';
import { data as modelData, dataLastUpdated } from '../data/synthesized_data.js';

export class LLMApp {
    constructor() {
        this.dataProcessor = new DataProcessor();
        this.chartRenderer = new ChartRenderer();
        this.uiController = new UIController();
        this.modelData = modelData;
        this.modelDataLastUpdated = dataLastUpdated;
        
        // Bind event handlers
        this.handleResize = this.handleResize.bind(this);
    }

    /**
     * Initialize the application
     */
    async init() {
        try {
            // Process and display data
            await this.loadAndDisplayData();
            
            // Setup event listeners
            this.setupEventListeners();
            
        } catch (error) {
            console.error('Failed to initialize app:', error);
            this.uiController.showError('Failed to load application data');
        }
    }

    /**
     * Load and display the data
     */
    async loadAndDisplayData() {
        const validData = this.dataProcessor.getValidData(this.modelData);

        // Render chart with all data
        await this.renderChart(validData);
        
        // Update legend with providers
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
            const { model, x, y } = event.detail;
            this.uiController.showTooltip(model, x, y);
        });
        
        document.addEventListener('modelUnhover', () => {
            this.uiController.hideTooltip();
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
     * Refresh the chart with current data
     */
    async refreshChart() {
        const validData = this.dataProcessor.getValidData(this.modelData);
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
        this.uiController.updateChartInfo(data.length, paretoData.length, this.modelDataLastUpdated);
        
        // Update legend
        this.uiController.updateLegend(providers);
        
        // Update Pareto information
        this.uiController.updateParetoInfo(paretoData);
    }
} 