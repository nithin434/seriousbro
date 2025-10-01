import logging
import json
from datetime import datetime, timedelta
from typing import Any, Optional, Dict, List
from bson import ObjectId

logger = logging.getLogger(__name__)

class CentralizedCacheManager:
    """
    Centralized cache manager for all application data with MongoDB backend
    Supports configurable expiration times and automatic cleanup
    """
    
    def __init__(self, db_connection):
        """
        Initialize cache manager with database connection
        
        Args:
            db_connection: MongoDB database connection
        """
        self.db = db_connection
        self.cache_collection = self.db.centralized_cache
        
        # Create index for automatic expiration
        try:
            self.cache_collection.create_index(
                "expires_at", 
                expireAfterSeconds=0
            )
            logger.info("Cache expiration index created successfully")
        except Exception as e:
            logger.warning(f"Cache index creation warning: {e}")
    
    def _serialize_data(self, data: Any) -> Any:
        """Serialize data to be JSON compatible"""
        if isinstance(data, dict):
            return {k: self._serialize_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._serialize_data(item) for item in data]
        elif isinstance(data, ObjectId):
            return str(data)
        elif isinstance(data, datetime):
            return data.isoformat()
        else:
            return data
    
    def set(self, key: str, data: Any, expiry_days: int = 5, cache_type: str = "general") -> bool:
        """
        Store data in cache with expiration
        
        Args:
            key: Unique cache key
            data: Data to cache
            expiry_days: Number of days until expiration (default: 5)
            cache_type: Type of cache for organization (e.g., 'profile', 'resume', 'job')
            
        Returns:
            bool: Success status
        """
        try:
            # Serialize data
            serialized_data = self._serialize_data(data)
            
            # Create cache document
            cache_document = {
                'cache_key': key,
                'cache_type': cache_type,
                'data': serialized_data,
                'cached_at': datetime.now(),
                'expires_at': datetime.now() + timedelta(days=expiry_days),
                'expiry_days': expiry_days
            }
            
            # Use upsert to replace existing cache
            result = self.cache_collection.replace_one(
                {'cache_key': key},
                cache_document,
                upsert=True
            )
            
            logger.info(f"Cached data for key: {key} (type: {cache_type}, expires in {expiry_days} days)")
            return True
            
        except Exception as e:
            logger.error(f"Error caching data for key {key}: {str(e)}")
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve data from cache if not expired
        
        Args:
            key: Cache key to retrieve
            
        Returns:
            Cached data or None if not found/expired
        """
        try:
            # MongoDB TTL will automatically remove expired documents
            cached_result = self.cache_collection.find_one({
                'cache_key': key
            })
            
            if cached_result:
                # Double-check expiration (in case TTL hasn't run yet)
                if datetime.now() < cached_result['expires_at']:
                    logger.info(f"Cache hit for key: {key}")
                    return cached_result['data']
                else:
                    # Manually remove expired entry
                    self.cache_collection.delete_one({'cache_key': key})
                    logger.info(f"Cache expired for key: {key}, removed")
            
            logger.info(f"Cache miss for key: {key}")
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving cache for key {key}: {str(e)}")
            return None
    
    def delete(self, key: str) -> bool:
        """
        Delete specific cache entry
        
        Args:
            key: Cache key to delete
            
        Returns:
            bool: Success status
        """
        try:
            result = self.cache_collection.delete_one({'cache_key': key})
            logger.info(f"Deleted cache entry for key: {key}")
            return result.deleted_count > 0
            
        except Exception as e:
            logger.error(f"Error deleting cache for key {key}: {str(e)}")
            return False
    
    def clear_by_type(self, cache_type: str) -> int:
        """
        Clear all cache entries of a specific type
        
        Args:
            cache_type: Type of cache to clear
            
        Returns:
            int: Number of entries deleted
        """
        try:
            result = self.cache_collection.delete_many({'cache_type': cache_type})
            logger.info(f"Cleared {result.deleted_count} cache entries of type: {cache_type}")
            return result.deleted_count
            
        except Exception as e:
            logger.error(f"Error clearing cache type {cache_type}: {str(e)}")
            return 0
    
    def clear_expired(self) -> int:
        """
        Manually clear expired cache entries
        
        Returns:
            int: Number of entries deleted
        """
        try:
            result = self.cache_collection.delete_many({
                'expires_at': {'$lt': datetime.now()}
            })
            logger.info(f"Manually cleared {result.deleted_count} expired cache entries")
            return result.deleted_count
            
        except Exception as e:
            logger.error(f"Error clearing expired cache: {str(e)}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics
        
        Returns:
            dict: Cache statistics
        """
        try:
            # Total entries
            total_entries = self.cache_collection.count_documents({})
            
            # Expired entries
            expired_entries = self.cache_collection.count_documents({
                'expires_at': {'$lt': datetime.now()}
            })
            
            # Recent entries (last 24 hours)
            recent_entries = self.cache_collection.count_documents({
                'cached_at': {'$gte': datetime.now() - timedelta(hours=24)}
            })
            
            # Entries by type
            pipeline = [
                {'$group': {'_id': '$cache_type', 'count': {'$sum': 1}}},
                {'$sort': {'count': -1}}
            ]
            type_distribution = list(self.cache_collection.aggregate(pipeline))
            
            # Entries by expiry days
            expiry_pipeline = [
                {'$group': {'_id': '$expiry_days', 'count': {'$sum': 1}}},
                {'$sort': {'_id': 1}}
            ]
            expiry_distribution = list(self.cache_collection.aggregate(expiry_pipeline))
            
            return {
                'total_entries': total_entries,
                'expired_entries': expired_entries,
                'valid_entries': total_entries - expired_entries,
                'recent_entries_24h': recent_entries,
                'type_distribution': type_distribution,
                'expiry_distribution': expiry_distribution,
                'database_status': 'connected'
            }
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {str(e)}")
            return {
                'total_entries': 0,
                'expired_entries': 0,
                'valid_entries': 0,
                'recent_entries_24h': 0,
                'type_distribution': [],
                'expiry_distribution': [],
                'database_status': 'error',
                'error': str(e)
            }
    
    def exists(self, key: str) -> bool:
        """
        Check if cache key exists and is not expired
        
        Args:
            key: Cache key to check
            
        Returns:
            bool: True if exists and valid
        """
        try:
            cached_result = self.cache_collection.find_one({
                'cache_key': key,
                'expires_at': {'$gt': datetime.now()}
            })
            return cached_result is not None
            
        except Exception as e:
            logger.error(f"Error checking cache existence for key {key}: {str(e)}")
            return False
    
    def extend_expiry(self, key: str, additional_days: int = 5) -> bool:
        """
        Extend expiration time for a cache entry
        
        Args:
            key: Cache key to extend
            additional_days: Additional days to add
            
        Returns:
            bool: Success status
        """
        try:
            result = self.cache_collection.update_one(
                {'cache_key': key},
                {
                    '$set': {
                        'expires_at': datetime.now() + timedelta(days=additional_days),
                        'expiry_days': additional_days,
                        'extended_at': datetime.now()
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"Extended cache expiry for key: {key} by {additional_days} days")
                return True
            else:
                logger.warning(f"Cache key not found for extension: {key}")
                return False
                
        except Exception as e:
            logger.error(f"Error extending cache expiry for key {key}: {str(e)}")
            return False

# Global cache instance (will be initialized in main.py)
cache_manager = None

def get_cache_manager():
    """Get the global cache manager instance"""
    global cache_manager
    if cache_manager is None:
        raise RuntimeError("Cache manager not initialized. Call init_cache_manager() first.")
    return cache_manager

def init_cache_manager(db_connection):
    """Initialize the global cache manager"""
    global cache_manager
    cache_manager = CentralizedCacheManager(db_connection)
    logger.info("Centralized cache manager initialized")
    return cache_manager

# Convenience functions for common cache operations
def cache_set(key: str, data: Any, expiry_days: int = 5, cache_type: str = "general") -> bool:
    """Convenience function to set cache data"""
    return get_cache_manager().set(key, data, expiry_days, cache_type)

def cache_get(key: str) -> Optional[Any]:
    """Convenience function to get cache data"""
    return get_cache_manager().get(key)

def cache_delete(key: str) -> bool:
    """Convenience function to delete cache data"""
    return get_cache_manager().delete(key)

def cache_exists(key: str) -> bool:
    """Convenience function to check if cache exists"""
    return get_cache_manager().exists(key)
