/**
 * Data processing module for LLM Pareto Frontier analysis
 * Handles data filtering and Pareto frontier calculations
 */
export class DataProcessor {
    constructor() {
        /** Price lookup loaded from data/price_data.json */
        this.priceLookupMap = new Map(); // key: provider model lowercased -> { inputPrice, outputPrice, provider, originalName }
        this.priceItems = []; // array of entries for iteration
        this.isPriceLoaded = false;
        this.priceCache = new Map(); // key: `${modelName.toLowerCase()}|${in}:${out}` -> {provider, inputPrice, outputPrice}
    }

    /**
     * Load provider pricing catalog once for dynamic cheapest-provider computation
     */
    async loadPriceData() {
        if (this.isPriceLoaded) return;
        try {
            const response = await fetch('./data/price_data.json', { cache: 'no-store' });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const priceData = await response.json();
            const tmpMap = new Map();
            const items = [];
            priceData.forEach(providerEntry => {
                const provider = providerEntry.provider;
                (providerEntry.models || []).forEach(m => {
                    const key = (m.name || '').toLowerCase();
                    if (!key) return;
                    const entry = {
                        inputPrice: Number(m.inputPrice),
                        outputPrice: Number(m.outputPrice ?? m.inputPrice),
                        provider,
                        originalName: m.name
                    };
                    // Keep the cheapest input price for direct lookup collisions
                    const existing = tmpMap.get(key);
                    if (!existing || entry.inputPrice < existing.inputPrice) {
                        tmpMap.set(key, entry);
                    }
                    items.push({ key, ...entry });
                });
            });
            this.priceLookupMap = tmpMap;
            this.priceItems = items;
            this.isPriceLoaded = true;
        } catch (e) {
            console.warn('Failed to load price_data.json; falling back to embedded dataset prices.', e);
        }
    }

    /** Normalize model name similar to Python pipeline */
    normalizeModelName(name) {
        if (!name) return '';
        let n = String(name).toLowerCase();
        // Special cases
        n = n.replace(/\bchatgpt-4o\b/gi, 'gpt-4o');
        // Remove version dates and preview indicators
        n = n.replace(/-\d{4}-\d{2}-\d{2}|-\d{4,}/g, '');
        n = n.replace(/-\d{2}-\d{2}/g, '');
        n = n.replace(/preview.*|exp.*|latest.*|beta.*|v\d.*/g, '');
        // Remove quality/quantization indicators
        n = n.replace(/-bf16|-fp\d+|-instruct|-chat/gi, '');
        // Standardize model size indicators
        n = n.replace(/(\d+)b-/g, '$1b ');
        // Normalize separators
        n = n.replace(/[-_\s]+/g, ' ').trim();
        return n;
    }

    /** Compute bonus when model families align (claude, gpt, llama, etc.) */
    _familyBonus(modelLower, priceModelLower) {
        const families = ['claude','codellama','command','deepseek','gemma','gemini','gpt','grok','llama','mistral','mixtral','qwen'];
        let bonus = 0;
        for (const fam of families) {
            if (modelLower.includes(fam) && priceModelLower.includes(fam)) {
                bonus += 0.3;
                const mv = modelLower.match(/(\d+\.?\d*)/);
                const pv = priceModelLower.match(/(\d+\.?\d*)/);
                if (mv && pv && mv[1] === pv[1]) bonus += 0.2;
                break;
            }
        }
        return bonus;
    }

    /** Jaccard token similarity with family/version bonus */
    _similarityScore(modelLower, modelNorm, priceModel) {
        const modelParts = new Set(modelNorm.match(/\w+/g) || []);
        const priceNorm = this.normalizeModelName(priceModel);
        const priceParts = new Set(priceNorm.match(/\w+/g) || []);
        const union = new Set([...modelParts, ...priceParts]);
        let overlap = 0;
        modelParts.forEach(p => { if (priceParts.has(p)) overlap += 1; });
        if (overlap < 2 || union.size === 0) return 0;
        const similarity = overlap / union.size;
        const bonus = this._familyBonus(modelLower, priceModel.toLowerCase());
        return similarity + bonus;
    }

