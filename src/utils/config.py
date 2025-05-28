"""
Configuration management for Contract Intelligence Agent

This module handles loading and validating configuration from environment variables.
"""

import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Logger setup
logger = logging.getLogger("contract_agent.utils")

class Config:
    """Configuration class that loads and validates config from environment variables"""
    
    def __init__(self):
        """Initialize configuration by loading from environment variables"""
        # Google Drive configuration
        self.credentials_file = os.getenv("GOOGLE_DRIVE_CREDENTIALS_FILE", "credentials.json")
        self.token_file = os.getenv("GOOGLE_DRIVE_TOKEN_FILE", "token.json")
        self.watch_folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
        
        # ERPNext configuration
        self.erpnext_url = os.getenv("ERPNEXT_URL")
        self.erpnext_api_key = os.getenv("ERPNEXT_API_KEY")
        self.erpnext_api_secret = os.getenv("ERPNEXT_API_SECRET")
        
        # Google Gemini configuration
        self.google_ai_api_key = os.getenv("GOOGLE_AI_API_KEY")
        
        # Client mapping configuration
        self.fuzzy_match_threshold = float(os.getenv("FUZZY_MATCH_THRESHOLD", "80.0"))
        self.client_mapping_confidence_threshold = float(os.getenv("CLIENT_MAPPING_CONFIDENCE_THRESHOLD", "0.75"))
        
        # Document processing configuration
        self.extraction_confidence_threshold = float(os.getenv("EXTRACTION_CONFIDENCE_THRESHOLD", "0.7"))
        
        # Alert configuration
        self.alert_periods = [int(days) for days in os.getenv("ALERT_PERIODS", "90,60,30,14,7").split(",")]
        
        # Validate configuration
        self._validate_config()
    
    def _validate_config(self):
        """Validate that all required configuration is present"""
        required_fields = [
            "watch_folder_id",
            "erpnext_url",
            "erpnext_api_key",
            "erpnext_api_secret",
            "google_ai_api_key"
        ]
        
        for field in required_fields:
            if not getattr(self, field):
                logger.warning(f"Missing required configuration: {field}")
        
        # Check credentials file exists
        if not os.path.exists(self.credentials_file):
            logger.warning(f"Google Drive credentials file not found: {self.credentials_file}")
            
        # Log non-critical configs
        if self.fuzzy_match_threshold < 50.0:
            logger.warning(f"Fuzzy match threshold {self.fuzzy_match_threshold} is low, may cause false matches") 