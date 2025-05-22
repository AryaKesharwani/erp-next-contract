"""
Client mapping module for Contract Intelligence Agent

This module handles mapping of extracted client names to existing client records in ERPNext,
using fuzzy matching to handle variations in client names.
"""

import logging
import json
from datetime import datetime
import os

from fuzzywuzzy import fuzz, process

from src.utils.config import Config
from src.utils.helpers import save_json, ensure_directory_exists
from src.erpnext_integration.api import ERPNextAPI

# Logger setup
logger = logging.getLogger("contract_agent.client_mapping")

class ClientMapper:
    """Map extracted client names to existing client records"""
    
    def __init__(self):
        """Initialize the client mapper with configuration"""
        self.config = Config()
        self.erpnext_api = ERPNextAPI()
        
        # Directory to store mapping results
        self.results_dir = os.path.join(os.getcwd(), "client_mapping_results")
        ensure_directory_exists(self.results_dir)
        
        # Cache for client list to avoid frequent API calls
        self.client_cache = None
        self.client_cache_timestamp = None
        self.cache_ttl = 3600  # 1 hour in seconds
    
    def _get_clients(self):
        """Get the list of existing clients, with caching"""
        current_time = datetime.now().timestamp()
        
        # If cache exists and is recent, use it
        if (self.client_cache is not None and 
            self.client_cache_timestamp is not None and 
            current_time - self.client_cache_timestamp < self.cache_ttl):
            logger.debug("Using cached client list")
            return self.client_cache
        
        # Otherwise, fetch from ERPNext
        logger.info("Fetching client list from ERPNext")
        clients = self.erpnext_api.get_clients()
        
        # Update cache
        self.client_cache = clients
        self.client_cache_timestamp = current_time
        
        return clients
    
    def _normalize_name(self, name):
        """Normalize a client name for better matching"""
        if not name:
            return ""
        
        # Convert to lowercase
        name = name.lower()
        
        # Remove common legal entity designations
        replacements = [
            (" inc.", ""),
            (" incorporated", ""),
            (" corp.", ""),
            (" corporation", ""),
            (" llc", ""),
            (" l.l.c.", ""),
            (" ltd", ""),
            (" limited", ""),
            (" gmbh", ""),
            (" co.", ""),
            (" company", ""),
            (",", ""),
            (".", "")
        ]
        
        for old, new in replacements:
            name = name.replace(old, new)
        
        return name.strip()
    
    def _match_client(self, client_info):
        """
        Match an extracted client to existing clients using fuzzy matching
        
        Args:
            client_info (dict): Client information from document extraction
                {
                    "primary_name": "Client Name",
                    "alternative_names": ["Alt Name 1", "Alt Name 2"],
                    "confidence_score": 0.95
                }
                
        Returns:
            dict: Matching result
                {
                    "matched_client_id": "client_123" or None,
                    "matched_client_name": "Matched Client Name" or None,
                    "confidence_score": 0.92,
                    "match_reasons": ["Reason 1", "Reason 2"],
                    "alternative_matches": [
                        {
                            "client_id": "client_456",
                            "client_name": "Alt Match Name",
                            "confidence_score": 0.75
                        }
                    ]
                }
        """
        # Get existing clients
        existing_clients = self._get_clients()
        
        if not existing_clients:
            logger.warning("No existing clients found, suggesting to create new client")
            return {
                "matched_client_id": None,
                "matched_client_name": None,
                "confidence_score": 0.0,
                "recommendation": "CREATE_NEW_CLIENT",
                "suggested_client_name": client_info["primary_name"]
            }
        
        # Extract primary client name
        primary_name = client_info["primary_name"]
        alternative_names = client_info.get("alternative_names", [])
        
        # Create a list of all names to check (primary + alternatives)
        all_names_to_check = [primary_name] + alternative_names
        
        # Best match tracking
        best_match = None
        best_score = 0
        best_client_id = None
        best_client_name = None
        match_reasons = []
        alternative_matches = []
        
        # Normalize extracted name for matching
        normalized_primary = self._normalize_name(primary_name)
        
        # Go through each existing client
        for client in existing_clients:
            client_id = client["client_id"]
            client_name = client["client_name"]
            client_aliases = client.get("client_aliases", [])
            
            # Normalize client name for matching
            normalized_client_name = self._normalize_name(client_name)
            
            # Check for exact match first
            if normalized_primary == normalized_client_name:
                best_match = client
                best_score = 100
                best_client_id = client_id
                best_client_name = client_name
                match_reasons.append("Exact name match (normalized)")
                break
            
            # Check each name to match against client name and aliases
            for name_to_check in all_names_to_check:
                normalized_name = self._normalize_name(name_to_check)
                
                # Check against client name
                score = fuzz.ratio(normalized_name, normalized_client_name)
                
                if score > best_score:
                    best_score = score
                    best_match = client
                    best_client_id = client_id
                    best_client_name = client_name
                    match_reasons = [f"Fuzzy match with score {score} against client name"]
                
                # If the current best is already good enough, no need to check aliases
                if best_score > 95:
                    continue
                
                # Check against client aliases
                for alias in client_aliases:
                    normalized_alias = self._normalize_name(alias)
                    alias_score = fuzz.ratio(normalized_name, normalized_alias)
                    
                    if alias_score > best_score:
                        best_score = alias_score
                        best_match = client
                        best_client_id = client_id
                        best_client_name = client_name
                        match_reasons = [f"Fuzzy match with score {alias_score} against alias '{alias}'"]
            
            # If this client is a good match but not the best, add to alternatives
            if best_score < 95 and best_score > 60 and best_match is not client:
                alternative_matches.append({
                    "client_id": client_id,
                    "client_name": client_name,
                    "confidence_score": best_score / 100
                })
        
        # Normalize score to 0-1 range
        normalized_score = best_score / 100
        
        # Check if we found a match with sufficient confidence
        if normalized_score >= self.config.client_mapping_confidence_threshold:
            return {
                "matched_client_id": best_client_id,
                "matched_client_name": best_client_name,
                "confidence_score": normalized_score,
                "match_reasons": match_reasons,
                "alternative_matches": sorted(
                    alternative_matches, 
                    key=lambda x: x["confidence_score"], 
                    reverse=True
                )[:3]  # Return top 3 alternatives
            }
        else:
            # No match with sufficient confidence
            return {
                "matched_client_id": None,
                "matched_client_name": None,
                "confidence_score": normalized_score if best_match else 0.0,
                "recommendation": "CREATE_NEW_CLIENT",
                "suggested_client_name": primary_name,
                "alternative_matches": sorted(
                    alternative_matches, 
                    key=lambda x: x["confidence_score"], 
                    reverse=True
                )[:5]  # Return top 5 alternatives
            }
    
    def map_client(self, client_info):
        """
        Map an extracted client to existing clients
        
        Args:
            client_info (dict): Client information from document extraction
                
        Returns:
            dict: Mapping result
        """
        try:
            logger.info(f"Mapping client: {client_info['primary_name']}")
            
            # Perform client matching
            mapping_result = self._match_client(client_info)
            
            # Save mapping result
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            client_name = client_info["primary_name"].replace(" ", "_")[:30]
            result_path = os.path.join(
                self.results_dir, 
                f"{client_name}_{timestamp}_mapping.json"
            )
            save_json(mapping_result, result_path)
            
            # Log mapping result
            if mapping_result.get("matched_client_id"):
                logger.info(f"Mapped client '{client_info['primary_name']}' to '{mapping_result['matched_client_name']}' with confidence {mapping_result['confidence_score']}")
            else:
                logger.info(f"No mapping found for client '{client_info['primary_name']}', suggesting to create new client")
            
            return mapping_result
            
        except Exception as e:
            logger.error(f"Error mapping client {client_info.get('primary_name', 'unknown')}: {str(e)}")
            raise 