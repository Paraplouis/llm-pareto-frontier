/**
 * Scatter plot of ELO score against blended price, with the Pareto frontier drawn as a staircase.
 * Colors come from CSS custom properties, so a theme switch needs no re-render.
 */
const MARGIN = { top: 16, right: 20, bottom: 48, left: 56 };
const COMPACT_WIDTH = 600;
const PRICE_TICKS = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200];
const DECADE_TICKS = [0.01, 0.1, 1, 10, 100];
const DOT_RADIUS = { model: 3.5, frontier: 6 };
const HOVER_DISTANCE = 32;
const MAX_MATCH_LABELS = 12;
const LABEL_GAP = 4;

// Label slots as [horizontal side, vertical side]; the frontier staircase leaves a point's upper-left free.
const FRONTIER_LABEL_SLOTS = [[-1, -1], [1, -1], [-1, 0], [1, 1], [-1, 1]];
const MATCH_LABEL_SLOTS = [[1, 0], [-1, 0], [1, -1], [1, 1], [-1, -1]];

export class ChartRenderer {
    constructor(container, { onHover }) {
        this.container = container;
        this.onHover = onHover;
        this.data = null;
        this.frameRequest = null;
        new ResizeObserver(() => this.scheduleDraw()).observe(container);
    }

    render(data, frontier, matches) {
        this.data = data;
        this.frontier = new Set(frontier);
        this.matches = new Set(matches);
        this.draw();
    }

    /** Highlight a model as if hovered, or clear the highlight with null. */
    focus(model) {
        if (this.plot) this.setHovered(model);
    }

    scheduleDraw() {
        if (!this.data || this.frameRequest) return;
        this.frameRequest = requestAnimationFrame(() => {
            this.frameRequest = null;
            this.draw();
        });
    }

    draw() {
        this.plot = null;
        this.hovered = null;
        this.onHover(null);

        if (this.data.length === 0) {
            const message = document.createElement('div');
            message.className = 'chart-message';
            message.textContent = 'No models match the current filters.';
            this.container.replaceChildren(message);
            return;
        }

        const { clientWidth: width, clientHeight: height } = this.container;
        const innerWidth = width - MARGIN.left - MARGIN.right;
        const innerHeight = height - MARGIN.top - MARGIN.bottom;
        const isCompact = width < COMPACT_WIDTH;

        const [minPrice, maxPrice] = d3.extent(this.data, d => d.price);
        const [minElo, maxElo] = d3.extent(this.data, d => d.elo);
        this.x = d3.scaleLog().domain([minPrice / 1.3, maxPrice * 1.3]).range([0, innerWidth]);
        this.y = d3.scaleLinear().domain([minElo - 10, maxElo + 20]).nice().range([innerHeight, 0]);

        const svg = d3.create('svg')
            .attr('width', width)
            .attr('height', height)
            .attr('role', 'img')
            .attr('aria-label', 'Scatter plot of LM Arena ELO score against blended price per million tokens');
        svg.classed('has-matches', this.matches.size > 0);
        this.svgNode = svg.node();
        // Label placement measures text with getBBox, which needs the SVG in the document.
        this.container.replaceChildren(this.svgNode);
        this.plot = svg.append('g').attr('transform', `translate(${MARGIN.left},${MARGIN.top})`);

        this.drawAxes(innerWidth, innerHeight, isCompact);
        this.drawFrontier(innerWidth);
        const ordered = this.drawDots();
        this.drawLabels(innerWidth, innerHeight, isCompact);
        this.drawHoverLayer(ordered, innerWidth, innerHeight);
    }

    drawAxes(innerWidth, innerHeight, isCompact) {
        const [low, high] = this.x.domain();
        const priceTicks = PRICE_TICKS.filter(t => t >= low && t <= high);
        const decadeTicks = priceTicks.filter(t => DECADE_TICKS.includes(t));
        let xTicks = isCompact && decadeTicks.length >= 3 ? decadeTicks : priceTicks;
        if (xTicks.length < 2) xTicks = this.x.ticks(3);
        const yTicks = this.y.ticks(isCompact ? 5 : 7);

        this.plot.append('g').attr('class', 'grid').selectAll('line').data(yTicks).join('line')
            .attr('x2', innerWidth)
            .attr('y1', this.y)
            .attr('y2', this.y);
        this.plot.append('g').attr('class', 'grid').selectAll('line').data(xTicks).join('line')
            .attr('x1', this.x)
            .attr('x2', this.x)
            .attr('y2', innerHeight);

        this.plot.append('g')
            .attr('class', 'axis')
            .attr('transform', `translate(0,${innerHeight})`)
            .call(d3.axisBottom(this.x).tickValues(xTicks).tickFormat(t => `$${t}`).tickSizeOuter(0).tickPadding(8));

        this.plot.append('g')
            .attr('class', 'axis')
            .call(d3.axisLeft(this.y).tickValues(yTicks).tickFormat(d3.format('d')).tickSizeOuter(0).tickPadding(8));

        this.plot.append('text')
            .attr('class', 'axis-title')
            .attr('x', innerWidth / 2)
            .attr('y', innerHeight + 40)
            .attr('text-anchor', 'middle')
            .text(isCompact ? 'USD per million tokens, log' : 'Blended price per million tokens (USD, log scale)');

        this.plot.append('text')
            .attr('class', 'axis-title')
            .attr('transform', 'rotate(-90)')
            .attr('x', -innerHeight / 2)
            .attr('y', -44)
            .attr('text-anchor', 'middle')
            .text('LM Arena ELO score');
    }

