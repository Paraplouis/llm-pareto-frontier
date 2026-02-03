import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

// Inline the class under test to avoid needing a browser/d3 environment.
// This mirrors the logic in js/modules/dataProcessor.js exactly.

class DataProcessor {
    constructor() {
        this.priceLookupMap = new Map();
        this.priceItems = [];
        this.isPriceLoaded = false;
        this.priceCache = new Map();
    }

    normalizeModelName(name) {
        if (!name) return '';
        let n = String(name).toLowerCase();
        n = n.replace(/\bchatgpt-4o\b/gi, 'gpt-4o');
        n = n.replace(/\bqwen3-max-preview\b/gi, 'qwen-max-latest');
        n = n.replace(/\bdbrx-instruct-preview\b/gi, 'dbrx instruct');
        n = n.replace(/\bsolar-10\.7b-instruct-v1\.0\b/gi, 'upstage solar instruct v1 (11b)');
        n = n.replace(/\bqwen3-32b\b/gi, 'qwen 3-32b');
        n = n.replace(/\bglm-4-plus\b/gi, 'glm-4-32b-0414-128k');
        n = n.replace(/[\s-]instruct\b/g, '');
        n = n.replace(/[\s-]chat\b/g, '');
        n = n.replace(/[\s-]online\b/g, '');
        n = n.replace(/-\d{4}-\d{2}-\d{2}|-\d{4,}/g, '');
        n = n.replace(/-\d{2}-\d{2}/g, '');
        n = n.replace(/preview.*|exp.*|latest.*|beta.*|v\d.*/g, '');
        n = n.replace(/-bf16|-fp\d+|-instruct|-chat/gi, '');
        n = n.replace(/(\d+)b-/g, '$1b ');
        n = n.replace(/[-_\s]+/g, ' ').trim();
        return n;
    }

    calculateParetoFrontier(data) {
        if (!Array.isArray(data) || data.length === 0) return [];
        const sortedByPrice = [...data].sort((a, b) => a.price - b.price);
        const paretoOptimal = [];
        let maxEloSoFar = -Infinity;
        for (const model of sortedByPrice) {
            if (model.elo > maxEloSoFar) {
                paretoOptimal.push(model);
                maxEloSoFar = model.elo;
            }
        }
        return paretoOptimal.sort((a, b) => b.elo - a.elo);
    }
}

const dp = new DataProcessor();

// ---------- normalizeModelName ----------

describe('normalizeModelName', () => {
    it('maps chatgpt-4o to gpt-4o', () => {
        assert.equal(dp.normalizeModelName('chatgpt-4o-2024-05-13'), 'gpt 4o');
    });

    it('maps qwen3-max-preview', () => {
        assert.equal(dp.normalizeModelName('qwen3-max-preview'), 'qwen max');
    });

    it('maps dbrx-instruct-preview', () => {
        assert.equal(dp.normalizeModelName('dbrx-instruct-preview'), 'dbrx');
    });

    it('maps solar-10.7b-instruct-v1.0', () => {
        const result = dp.normalizeModelName('solar-10.7b-instruct-v1.0');
        assert.ok(result.includes('upstage') && result.includes('solar'), `Expected upstage solar in "${result}"`);
    });

    it('maps qwen3-32b', () => {
        assert.equal(dp.normalizeModelName('qwen3-32b'), 'qwen 3 32b');
    });

    it('maps glm-4-plus', () => {
        const result = dp.normalizeModelName('glm-4-plus');
        assert.ok(result.includes('glm'), `Expected glm in "${result}"`);
    });

    it('removes -online suffix', () => {
        const result = dp.normalizeModelName('command-r-online');
        assert.ok(!result.includes('online'), `Unexpected online in "${result}"`);
    });

    it('removes date suffixes', () => {
        assert.equal(dp.normalizeModelName('gpt-4o-2024-08-06'), 'gpt 4o');
    });

    it('handles empty/null input', () => {
        assert.equal(dp.normalizeModelName(''), '');
        assert.equal(dp.normalizeModelName(null), '');
        assert.equal(dp.normalizeModelName(undefined), '');
    });
});

// ---------- calculateParetoFrontier ----------

describe('calculateParetoFrontier', () => {
    it('returns correct Pareto set for known inputs', () => {
        const data = [
            { model: 'A', elo: 1400, price: 10 },
            { model: 'B', elo: 1300, price: 5 },
            { model: 'C', elo: 1200, price: 1 },
            { model: 'D', elo: 1100, price: 3 },  // dominated by C (cheaper) and B (higher elo)
        ];
        const pareto = dp.calculateParetoFrontier(data);
        const names = pareto.map(m => m.model);
        assert.deepEqual(names, ['A', 'B', 'C']);
    });

    it('returns empty array for empty input', () => {
        assert.deepEqual(dp.calculateParetoFrontier([]), []);
    });

    it('returns single model when only one provided', () => {
        const data = [{ model: 'X', elo: 1500, price: 5 }];
        const pareto = dp.calculateParetoFrontier(data);
        assert.equal(pareto.length, 1);
        assert.equal(pareto[0].model, 'X');
    });

    it('handles tied prices correctly', () => {
        const data = [
            { model: 'A', elo: 1400, price: 5 },
            { model: 'B', elo: 1300, price: 5 },
        ];
        const pareto = dp.calculateParetoFrontier(data);
        // Only A should be Pareto (same price, higher ELO)
        assert.equal(pareto.length, 1);
        assert.equal(pareto[0].model, 'A');
    });

    it('handles non-array input', () => {
        assert.deepEqual(dp.calculateParetoFrontier(null), []);
        assert.deepEqual(dp.calculateParetoFrontier('bad'), []);
    });
});
