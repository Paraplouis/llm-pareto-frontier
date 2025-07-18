/**
 * Chart rendering module for LLM Pareto Frontier visualization
 * Uses D3.js for creating interactive scatter plots with Pareto frontier
 */
export class ChartRenderer {
    constructor() {
        this.container = d3.select("#chart");
        this.colorScale = null;
        this.tooltip = null;
        this.svg = null;
        this.dimensions = null;
        this.currentData = [];
        this.currentParetoFrontier = [];
        this.sortedParetoFrontier = [];
        this.paretoIndexLookup = new Map();
        this.paretoLabelInfo = new Map();
        this.config = {
            RESPONSIVE: {
                MOBILE_BREAKPOINT: 600,
            },
            CHART: {
                MARGIN: {
                    top: 20,
                    right: 80,
                    bottom: 30,
                    left: 60,
                    mobile: {
                        right: 40,
                        left: 50,
                    },
                },
                SCALES: {
                    X_DOMAIN: [0.02, 100],
                    Y_DOMAIN: [1000, 1500],
                },
                POINTS: {
                    RADIUS: {
                        normal: { desktop: 5, mobile: 4 },
                        pareto: { desktop: 7, mobile: 6 },
                        hover: { desktop: 9, mobile: 8 },
                    },
                },
                COLORS: {
                    PARETO_STROKE: "#000",
                    PARETO_LINE: "#000",
                },
            },
            ANIMATION: {
                HOVER_DURATION: 150,
            }
        };
    }

    /**
     * Setup color scale for organizations
     */
    setupColorScale(organizations) {
        // Use a larger categorical palette to avoid color collisions when organizations >10
        const palette = [...d3.schemeTableau10, ...d3.schemeSet3];
        this.colorScale = d3.scaleOrdinal()
            .domain(organizations)
            .range(palette);
    }

    /**
     * Calculate chart dimensions based on container size
     */
    calculateDimensions() {
        const containerWidth = this.container.node().clientWidth;
        const containerHeight = Math.max(400, window.innerHeight * 0.6);
        const isMobile = containerWidth < this.config.RESPONSIVE.MOBILE_BREAKPOINT;

        const margin = {
            ...this.config.CHART.MARGIN,
            right: isMobile ? this.config.CHART.MARGIN.mobile.right : this.config.CHART.MARGIN.right,
            left: isMobile ? this.config.CHART.MARGIN.mobile.left : this.config.CHART.MARGIN.left
        };

        return {
            containerWidth,
            containerHeight,
            width: containerWidth - margin.left - margin.right,
            height: containerHeight - margin.top - margin.bottom,
            margin,
            isMobile
        };
    }

    /**
     * Create scales for x (price) and y (ELO) axes
     */
    createScales() {
        const { width, height } = this.dimensions;

        // Dynamically derive domains from data; fall back to config defaults
        const priceValues = (this.currentData || []).map(d => d.price).filter(p => p > 0);
        const eloValues   = (this.currentData || []).map(d => d.elo);

        const defaultX = this.config.CHART.SCALES.X_DOMAIN;
        const defaultY = this.config.CHART.SCALES.Y_DOMAIN;

        const xMin = priceValues.length ? Math.min(...priceValues) * 0.9 : defaultX[0];
        const xMax = priceValues.length ? Math.max(...priceValues) * 1.1 : defaultX[1];

        const yMin = eloValues.length ? Math.min(...eloValues) - 20 : defaultY[0];
        const yMax = eloValues.length ? Math.max(...eloValues) + 20 : defaultY[1];

        const xScale = d3.scaleLog()
            .domain([Math.max(0.01, xMin), xMax])
            .range([0, width])
            .clamp(true);

        const yScale = d3.scaleLinear()
            .domain([yMin, yMax])
            .range([height, 0])
            .clamp(true);

        return { xScale, yScale };
    }

