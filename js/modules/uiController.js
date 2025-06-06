/**
 * UI controller module for LLM Pareto Frontier
 * Handles user interface interactions, tooltips, and statistics display
 */
export class UIController {
    constructor() {
        this.colorScale = null;
    }

    /**
     * Set the color scale for consistent provider colors
     */
    setColorScale(colorScale) {
        this.colorScale = colorScale;
    }


    /**
     * Show tooltip with model information
     */
    showTooltip(model, x, y, isPareto = false) {
        d3.selectAll('.tooltip').remove();
        
        const tooltip = d3.select('body')
            .append('div')
            .attr('class', 'tooltip')
            .style('left', (x + 10) + 'px')
            .style('top', (y - 10) + 'px');
            
        let tooltipHTML = `
            <strong>${model.model}</strong><br/>
            Provider: ${model.provider}<br/>
            ELO: ${model.elo}<br/>
            Price: $${model.price}/M tokens<br/>
            Votes: ${model.votes || 'N/A'}
        `;

        if (isPareto) {
            tooltipHTML += `<br/><span style="color: #d62728; font-weight: bold;">Pareto Optimal</span>`;
        }

        tooltip.html(tooltipHTML);
    }

    /**
     * Hide tooltip
     */
    hideTooltip() {
        d3.selectAll('.tooltip').remove();
    }

    /**
     * Show model details (for future implementation)
     */
    showModelDetails(model) {
        console.log('Model details:', model);
    }

    /**
     * Update provider legend
     */
    updateLegend(providers) {
        const legendContainer = d3.select("#legend");
        if (legendContainer.empty()) return;

        legendContainer.html("");

        providers.forEach(provider => {
            const legendItem = legendContainer
                .append("div")
                .attr("class", "legend-item");

            legendItem
                .append("div")
                .attr("class", "legend-color")
                .style("background-color", this.colorScale ? this.colorScale(provider) : "#ccc");

            legendItem
                .append("span")
                .text(provider);
        });
    }

    /**
     * Update Pareto frontier information
     */
    updateParetoInfo(paretoData) {
        // Remove existing Pareto info
        d3.select("#pareto-info").remove();
        
        if (!paretoData || paretoData.length === 0) return;

        // Create Pareto info container after legend
        const container = d3.select("#legend").node().parentNode;
        const paretoContainer = d3.select(container)
            .append("div")
            .attr("id", "pareto-info")
            .attr("class", "pareto-note");

        paretoContainer
            .append("h3")
            .text("Pareto Frontier Models");

        const modelsContainer = paretoContainer
            .append("div")
            .attr("class", "pareto-models");

        paretoData.forEach(model => {
            const modelElement = modelsContainer
                .append("div")
                .attr("class", "pareto-model")
                .style("border-left", `3px solid ${this.colorScale ? this.colorScale(model.provider) : "#ccc"}`);

            modelElement
                .append("strong")
                .text(model.model);

            modelElement
                .append("span")
                .style("display", "block")
                .style("font-size", "11px")
                .style("color", "#666")
                .text(`${model.provider} • ${model.elo} • $${model.price}/M tokens`);
        });
    }

    /**
     * Clear loading state
     */
    clearLoading() {
        const chartContainer = document.getElementById("chart");
        if (chartContainer) {
            d3.select("#chart").selectAll("*").remove();
        }
    }

    /**
     * Show loading state
     */
    showLoading() {
        const chartContainer = document.getElementById("chart");
        if (chartContainer) {
            chartContainer.innerHTML = '<div class="loading">Initializing chart...</div>';
        }
    }

    /**
     * Show error message
     */
    showError(message) {
        const chartContainer = document.getElementById("chart");
        if (chartContainer) {
            chartContainer.innerHTML = `<div class="error">Error: ${message}</div>`;
        }
    }

    /**
     * Initialize UI controller
     */
    init() {
        // Any initialization logic can go here
    }

    /**
     * Update chart information display
     */
    updateChartInfo(modelCount, paretoCount, lastUpdated, minElo, excludeFree) {
        const chartInfoElement = document.getElementById("chart-info");
        if (chartInfoElement) {
            const mainText = `Showing ${modelCount} models with ${paretoCount} Pareto optimal models`;
            
            const details = [];
            if (lastUpdated) {
                const updateDate = new Date(lastUpdated);
                const isoDate = updateDate.toISOString().split('T')[0];
                details.push(`updated ${isoDate}`);
            }

            if (minElo) {
                details.push(`min ELO: ${minElo}`);
            }

            if (excludeFree) {
                details.push(`excluding free models`);
            }
            
            let detailsText = '';
            if (details.length > 0) {
                detailsText = `(${details.join(', ')})`;
            }

            let innerHTML = mainText;
            if (detailsText) {
                innerHTML += `<br><span class="chart-info-details">${detailsText}</span>`;
            }
            
            chartInfoElement.innerHTML = innerHTML;
        }
    }
} 