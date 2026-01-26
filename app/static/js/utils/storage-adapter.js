/**
 * Storage Adapter - IndexedDB via localforage
 * 
 * Provides enhanced storage capacity (50MB-2GB+) compared to localStorage (5-10MB).
 * Automatically migrates data from localStorage to IndexedDB on first load.
 */

// Configure localforage
localforage.config({
    driver: [localforage.INDEXEDDB, localforage.LOCALSTORAGE, localforage.WEBSQL],
    name: 'tinychat',
    version: 1.0,
    storeName: 'tinychat_data',
    description: 'TinyChat conversation and configuration data'
});

// Storage adapter object
const storageAdapter = {
    /**
     * Get item from storage
     */
    async getItem(key) {
        try {
            return await localforage.getItem(key);
        } catch (error) {
            console.error(`Error getting item ${key}:`, error);
            return null;
        }
    },
    
    /**
     * Set item in storage
     */
    async setItem(key, value) {
        try {
            await localforage.setItem(key, value);
        } catch (error) {
            console.error(`Error setting item ${key}:`, error);
            throw error;
        }
    },
    
    /**
     * Remove item from storage
     */
    async removeItem(key) {
        try {
            await localforage.removeItem(key);
        } catch (error) {
            console.error(`Error removing item ${key}:`, error);
        }
    },
    
    /**
     * Clear all storage
     */
    async clear() {
        try {
            await localforage.clear();
        } catch (error) {
            console.error('Error clearing storage:', error);
        }
    },
    
    /**
     * Get all keys
     */
    async keys() {
        try {
            return await localforage.keys();
        } catch (error) {
            console.error('Error getting keys:', error);
            return [];
        }
    },
    
    /**
     * Get storage statistics
     */
    async getStorageStats() {
        try {
            // Use Storage API if available (modern browsers)
            if (navigator.storage && navigator.storage.estimate) {
                const estimate = await navigator.storage.estimate();
                const used = estimate.usage || 0;
                const quota = estimate.quota || 0;
                
                return {
                    used: used,
                    usedMB: used / 1024 / 1024,
                    quota: quota,
                    totalMB: quota / 1024 / 1024,
                    percentUsed: quota > 0 ? (used / quota) * 100 : 0,
                    available: true
                };
            }
            
            // Fallback: estimate from stored data
            const keys = await this.keys();
            let totalSize = 0;
            
            for (const key of keys) {
                const item = await this.getItem(key);
                if (item !== null) {
                    totalSize += JSON.stringify(item).length;
                }
            }
            
            return {
                used: totalSize,
                usedMB: totalSize / 1024 / 1024,
                quota: null,
                totalMB: 0,
                percentUsed: 0,
                available: false
            };
        } catch (error) {
            console.error('Error getting storage stats:', error);
            return {
                used: 0,
                usedMB: 0,
                quota: null,
                totalMB: 0,
                percentUsed: 0,
                available: false
            };
        }
    },
    
    /**
     * Export all data as JSON (for debugging/backup)
     */
    async exportData() {
        try {
            const keys = await this.keys();
            const data = {};
            
            for (const key of keys) {
                data[key] = await this.getItem(key);
            }
            
            return {
                exportDate: new Date().toISOString(),
                version: '1.0',
                data: data
            };
        } catch (error) {
            console.error('Error exporting data:', error);
            return null;
        }
    },
    
    /**
     * Import data from JSON export
     */
    async importData(exportedData) {
        try {
            if (!exportedData || !exportedData.data) {
                throw new Error('Invalid export data');
            }
            
            for (const [key, value] of Object.entries(exportedData.data)) {
                await this.setItem(key, value);
            }
            
            return true;
        } catch (error) {
            console.error('Error importing data:', error);
            return false;
        }
    },
    
    /**
     * Migrate data from localStorage to IndexedDB
     * Runs automatically on first load, clears localStorage when done
     */
    async migrateFromLocalStorage() {
        try {
            // Check if already migrated
            const migrated = await this.getItem('_migration_complete');
            if (migrated) {
                console.log('Already migrated to IndexedDB');
                return { success: true, alreadyMigrated: true };
            }
            
            console.log('Starting migration from localStorage to IndexedDB...');
            
            // Keys to migrate
            const keysToMigrate = [
                'tinychat_conversations',
                'tinychat_markdown_enabled',
                'tinychat_selected_model',
                'tinychat_rlm_enabled',
                'tinychat_rlm_thinking_enabled',
                'tinychat_session_id'
            ];
            
            let migratedCount = 0;
            
            // Migrate each key
            for (const key of keysToMigrate) {
                const value = localStorage.getItem(key);
                if (value !== null) {
                    try {
                        // Try to parse as JSON for objects/arrays
                        let parsedValue = value;
                        if (key === 'tinychat_conversations') {
                            parsedValue = JSON.parse(value);
                        }
                        // For other keys, keep as string
                        
                        await this.setItem(key, parsedValue);
                        migratedCount++;
                        console.log(`Migrated ${key}`);
                    } catch (e) {
                        // If parse fails, store as-is
                        await this.setItem(key, value);
                        migratedCount++;
                    }
                }
            }
            
            // Mark migration complete
            await this.setItem('_migration_complete', {
                completed: true,
                date: new Date().toISOString(),
                migratedKeys: migratedCount
            });
            
            console.log(`Migration complete! Migrated ${migratedCount} items.`);
            
            // Clear old localStorage (clean break as requested)
            for (const key of keysToMigrate) {
                localStorage.removeItem(key);
            }
            console.log('Cleared old localStorage data');
            
            return { 
                success: true, 
                migratedCount,
                alreadyMigrated: false
            };
            
        } catch (error) {
            console.error('Migration failed:', error);
            
            // Show warning to user but allow fallback to localStorage
            if (typeof showError === 'function') {
                showError('⚠️ Could not migrate to enhanced storage. Using limited storage mode. You may encounter storage limits with images.');
            }
            
            return { 
                success: false, 
                error: error.message,
                fallbackToLocalStorage: true
            };
        }
    }
};

/**
 * Check storage driver being used
 */
function getStorageDriver() {
    const driver = localforage.driver();
    const driverNames = {
        [localforage.INDEXEDDB]: 'IndexedDB',
        [localforage.WEBSQL]: 'WebSQL',
        [localforage.LOCALSTORAGE]: 'localStorage'
    };
    return driverNames[driver] || 'Unknown';
}

console.log(`Storage driver: ${getStorageDriver()}`);
