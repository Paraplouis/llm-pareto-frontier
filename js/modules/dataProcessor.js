/**
 * Data processing module for LLM Pareto Frontier analysis
 * Handles data filtering and Pareto frontier calculations
 */
export class DataProcessor {
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

        // Compute effective price for each model
        const mappedData = filteredData.map(model => {
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
