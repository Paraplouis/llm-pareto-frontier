/**
 * Pure functions over the synthesized model records: filtering, price blending, Pareto frontier, and search.
 */

/** Models of the active organizations, each with `price` blending its input and output prices by the token mix. */
export function visibleModels(data, activeOrganizations, promptTokens, outputTokens) {
    const totalTokens = promptTokens + outputTokens;
    const inputShare = totalTokens > 0 ? promptTokens / totalTokens : 1;
    return data
        .filter(model => activeOrganizations.has(model.organization))
        .map(model => ({
            ...model,
            price: model.input_price * inputShare + model.output_price * (1 - inputShare),
        }));
}

/** Models that no other model beats on both price and ELO, by ELO descending. */
export function calculateParetoFrontier(data) {
    const paretoOptimal = [];
    let maxEloSoFar = -Infinity;
    for (const model of [...data].sort((a, b) => a.price - b.price || b.elo - a.elo)) {
        if (model.elo > maxEloSoFar) {
            paretoOptimal.push(model);
            maxEloSoFar = model.elo;
        }
    }
    return paretoOptimal.sort((a, b) => b.elo - a.elo);
}

/**
 * Cheapest frontier model that costs no more and scores at least as well as the given model.
 * Returns null for a model on the frontier.
 */
export function findCheaperAlternative(model, paretoFrontier) {
    if (paretoFrontier.includes(model)) return null;
    return paretoFrontier
        .filter(candidate => candidate.price <= model.price && candidate.elo >= model.elo)
        .reduce((best, candidate) => (!best || candidate.price < best.price ? candidate : best), null);
}

/** Models whose name contains every whitespace-separated term of the query, ignoring case. */
export function searchModels(data, query) {
    const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
    if (terms.length === 0) return [];
    return data.filter(model => {
        const name = model.model.toLowerCase();
        return terms.every(term => name.includes(term));
    });
}

export function uniqueOrganizations(data) {
    return [...new Set(data.map(model => model.organization))].sort();
}

/** ELO points between a model and the best model at its price or less; 0 on the frontier. */
export function eloGap(model, paretoFrontier) {
    const bestAtPrice = Math.max(...paretoFrontier.filter(step => step.price <= model.price).map(step => step.elo));
    return bestAtPrice - model.elo;
}

/** The top frontier model, and the cheapest frontier model within `maxGap` ELO points of it. */
export function valuePick(paretoFrontier, maxGap) {
    const leader = paretoFrontier[0];
    const value = paretoFrontier
        .filter(step => step.elo >= leader.elo - maxGap)
        .reduce((cheapest, step) => (step.price < cheapest.price ? step : cheapest));
    return { leader, value };
}

/** Share of head-to-head votes the higher-rated model is expected to win, from the ELO difference. */
export function winProbability(eloDifference) {
    return 1 / (1 + 10 ** (-eloDifference / 400));
}