    /**
     * Create and render chart axes
     */
    createAxes(scales) {
        const { xScale, yScale } = scales;
        const { width, height, isMobile } = this.dimensions;

        const xAxis = d3.axisBottom(xScale)
            .ticks(isMobile ? 4 : 6)
            .tickSize(6)
            .tickPadding(3)
            .tickFormat(d => {
                const formatted = d < 1 ? Number(d.toFixed(4)) : Number(d.toFixed(2));
                return `$${formatted}`;
            });

        this.svg.append("g")
            .attr("transform", `translate(0,${height})`)
            .attr("class", "x-axis axis")
            .call(xAxis)
            .selectAll("text")
            .style("text-anchor", "end")
            .style("fill", "#000")
            .attr("dx", "-.8em")
            .attr("dy", ".15em")
            .attr("transform", "rotate(-45)");

        const yAxis = d3.axisLeft(yScale)
            .ticks(height < 400 ? 5 : 8)
            .tickSize(6)
            .tickPadding(3);

        this.svg.append("g")
            .attr("class", "y-axis axis")
            .style("color", "#000")
            .call(yAxis)
            .selectAll("text")
            .style("fill", "#000");

        this.addAxisLabels();
        this.addGridLines(scales);
    }

    /**
     * Add axis labels
     */
    addAxisLabels() {
        const { width, height, isMobile } = this.dimensions;

        this.svg.append("text")
            .attr("class", "x-axis-title axis-label")
            .attr("x", width / 2)
            .attr("y", height + (isMobile ? 40 : 55))
            .attr("fill", "#000")
            .attr("text-anchor", "middle")
            .attr("font-weight", "bold")
            .attr("font-size", isMobile ? "10px" : "12px")
            .text("Price per million tokens ($)");

        this.svg.append("text")
            .attr("class", "y-axis-title axis-label")
            .attr("transform", "rotate(-90)")
            .attr("y", -45)
            .attr("x", -height / 2)
            .attr("fill", "#000")
            .attr("text-anchor", "middle")
            .attr("font-weight", "bold")
            .attr("font-size", isMobile ? "10px" : "12px")
            .text("LM Arena ELO score");
    }

    /**
     * Add grid lines to chart
     */
    addGridLines(scales) {
        const { xScale, yScale } = scales;
        const { width, height } = this.dimensions;

        this.svg.append("g")
            .attr("class", "grid")
            .call(d3.axisLeft(yScale).tickSize(-width).tickFormat(""));

        this.svg.append("g")
            .attr("class", "grid")
            .attr("transform", `translate(0,${height})`)
            .call(d3.axisBottom(xScale).tickSize(-height).tickFormat(""));
    }

    /**
     * Check if a model is on the Pareto frontier
     */
    isParetoOptimal(modelName) {
        return this.currentParetoFrontier.some(p => p.model === modelName);
    }

    /**
     * Get point radius based on state and Pareto optimality
     */
    getPointRadius(d, state = 'normal') {
        const { isMobile } = this.dimensions;
        const device = isMobile ? 'mobile' : 'desktop';
        const isPareto = this.isParetoOptimal(d.model);
        const pointType = isPareto ? 'pareto' : 'normal';
        
        if (state === 'hover') {
            return this.config.CHART.POINTS.RADIUS.hover[device];
        }
        
        return this.config.CHART.POINTS.RADIUS[pointType][device];
    }

