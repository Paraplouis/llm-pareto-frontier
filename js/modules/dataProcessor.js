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

        const paretoOptimal = [];
        
        for (let i = 0; i < data.length; i++) {
            const currentModel = data[i];
            let isDominated = false;
            
            // Check if current model is dominated by any other model
            for (let j = 0; j < data.length; j++) {
                if (i === j) continue;
                
                const otherModel = data[j];
                
                // A model dominates another if it has higher or equal ELO AND lower or equal price
                // AND at least one of these is strictly better
                const hasHigherOrEqualElo = otherModel.elo >= currentModel.elo;
                const hasLowerOrEqualPrice = otherModel.price <= currentModel.price;
                const hasStrictlyHigherElo = otherModel.elo > currentModel.elo;
                const hasStrictlyLowerPrice = otherModel.price < currentModel.price;
                
                if (hasHigherOrEqualElo && hasLowerOrEqualPrice && 
                    (hasStrictlyHigherElo || hasStrictlyLowerPrice)) {
                    isDominated = true;
                    break;
                }
            }
            
            if (!isDominated) {
                paretoOptimal.push(currentModel);
            }
        }
        
        // Sort by ELO descending for better visualization
        return paretoOptimal.sort((a, b) => b.elo - a.elo);
    }

    /**
     * Get models by provider
     * @param {Array} data - Array of model objects
     * @param {string} provider - Provider name to filter by
     * @returns {Array} Models from the specified provider
     */
    getModelsByProvider(data, provider) {
        if (!Array.isArray(data)) {
            console.warn('Invalid data provided to getModelsByProvider');
            return [];
        }

        return data.filter(model => 
            model.cheapest_provider && model.cheapest_provider.toLowerCase() === provider.toLowerCase()
        );
    }

    /**
     * Get valid data by filtering out models with missing required fields
     * @param {Array} data - Array of model objects
     * @param {Set<string>} [activeProviders=null]
     * @returns {Array} Valid model data
     */
    getValidData(data, activeProviders = null) {
        if (!Array.isArray(data)) {
            console.warn('Invalid data provided to getValidData');
            return [];
        }

        let filteredData = data.filter(model => 
            model && 
            typeof model.elo === 'number' && 
            typeof model.price === 'number' &&
            model.elo > 0 && 
            model.price > 0 &&
            model.model
        );

        // Apply provider filter if activeProviders set is provided and not empty
        if (activeProviders && activeProviders.size > 0) {
            filteredData = filteredData.filter(model =>
                activeProviders.has(model.cheapest_provider)
            );
        }

        return filteredData;
    }

    /**
     * Get unique providers from data
     * @param {Array} data - Array of model objects
     * @returns {Array} Array of unique provider names
     */
    getUniqueProviders(data) {
        if (!Array.isArray(data)) {
            console.warn('Invalid data provided to getUniqueProviders');
            return [];
        }

        const providers = [...new Set(data.map(model => model.cheapest_provider).filter(Boolean))];
        return providers.sort();
    }
}
