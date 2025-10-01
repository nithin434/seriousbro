import chromadb
from chromadb.config import Settings
from pymongo import MongoClient, ASCENDING
from dotenv import load_dotenv
import os
from datetime import datetime
import logging
from pathlib import Path
def init_databases():
    """Initialize ChromaDB and MongoDB databases."""
    try:
        # Initialize MongoDB
        mongo_client = MongoClient("mongodb://localhost:27017/")
        db = mongo_client.resumeDB

        # Drop existing unique index if it exists
        try:
            db.resumes.drop_index("personal_info.email_1")
        except:
            pass

        # Create new compound index on both email and resume_id
        db.resumes.create_index(
            [
                ("personal_info.email", 1),
                ("_id", 1)
            ],
            unique=True,
            sparse=True  # Allows multiple documents with missing email
        )

        # Create profile_roasts collection with indexes
        try:
            # Create unique index on profile_url
            db.profile_roasts.create_index("profile_url", unique=True)
            
            # Create index on last_updated for TTL (24 hours = 86400 seconds)
            db.profile_roasts.create_index("last_updated", expireAfterSeconds=86400)
            
            # Create index on platform for efficient queries
            db.profile_roasts.create_index("platform")
            
            print("✅ Profile roasts collection indexes created")
        except Exception as e:
            print(f"⚠️ Profile roasts indexes already exist or error: {e}")

        # Other indexes
        db.resumes.create_index([("created_at", -1)])
        db.job_matches.create_index([("resume_id", 1), ("job_id", 1)])

        # Initialize ChromaDB
        # chroma_client = chromadb.PersistentClient(path="./data/chromadb")
        
        collections = ["resume_embeddings", "job_embeddings"]
        for name in collections:
            try:
                chroma_client.get_collection(name)
            except:
                chroma_client.create_collection(
                    name=name,
                    metadata={"hnsw:space": "cosine"}
                )

        return True

    except Exception as e:
        print(f"Database initialization error: {str(e)}")
        return False

if __name__ == "__main__":
    load_dotenv()
    init_databases()