    /**
     * Render data points on the chart
     */
    renderDataPoints(scales, data) {
        const { xScale, yScale } = scales;

        // Draw non-Pareto points first, Pareto points last for correct stacking order
        const orderedData = [...data].sort((a, b) => {
            const aPareto = this.isParetoOptimal(a.model) ? 1 : 0;
            const bPareto = this.isParetoOptimal(b.model) ? 1 : 0;
            return aPareto - bPareto; // non-Pareto (0) first, Pareto (1) last
        });

        this.svg.selectAll(".datapoint")
            .data(orderedData)
            .enter()
            .append("circle")
            .attr("class", d => {
                const isPareto = this.isParetoOptimal(d.model);
                return isPareto ? "datapoint pareto" : "datapoint";
            })
            .attr("cx", d => xScale(d.price))
            .attr("cy", d => yScale(d.elo))
            .attr("r", d => this.getPointRadius(d))
            .attr("fill", d => this.colorScale ? this.colorScale(d.organization) : "#666")
            .attr("stroke", d => {
                const isPareto = this.isParetoOptimal(d.model);
                return isPareto ? this.config.CHART.COLORS.PARETO_STROKE : "#fff";
            })
            .attr("stroke-width", d => {
                const isPareto = this.isParetoOptimal(d.model);
                return isPareto ? 2 : 1;
            })
            .attr("opacity", 0.8)
            .on("mouseover", (event, d) => this.handleMouseOver(event, d))
            .on("mouseout", (event, d) => this.handleMouseOut(event, d))
            .on("click", (event, d) => this.handleClick(event, d));
    }

    /**
     * Handle mouseover on a data point
     */
    handleMouseOver(event, d) {
        d3.select(event.currentTarget)
            .transition()
            .duration(this.config.ANIMATION.HOVER_DURATION)
            .attr("r", this.getPointRadius(d, 'hover'))
            .attr("opacity", 1);

        const hoverEvent = new CustomEvent('modelHover', {
            detail: {
                model: d,
                x: event.pageX,
                y: event.pageY,
                isPareto: this.isParetoOptimal(d.model)
            }
        });
        document.dispatchEvent(hoverEvent);
    }

    /**
     * Handle mouse out event for data points
     */
    handleMouseOut(event, d) {
        d3.select(event.target)
            .transition()
            .duration(this.config.ANIMATION.HOVER_DURATION)
            .attr("r", this.getPointRadius(d))
            .attr("opacity", 0.8);

        document.dispatchEvent(new CustomEvent('modelUnhover'));
    }

    /**
     * Handle click event for data points
     */
    handleClick(event, d) {
        document.dispatchEvent(new CustomEvent('modelClick', {
            detail: { model: d }
        }));
    }

    /**
     * Pre-calculates positions for Pareto point labels to avoid collisions.
     */
    precomputeParetoLabels(scales) {
        this.paretoLabelInfo.clear();
        if (this.sortedParetoFrontier.length === 0) return;

        const { xScale, yScale } = scales;
        const { isMobile } = this.dimensions;

        this.sortedParetoFrontier.forEach((p, i) => {
            const p_left = i > 0 ? this.sortedParetoFrontier[i - 1] : null;
            const p_right = i < this.sortedParetoFrontier.length - 1 ? this.sortedParetoFrontier[i + 1] : null;

            // Default position: right of the point
            let anchor = "start";
            let x_offset = this.getPointRadius(p) + 5;
            let y_offset = 3;

            // If the point is on a convex part of the curve (a peak or elbow), move the label above it.
            if (p_left && p_right) {
                const x_p = xScale(p.price);
                const y_p = yScale(p.elo);
                const x_left = xScale(p_left.price);
                const y_left = yScale(p_left.elo);
                const x_right = xScale(p_right.price);
                const y_right = yScale(p_right.elo);

                if (x_right > x_left) {
                    // Find the y-coordinate on the line segment connecting the neighbors
                    const y_on_line = y_left + (y_right - y_left) * (x_p - x_left) / (x_right - x_left);
                    
                    // If the point's y is below the line on screen (higher ELO), it's a convex point.
                    // Add a small tolerance to handle near-straight lines.
                    if (y_p < y_on_line - 2) { 
                        anchor = "middle";
                        x_offset = 0;
                        y_offset = -this.getPointRadius(p) - 4;
                    }
                }
            }
            
            this.paretoLabelInfo.set(p.model, { anchor, x_offset, y_offset });
        });
    }
    