    /**
     * Find best provider for a model given current prompt/output tokens.
     * Returns null if pricing catalog not loaded or no reasonable match.
     */
    findBestProvider(modelName, promptTokens = 750, outputTokens = 250, excludeFree = false) {
        if (!this.isPriceLoaded || !this.priceItems.length || !modelName) return null;

        const cacheKey = `${modelName.toLowerCase()}|${promptTokens}:${outputTokens}|${excludeFree ? 'xfree' : 'all'}`;
        if (this.priceCache.has(cacheKey)) return this.priceCache.get(cacheKey);

        const total = Math.max(0, (promptTokens || 0)) + Math.max(0, (outputTokens || 0));
        const inputRatio = total > 0 ? (promptTokens || 0) / total : 1;

        const mLower = modelName.toLowerCase();
        const mNorm = this.normalizeModelName(modelName);

        // 1) direct exact lowercased match
        const direct = this.priceLookupMap.get(mLower);
        const candidates = [];
        if (direct) candidates.push({ key: mLower, ...direct, score: 2 });

        // 2) normalized equality
        if (!direct) {
            for (const { key, inputPrice, outputPrice, provider, originalName } of this.priceItems) {
                if (this.normalizeModelName(key) === mNorm) {
                    candidates.push({ key, inputPrice, outputPrice, provider, originalName, score: 1.5 });
                }
            }
        }

        // 3) fuzzy scan with threshold
        if (candidates.length === 0) {
            let best = null;
            let bestScore = 0;
            for (const { key, inputPrice, outputPrice, provider, originalName } of this.priceItems) {
                const score = this._similarityScore(mLower, mNorm, key);
                if (score > bestScore) {
                    bestScore = score;
                    best = { key, inputPrice, outputPrice, provider, originalName, score };
                }
            }
            if (best && best.score > 0.6) candidates.push(best);
        }

        if (candidates.length === 0) return null;

        // Choose the candidate with lowest effective price (respect excludeFree)
        let bestCand = null;
        let bestEff = Infinity;
        for (const c of candidates) {
            const ip = Number(c.inputPrice);
            const op = Number(c.outputPrice);
            if (excludeFree && (ip === 0 && op === 0)) continue;
            const eff = ip * inputRatio + op * (1 - inputRatio);
            if (eff < bestEff) {
                bestEff = eff;
                bestCand = c;
            }
        }
        if (!bestCand) return null;

        const result = {
            provider: bestCand.provider,
            providerModel: bestCand.originalName,
            inputPrice: Number(bestCand.inputPrice),
            outputPrice: Number(bestCand.outputPrice),
            effectivePrice: bestEff
        };
        this.priceCache.set(cacheKey, result);
        return result;
    }
    /**
     * Filter data based on price range
     * @param {Array} data - Array of model objects
     * @param {number} minPrice - Minimum price filter
     * @param {number} maxPrice - Maximum price filter
     * @returns {Array} Filtered data
     */
    filterByPrice(data, minPrice, maxPrice) {
        if (!Array.isArray(data)) {
            console.warn('Invalid data provided to filterByPrice');
            return [];
        }

        return data.filter(model => {
            const price = parseFloat(model.price);
            return price >= minPrice && price <= maxPrice;
        });
    }

    /**
     * Calculate Pareto frontier from model data
     * A model is Pareto optimal if no other model has both higher ELO and lower price
     * @param {Array} data - Array of model objects with elo and price properties
     * @returns {Array} Array of Pareto optimal models
     */
    calculateParetoFrontier(data) {
        if (!Array.isArray(data) || data.length === 0) {
            console.warn('Invalid or empty data provided to calculateParetoFrontier');
            return [];
        }

        // Efficient O(n log n) implementation
        // 1. Sort models by ascending price
        const sortedByPrice = [...data].sort((a, b) => a.price - b.price);

        const paretoOptimal = [];
        let maxEloSoFar = -Infinity;

        // 2. Sweep from cheapest to most expensive, keeping only models that
        //    improve on the best ELO encountered so far.
        for (const model of sortedByPrice) {
            if (model.elo > maxEloSoFar) {
                paretoOptimal.push(model);
                maxEloSoFar = model.elo;
            }
        }

        // Return by ELO desc for display
        return paretoOptimal.sort((a, b) => b.elo - a.elo);
    }

    /**
     * Get models by organization
     * @param {Array} data - Array of model objects
     * @param {string} organization - Organization name to filter by
     * @returns {Array} Models from the specified organization
     */
    getModelsByOrganization(data, organization) {
        if (!Array.isArray(data)) {
            console.warn('Invalid data provided to getModelsByOrganization');
            return [];
        }

        return data.filter(model =>
            model.organization && model.organization.toLowerCase() === organization.toLowerCase()
        );
    }

    /**
     * Get valid data by filtering out models with missing required fields
     * @param {Array} data - Array of model objects
     * @param {Set<string>} [activeOrganizations=null]
     * @param {boolean} [excludeFree=false]
     * @param {number} [promptTokens=750]
     * @param {number} [outputTokens=250]
     * @returns {Array} Valid model data
     */
    getValidData(data, activeOrganizations = null, excludeFree = false, promptTokens = 750, outputTokens = 250) {
        if (!Array.isArray(data)) {
            console.warn('Invalid data provided to getValidData');
            return [];
        }

        const totalTokens = promptTokens + outputTokens;
        const inputRatio = totalTokens > 0 ? promptTokens / totalTokens : 1;

        let filteredData = data.filter(model =>
            model &&
            typeof model.elo === 'number' &&
            (typeof model.input_price === 'number' || typeof model.price === 'number') &&
            model.elo > 0 &&
            // Honour excludeFree flag – only drop free models when requested
            (excludeFree ? (model.input_price ? model.input_price > 0 : model.price > 0) : true) &&
            model.model
        );

        // Apply organization filter if activeOrganizations set is provided and not empty
        if (activeOrganizations && activeOrganizations.size > 0) {
            filteredData = filteredData.filter(model =>
                activeOrganizations.has(model.organization)
            );
        }

        // Compute effective price and dynamic cheapest provider for each model (if catalog available)
        const mappedData = filteredData.map(model => {
            // Try dynamic provider lookup
            const best = this.findBestProvider(model.model, promptTokens, outputTokens, excludeFree);
            if (best) {
                return {
                    ...model,
                    input_price: best.inputPrice,
                    output_price: best.outputPrice,
                    cheapest_provider: best.provider,
                    provider_model: best.providerModel,
                    price: best.effectivePrice
                };
            }

            // Fallback to dataset's own prices
            if (typeof model.input_price === 'number' && typeof model.output_price === 'number') {
                const effectivePrice = (model.input_price * inputRatio) + (model.output_price * (1 - inputRatio));
                return { ...model, price: effectivePrice };
            }
            // Fallback to existing price field
            return model;
        });

        return mappedData;
    }

    /**
     * Get unique organizations from data
     * @param {Array} data - Array of model objects
     * @returns {Array} Array of unique organization names
     */
    getUniqueOrganizations(data) {
        if (!Array.isArray(data)) {
            console.warn('Invalid data provided to getUniqueOrganizations');
            return [];
        }

        const organizations = [...new Set(data.map(model => model.organization).filter(Boolean))];
        return organizations.sort();
    }
}
