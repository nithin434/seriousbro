import os
import logging
import pymongo
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, OperationFailure
import threading
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import weakref

logger = logging.getLogger(__name__)

class DatabasePoolManager:
    """
    Singleton Database Pool Manager for handling multiple concurrent users
    Provides connection pooling, monitoring, and optimization
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(DatabasePoolManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
            
        self._initialized = True
        self._clients = {}  # Store client instances
        self._connection_stats = {
            'total_connections': 0,
            'active_connections': 0,
            'failed_connections': 0,
            'last_health_check': None,
            'connection_errors': []
        }
        
        # Configuration for connection pooling
        self.pool_config = {
            'maxPoolSize': 100,  # Maximum connections in pool
            'minPoolSize': 10,   # Minimum connections in pool
            'maxIdleTimeMS': 300000,  # 5 minutes idle timeout
            'waitQueueTimeoutMS': 5000,  # 5 seconds wait timeout
            'connectTimeoutMS': 10000,   # 10 seconds connection timeout
            'serverSelectionTimeoutMS': 5000,  # 5 seconds server selection timeout
            'heartbeatFrequencyMS': 10000,  # 10 seconds heartbeat
            'retryWrites': True,
            'retryReads': True,
            'w': 'majority',  # Write concern
            'readPreference': 'primaryPreferred'
        }
        
        # MongoDB URI with authentication
        self.mongo_uri = self._build_mongo_uri()
        
        # Initialize main client
        self._main_client = None
        self._initialize_main_client()
        
        # Start background monitoring
        self._start_monitoring()
        
        logger.info(f"Database Pool Manager initialized with config: {self.pool_config}")
    
    def _build_mongo_uri(self) -> str:
        """Build MongoDB URI with optimal settings for pooling"""
        # Get MongoDB configuration from environment
        mongo_host = os.getenv('MONGO_HOST', 'localhost')
        mongo_port = os.getenv('MONGO_PORT', '27017')
        mongo_username = os.getenv('MONGO_USERNAME', '')
        mongo_password = os.getenv('MONGO_PASSWORD', '')
        mongo_db = os.getenv('MONGO_DB', 'resume_ai')
        
        # Build URI
        if mongo_username and mongo_password:
            mongo_uri = f"mongodb://{mongo_username}:{mongo_password}@{mongo_host}:{mongo_port}/{mongo_db}"
        else:
            mongo_uri = f"mongodb://{mongo_host}:{mongo_port}/{mongo_db}"
        
        # Add connection pool parameters
        pool_params = [
            f"maxPoolSize={self.pool_config['maxPoolSize']}",
            f"minPoolSize={self.pool_config['minPoolSize']}",
            f"maxIdleTimeMS={self.pool_config['maxIdleTimeMS']}",
            f"waitQueueTimeoutMS={self.pool_config['waitQueueTimeoutMS']}",
            f"connectTimeoutMS={self.pool_config['connectTimeoutMS']}",
            f"serverSelectionTimeoutMS={self.pool_config['serverSelectionTimeoutMS']}",
            f"heartbeatFrequencyMS={self.pool_config['heartbeatFrequencyMS']}",
            f"retryWrites={str(self.pool_config['retryWrites']).lower()}",
            f"retryReads={str(self.pool_config['retryReads']).lower()}",
            f"w={self.pool_config['w']}",
            f"readPreference={self.pool_config['readPreference']}"
        ]
        
        # Add parameters to URI
        separator = '&' if '?' in mongo_uri else '?'
        mongo_uri_with_params = mongo_uri + separator + '&'.join(pool_params)
        
        logger.info(f"Built MongoDB URI with pooling parameters")
        return mongo_uri_with_params
    
    def _initialize_main_client(self):
        """Initialize the main MongoDB client with retry logic"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                self._main_client = MongoClient(self.mongo_uri)
                
                # Test the connection
                self._main_client.admin.command('ping')
                
                self._connection_stats['total_connections'] += 1
                self._connection_stats['active_connections'] += 1
                self._connection_stats['last_health_check'] = datetime.now()
                
                logger.info(f"Main MongoDB client initialized successfully on attempt {attempt + 1}")
                return
                
            except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                self._connection_stats['failed_connections'] += 1
                self._connection_stats['connection_errors'].append({
                    'timestamp': datetime.now(),
                    'error': str(e),
                    'attempt': attempt + 1
                })
                
                if attempt < max_retries - 1:
                    logger.warning(f"MongoDB connection attempt {attempt + 1} failed: {e}. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error(f"Failed to initialize MongoDB client after {max_retries} attempts: {e}")
                    raise
    
    def get_client(self, client_id: str = "default") -> MongoClient:
        """
        Get a MongoDB client instance with connection pooling
        
        Args:
            client_id: Identifier for the client (useful for tracking different components)
            
        Returns:
            MongoClient instance
        """
        try:
            # For now, return the main client as it handles pooling internally
            # In future, we could implement per-component clients if needed
            if self._main_client is None:
                self._initialize_main_client()
            
            # Test connection health
            if not self._is_client_healthy(self._main_client):
                logger.warning(f"Main client unhealthy, reinitializing...")
                self._initialize_main_client()
            
            return self._main_client
            
        except Exception as e:
            logger.error(f"Error getting MongoDB client for {client_id}: {e}")
            self._connection_stats['failed_connections'] += 1
            raise
    
    def get_database(self, db_name: str = None, client_id: str = "default"):
        """
        Get a database instance with connection pooling
        
        Args:
            db_name: Database name (defaults to environment config)
            client_id: Client identifier
            
        Returns:
            Database instance
        """
        try:
            client = self.get_client(client_id)
            
            if db_name is None:
                db_name = os.getenv('MONGO_DB', 'resume_ai')
            
            database = client[db_name]
            
            # Test database connection
            database.command('ping')
            
            return database
            
        except Exception as e:
            logger.error(f"Error getting database {db_name} for client {client_id}: {e}")
            raise
    
    def _is_client_healthy(self, client: MongoClient) -> bool:
        """Check if a MongoDB client is healthy"""
        try:
            # Quick ping test
            client.admin.command('ping')
            return True
        except Exception as e:
            logger.warning(f"Client health check failed: {e}")
            return False
    
    def _start_monitoring(self):
        """Start background monitoring of connection health"""
        def monitor_connections():
            while True:
                try:
                    time.sleep(30)  # Check every 30 seconds
                    self._perform_health_check()
                    self._cleanup_old_errors()
                except Exception as e:
                    logger.error(f"Error in connection monitoring: {e}")
        
        monitor_thread = threading.Thread(target=monitor_connections, daemon=True)
        monitor_thread.start()
        logger.info("Started database connection monitoring thread")
    
    def _perform_health_check(self):
        """Perform periodic health check on connections"""
        try:
            if self._main_client:
                start_time = time.time()
                self._main_client.admin.command('ping')
                response_time = (time.time() - start_time) * 1000  # Convert to ms
                
                self._connection_stats['last_health_check'] = datetime.now()
                
                if response_time > 1000:  # Log if response time > 1 second
                    logger.warning(f"Slow database response: {response_time:.2f}ms")
                    
                # Log basic connection info
                try:
                    # Get server info to verify connection
                    server_info = self._main_client.server_info()
                    logger.debug(f"MongoDB server version: {server_info.get('version', 'unknown')}")
                except Exception as info_error:
                    logger.debug(f"Could not get server info: {info_error}")
                        
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            self._connection_stats['failed_connections'] += 1
    
    def _cleanup_old_errors(self):
        """Clean up old error records to prevent memory bloat"""
        cutoff_time = datetime.now() - timedelta(hours=24)
        self._connection_stats['connection_errors'] = [
            error for error in self._connection_stats['connection_errors']
            if error['timestamp'] > cutoff_time
        ]
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get current connection statistics"""
        stats = self._connection_stats.copy()
        
        # Add current pool information
        if self._main_client:
            try:
                # Get server info
                server_info = self._main_client.server_info()
                stats['server_version'] = server_info.get('version')
                stats['server_uptime'] = server_info.get('uptime')
                
                # Add pool configuration
                stats['pool_config'] = self.pool_config.copy()
                
            except Exception as e:
                logger.warning(f"Could not get server info: {e}")
        
        return stats
    
    def close_all_connections(self):
        """Close all database connections - useful for cleanup"""
        try:
            if self._main_client:
                self._main_client.close()
                logger.info("Closed main MongoDB client")
                
            self._connection_stats['active_connections'] = 0
            
        except Exception as e:
            logger.error(f"Error closing connections: {e}")
    
    def __del__(self):
        """Cleanup when the pool manager is destroyed"""
        try:
            self.close_all_connections()
        except:
            pass

# Singleton instance
db_pool = DatabasePoolManager()

def get_database(db_name: str = None, client_id: str = "default"):
    """
    Convenience function to get database instance with pooling
    
    Args:
        db_name: Database name
        client_id: Client identifier for tracking
        
    Returns:
        Database instance with connection pooling
    """
    return db_pool.get_database(db_name, client_id)

def get_connection_stats():
    """Get current database connection statistics"""
    return db_pool.get_connection_stats()