    /**
     * Render model labels
     */
    renderLabels(scales, data) {
        const { xScale, yScale } = scales;
        const { isMobile } = this.dimensions;

        this.svg.selectAll(".model-label")
            .data(data)
            .enter()
            .append("text")
            .attr("class", "model-label")
            .attr("text-anchor", d => {
                if (this.isParetoOptimal(d.model) && this.paretoLabelInfo.has(d.model)) {
                    return this.paretoLabelInfo.get(d.model).anchor;
                }
                return "start"; // Default for non-Pareto
            })
            .attr("x", d => {
                const xBase = xScale(d.price);
                if (this.isParetoOptimal(d.model) && this.paretoLabelInfo.has(d.model)) {
                    return xBase + this.paretoLabelInfo.get(d.model).x_offset;
                }
                const baseOffset = isMobile ? 4 : 6;
                return xBase + baseOffset;
            })
            .attr("y", d => {
                const yBase = yScale(d.elo);
                if (this.isParetoOptimal(d.model) && this.paretoLabelInfo.has(d.model)) {
                    return yBase + this.paretoLabelInfo.get(d.model).y_offset;
                }
                return yBase + 3;
            })
            .text(d => {
                if (isMobile) {
                    const isPareto = this.isParetoOptimal(d.model);
                    const dataIndex = data.indexOf(d);
                    return isPareto || dataIndex < 5 ? d.model : "";
                }
                return d.model;
            })
            .attr("fill", "#000")
            .style("font-weight", d => this.isParetoOptimal(d.model) ? "bold" : "normal")
            .style("opacity", d => this.isParetoOptimal(d.model) ? 1 : 0.7);
    }

    /**
     * Render Pareto frontier line
     */
    renderParetoLine(scales, paretoFrontier) {
        if (!paretoFrontier || paretoFrontier.length === 0) return;

        const { xScale, yScale } = scales;

        const lineGenerator = d3.line()
            .x(d => xScale(d.price))
            .y(d => yScale(d.elo));

        const sortedParetoFrontier = [...paretoFrontier]
            .sort((a, b) => a.price - b.price);

        this.svg.append("path")
            .datum(sortedParetoFrontier)
            .attr("fill", "none")
            .attr("stroke", this.config.CHART.COLORS.PARETO_LINE)
            .attr("stroke-width", 2)
            .attr("stroke-dasharray", "5,5")
            .attr("d", lineGenerator);
    }

    /**
     * Main render method for the chart
     */
    async render(data = [], paretoFrontier = []) {
        if (!this.container.node()) {
            console.error("Chart container not found.");
            return;
        }
        
        this.currentData = data;
        this.currentParetoFrontier = paretoFrontier;

        // Sort pareto frontier by price to determine neighbors for label placement
        if (paretoFrontier.length > 0) {
            this.sortedParetoFrontier = [...paretoFrontier].sort((a, b) => a.price - b.price);
            this.paretoIndexLookup = new Map(this.sortedParetoFrontier.map((p, i) => [p.model, i]));
        } else {
            this.sortedParetoFrontier = [];
            this.paretoIndexLookup.clear();
        }

        this.container.selectAll("*").remove();
        this.dimensions = this.calculateDimensions();

        this.svg = this.container
            .append("svg")
            .attr("width", this.dimensions.containerWidth)
            .attr("height", this.dimensions.containerHeight)
            .style("overflow", "visible")
            .append("g")
            .attr("transform", `translate(${this.dimensions.margin.left},${this.dimensions.margin.top})`);
        
        const scales = this.createScales();
        this.createAxes(scales);

        // Pre-calculate label positions for Pareto points
        this.precomputeParetoLabels(scales);
        
        this.renderDataPoints(scales, this.currentData);
        this.renderLabels(scales, this.currentData);
        this.renderParetoLine(scales, this.currentParetoFrontier);
    }
}
