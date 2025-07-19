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
            
        const formatPrice = (p) => {
            // cap to 4 decimals and strip trailing zeros
            const fixed = Number(p).toFixed(4);
            return parseFloat(fixed).toString();
        };

        let tooltipHTML = `
            <strong>${model.model}</strong><br/>
            <br/>ELO: ${model.elo}<br/>
            Votes: ${model.votes || 'N/A'}<br/>
            Price: $${formatPrice(model.price)}/M tokens<br/>
            Cheapest provider: ${model.cheapest_provider}<br>
            Organization: ${model.organization || 'N/A'}<br>
        `;

        if (isPareto) {
            tooltipHTML += `<br/><span style="color: #ff4444; font-weight: bold;">Pareto Optimal</span>`;
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
     * Update provider legend with clickable items for toggling visibility.
     * @param {Array<string>} organizations - Array of all unique organization names.
     * @param {Set<string>} activeOrganizations - Set of currently active organization names.
     */
    updateLegend(organizations, activeOrganizations) {
        const legendContainer = d3.select("#legend");
        if (legendContainer.empty()) return;

        legendContainer.html(""); // Clear existing legend

        // Add a title and explanation for the legend
        const legendHeader = legendContainer.append("div").attr("class", "legend-header");
        legendHeader.append("h3").text("Filter by organization");
        legendHeader.append("p").text("Click an organization (the company that created the model) to show/hide its models.");

        organizations.forEach(organization => {
            const isActive = activeOrganizations.has(organization);
            const legendItem = legendContainer
                .append("div")
                .attr("class", "legend-item")
                .attr("tabindex", 0) // keyboard focusable
                .classed("disabled", !isActive)
                .on("click", function() {
                    // Determine new state from DOM (robust against double-clicks)
                    const currentlyDisabled = d3.select(this).classed('disabled');
                    document.dispatchEvent(new CustomEvent('organizationToggle', {
                        detail: {
                            organization: organization,
                            isChecked: currentlyDisabled // we will enable if it was disabled
                        }
                    }));
                })
                .on("keydown", function(event) {
                    if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        // Trigger click handler for keyboard
                        d3.select(this).dispatch('click');
                    }
                });

            legendItem
                .append("div")
                .attr("class", "legend-color")
                .style("background-color", this.colorScale ? this.colorScale(organization) : "#ccc");

            legendItem
                .append("span")
                .text(organization);
        });

        // Add a "Reset" button at the end of the legend
        if (organizations.length > 0) {
            const resetItem = legendContainer
                .append("div")
                .attr("class", "legend-item reset-button")
                .attr("tabindex", 0)
                .on("click", function() {
                    document.dispatchEvent(new CustomEvent('resetOrganizations'));
                })
                .on("keydown", function(event) {
                    if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        d3.select(this).dispatch('click');
                    }
                });

            resetItem.append("span").text("Reset Selections");
        }
    }

    /**
     * Update Pareto frontier information
     */
    updateParetoInfo(paretoData) {
        const explanationContainer = d3.select(".explanation");
        
        // Clear previous Pareto content to prevent duplication. (DEPRECATED: Remove old separate pareto-info container if it exists.)
        explanationContainer.select("#pareto-frontier-content").remove();

        if (!paretoData || paretoData.length === 0) {
            return;
        }
        
        // Append Pareto content into the main explanation container.
        const paretoContent = explanationContainer.append("div").attr("id", "pareto-frontier-content");

        paretoContent.append('h2').html('Pareto frontier models');
        
        paretoContent.append('p').attr('class', 'pareto-explanation-detail').html('The models circled in black ⚫ are "pareto optimal". This means no other model is both cheaper and higher quality. These are generally the most efficient models to consider.');
        paretoContent.append('p').attr('class', 'pareto-explanation-detail').html('The black dotted line connects these optimal models, illustrating the Pareto frontier. Ultimately, this line represents the best possible performance you can achieve for a given cost.');

        paretoContent.append('p').html('Below is a list of all models on the Pareto frontier, sorted by ELO score descending :');
        
        const modelsContainer = paretoContent
            .append("div")
            .attr("class", "pareto-models");

        // Sort models by ELO score descending for ordered display.
        paretoData.sort((a, b) => b.elo - a.elo);

        const formatPrice = (p) => {
            const fixed = Number(p).toFixed(4);
            return parseFloat(fixed).toString();
        };

        paretoData.forEach(model => {
            const modelElement = modelsContainer
                .append("div")
                .attr("class", "pareto-model")
                .style("border-left", `3px solid ${this.colorScale ? this.colorScale(model.organization) : "#ccc"}`);
            
            modelElement.append("strong").text(model.model);
            
            modelElement
                .append("span")
                .style("display", "block")
                .style("font-size", "11px")
                .style("color", "#666")
                .html(`Organization: ${model.organization}<br>Cheapest provider: ${model.cheapest_provider}<br>ELO: ${model.elo}<br>Cost: $${formatPrice(model.price)}/M tokens`);
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

    /**
     * Sets up collapsible sections in the UI.
     */
    setupCollapsibleSections() {
        const toggle = document.querySelector('.explanation-toggle');
        const content = document.querySelector('.explanation-content');

        if (toggle && content) {
            // Set initial state
            if (!content.classList.contains('collapsed')) {
                toggle.classList.add('expanded');
            }

            toggle.addEventListener('click', () => {
                content.classList.toggle('collapsed');
                toggle.classList.toggle('expanded');
            });
        }
    }
}
