import os
import spacy
import logging
from pathlib import Path

def init_models():
    """Initialize and verify all required models."""
    logging.info("Initializing models...")
    
    # Create models directory
    models_dir = Path(__file__).parent / 'models'
    models_dir.mkdir(exist_ok=True)
    
    try:
        # Check if spaCy model exists
        if not spacy.util.is_package("en_core_web_lg"):
            logging.info("Downloading spaCy model...")
            spacy.cli.download("en_core_web_lg")
        
        # Load model to verify
        nlp = spacy.load("en_core_web_lg")
        logging.info("spaCy model loaded successfully")
        
        return True
    except Exception as e:
        logging.error(f"Error initializing models: {e}")
        return False

if __name__ == "__main__":
    init_models()