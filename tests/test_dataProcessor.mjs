import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
    calculateParetoFrontier,
    eloGap,
    findCheaperAlternative,
    searchModels,
    valuePick,
    visibleModels,
    winProbability,
} from '../js/modules/dataProcessor.js';

describe('visibleModels', () => {
    const models = [
        { model: 'Kept', elo: 1400, input_price: 2, output_price: 10, organization: 'A' },
        { model: 'Hidden', elo: 1350, input_price: 1, output_price: 1, organization: 'B' },
    ];

    it('keeps active organizations and blends prices by the token mix', () => {
        const visible = visibleModels(models, new Set(['A']), 750, 250);
        assert.deepEqual(visible.map(m => m.model), ['Kept']);
        assert.equal(visible[0].price, 2 * 0.75 + 10 * 0.25);
    });

    it('uses the input price alone when there are no tokens', () => {
        assert.equal(visibleModels(models, new Set(['A']), 0, 0)[0].price, 2);
    });
});

describe('calculateParetoFrontier', () => {
    it('returns correct Pareto set for known inputs', () => {
        const data = [
            { model: 'A', elo: 1400, price: 10 },
            { model: 'B', elo: 1300, price: 5 },
            { model: 'C', elo: 1200, price: 1 },
            { model: 'D', elo: 1100, price: 3 },  // dominated by C (cheaper) and B (higher elo)
        ];
        const pareto = calculateParetoFrontier(data);
        const names = pareto.map(m => m.model);
        assert.deepEqual(names, ['A', 'B', 'C']);
    });

    it('returns empty array for empty input', () => {
        assert.deepEqual(calculateParetoFrontier([]), []);
    });

    it('returns single model when only one provided', () => {
        const data = [{ model: 'X', elo: 1500, price: 5 }];
        const pareto = calculateParetoFrontier(data);
        assert.equal(pareto.length, 1);
        assert.equal(pareto[0].model, 'X');
    });

    it('keeps only the better model of a price tie, whatever the input order', () => {
        const data = [
            { model: 'B', elo: 1300, price: 5 },
            { model: 'A', elo: 1400, price: 5 },
        ];
        assert.deepEqual(calculateParetoFrontier(data).map(m => m.model), ['A']);
    });
});

describe('findCheaperAlternative', () => {
    const cheap = { model: 'Cheap', elo: 1300, price: 1 };
    const mid = { model: 'Mid', elo: 1400, price: 4 };
    const top = { model: 'Top', elo: 1500, price: 20 };
    const frontier = [top, mid, cheap];

    it('returns null for a frontier model', () => {
        assert.equal(findCheaperAlternative(mid, frontier), null);
    });

    it('returns the cheapest frontier model that scores at least as well', () => {
        const dominated = { model: 'Dominated', elo: 1350, price: 10 };
        assert.equal(findCheaperAlternative(dominated, frontier), mid);
    });

    it('accepts an equal score at a lower price', () => {
        const dominated = { model: 'Dominated', elo: 1300, price: 3 };
        assert.equal(findCheaperAlternative(dominated, frontier), cheap);
    });
});

describe('searchModels', () => {
    const models = [
        { model: 'Gemini 3.8 Flash (High)' },
        { model: 'Gemini 4 Argon (High)' },
        { model: 'GLM-5.3-Flash' },
    ];

    it('requires every term, ignoring case and order', () => {
        assert.deepEqual(searchModels(models, 'flash GEMINI').map(m => m.model), ['Gemini 3.8 Flash (High)']);
    });

    it('returns no match for a blank query', () => {
        assert.deepEqual(searchModels(models, '   '), []);
    });
});

describe('eloGap', () => {
    const cheap = { model: 'Cheap', elo: 1300, price: 1 };
    const top = { model: 'Top', elo: 1500, price: 20 };

    it('measures the distance to the best model at the same price or less', () => {
        assert.equal(eloGap({ model: 'Mid', elo: 1250, price: 10 }, [top, cheap]), 50);
    });

    it('is zero on the frontier', () => {
        assert.equal(eloGap(top, [top, cheap]), 0);
    });
});

describe('valuePick', () => {
    const leader = { model: 'Leader', elo: 1520, price: 4 };
    const close = { model: 'Close', elo: 1480, price: 0.4 };
    const far = { model: 'Far', elo: 1400, price: 0.05 };

    it('picks the cheapest frontier model within the gap of the leader', () => {
        assert.deepEqual(valuePick([leader, close, far], 50), { leader, value: close });
    });

    it('falls back to the leader when nothing cheaper is close', () => {
        assert.deepEqual(valuePick([leader, far], 50), { leader, value: leader });
    });
});

describe('winProbability', () => {
    it('gives about 57% for a 50-point lead', () => {
        assert.equal(Math.round(winProbability(50) * 100), 57);
    });
});