    drawFrontier(innerWidth) {
        const steps = [...this.frontier].sort((a, b) => a.price - b.price);
        const corners = steps.map(d => [this.x(d.price), this.y(d.elo)]);
        corners.push([innerWidth, this.y(steps.at(-1).elo)]);
        // Each step is a horizontal run then a rise; labels must stay off both.
        this.frontierSegments = corners.slice(1).flatMap(([x, y], i) => {
            const [previousX, previousY] = corners[i];
            return [
                { x: previousX, y: previousY - 2, width: x - previousX, height: 4 },
                { x: x - 2, y, width: 4, height: previousY - y },
            ];
        });

        this.plot.append('path')
            .attr('class', 'frontier-line')
            .attr('d', d3.line().curve(d3.curveStepAfter)(corners));
    }

    drawDots() {
        const layer = d => (this.frontier.has(d) ? 2 : this.matches.has(d) ? 1 : 0);
        const ordered = [...this.data].sort((a, b) => layer(a) - layer(b));

        this.plot.append('g')
            .selectAll('circle')
            .data(ordered)
            .join('circle')
            .attr('class', d => {
                const classes = ['dot'];
                if (this.frontier.has(d)) classes.push('frontier');
                if (this.matches.has(d)) classes.push('match');
                return classes.join(' ');
            })
            .attr('cx', d => this.x(d.price))
            .attr('cy', d => this.y(d.elo))
            .attr('r', d => this.radius(d));

        return ordered;
    }

    radius(model) {
        return this.frontier.has(model) ? DOT_RADIUS.frontier : DOT_RADIUS.model;
    }

    drawLabels(innerWidth, innerHeight, isCompact) {
        const matchesToLabel = [...this.matches]
            .filter(d => !this.frontier.has(d))
            .sort((a, b) => b.elo - a.elo)
            .slice(0, MAX_MATCH_LABELS);
        const layer = this.plot.append('g');
        const annotation = layer.append('text')
            .attr('class', 'annotation')
            .attr('x', 10)
            .attr('y', 22)
            .text(isCompact ? 'Nothing beats the line.' : 'Up here, nothing: no model is cheaper and better ranked than the line.');
        const placed = [annotation.node().getBBox(), ...this.frontierSegments];

        const place = (model, className, label, slots, isRequired) => {
            const text = layer.append('text').attr('class', className).text(label);
            const px = this.x(model.price);
            const py = this.y(model.elo);
            const offset = this.radius(model) + LABEL_GAP;
            const tryPlace = ([side, level]) => {
                text.attr('x', px + side * offset)
                    .attr('y', level === 0 ? py + 4 : py + level * offset + (level > 0 ? 8 : 0))
                    .attr('text-anchor', side < 0 ? 'end' : 'start');
                return text.node().getBBox();
            };
            const fits = (box) => box.x >= 0 && box.y >= 0
                && box.x + box.width <= innerWidth && box.y + box.height <= innerHeight
                && !placed.some(other => overlaps(box, other));
            for (const slot of slots) {
                const box = tryPlace(slot);
                if (fits(box)) {
                    placed.push(box);
                    return;
                }
            }
            if (isRequired) {
                placed.push(tryPlace(slots[0]));
            } else {
                text.remove();
            }
        };

        [...this.frontier]
            .sort((a, b) => a.price - b.price)
            .forEach((model, index) => place(model, 'label', isCompact ? index + 1 : model.model, FRONTIER_LABEL_SLOTS, true));
        matchesToLabel.forEach(model => place(model, 'label match', model.model, MATCH_LABEL_SLOTS, false));
    }

    drawHoverLayer(ordered, innerWidth, innerHeight) {
        this.hoverRing = this.plot.append('circle').attr('class', 'hover-ring').attr('visibility', 'hidden');
        const delaunay = d3.Delaunay.from(ordered, d => this.x(d.price), d => this.y(d.elo));

        const handlePointer = (event) => {
            const [px, py] = d3.pointer(event);
            const model = ordered[delaunay.find(px, py)];
            const distance = Math.hypot(this.x(model.price) - px, this.y(model.elo) - py);
            this.setHovered(distance <= HOVER_DISTANCE ? model : null);
        };

        this.plot.append('rect')
            .attr('width', innerWidth)
            .attr('height', innerHeight)
            .attr('fill', 'transparent')
            .on('pointermove pointerdown', handlePointer)
            .on('pointerleave', () => this.setHovered(null));
    }

    setHovered(model) {
        if (model === this.hovered) return;
        this.hovered = model;
        if (!model) {
            this.hoverRing.attr('visibility', 'hidden');
            this.onHover(null);
            return;
        }

        const px = this.x(model.price);
        const py = this.y(model.elo);
        this.hoverRing
            .attr('cx', px)
            .attr('cy', py)
            .attr('r', this.radius(model) + 4)
            .attr('visibility', 'visible');

        const box = this.svgNode.getBoundingClientRect();
        this.onHover(model, box.left + MARGIN.left + px, box.top + MARGIN.top + py);
    }
}

function overlaps(a, b) {
    return a.x < b.x + b.width + 2 && b.x < a.x + a.width + 2 && a.y < b.y + b.height && b.y < a.y + a.height;
}
