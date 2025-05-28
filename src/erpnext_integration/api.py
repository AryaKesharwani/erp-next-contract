"""
ERPNext API integration for Contract Intelligence Agent

This module handles interactions with the ERPNext API to create and update
client records, contract records, and alerts.
"""

import os
import logging
import requests
import json
import base64
from datetime import datetime, timedelta
import urllib.parse
from colorama import Fore, Style, init

from src.utils.config import Config
from src.utils.helpers import parse_date, save_json, ensure_directory_exists

# Initialize colorama
init()

# Logger setup with colors
class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for different log levels"""
    
    COLORS = {
        'DEBUG': Fore.BLUE,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Style.BRIGHT
    }
    
    def format(self, record):
        if not record.exc_info:
            level = record.levelname
            if level in self.COLORS:
                record.msg = f"{self.COLORS[level]}{record.msg}{Style.RESET_ALL}"
        return super().format(record)

# Configure logger with colored output
logger = logging.getLogger("contract_agent.erpnext_integration")
handler = logging.StreamHandler()
handler.setFormatter(ColoredFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

class ERPNextAPI:
    """Interface for the ERPNext API"""
    
    def __init__(self):
        """Initialize the ERPNext API client with configuration"""
        self.config = Config()
        self.base_url = self.config.erpnext_url
        self.api_key = self.config.erpnext_api_key
        self.api_secret = self.config.erpnext_api_secret
        
        # Directory to store API transaction logs
        self.log_dir = os.path.join(os.getcwd(), "erpnext_logs")
        ensure_directory_exists(self.log_dir)
    
    def _get_auth_headers(self):
        """Get authentication headers for ERPNext API requests"""
        auth_string = f"{self.api_key}:{self.api_secret}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        return {
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    def _make_request(self, method, endpoint, data=None, params=None):
        """
        Make an API request to ERPNext
        
        Args:
            method (str): HTTP method (GET, POST, PUT, DELETE)
            endpoint (str): API endpoint to call
            data (dict, optional): Request body data
            params (dict, optional): Query parameters
            
        Returns:
            dict: Response data
        """
        url = f"{self.base_url}/api/resource/{endpoint}"
        headers = self._get_auth_headers()
        
        try:
            # Log the request
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            log_data = {
                "timestamp": timestamp,
                "method": method,
                "url": url,
                "headers": {k: v for k, v in headers.items() if k != "Authorization"},
                "params": params,
                "data": data
            }
            
            # Make the request
            if method == "GET":
                response = requests.get(url, headers=headers, params=params)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data, params=params)
            elif method == "PUT":
                response = requests.put(url, headers=headers, json=data, params=params)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers, params=params)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Log the response
            log_data["status_code"] = response.status_code
            log_data["response"] = response.json() if response.text else None
            
            log_path = os.path.join(
                self.log_dir, 
                f"{endpoint.replace('/', '_')}_{method}_{timestamp}.json"
            )
            save_json(log_data, log_path)
            
            # Check for errors
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error making {method} request to {url}: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error making {method} request to {url}: {str(e)}")
            raise
    
    def get_clients(self):
        """
        Get a list of all clients from ERPNext
        
        Returns:
            list: List of client records
        """
        try:
            # Get client list from ERPNext
            params = {
                "fields": json.dumps([
                    "name", "client_id", "client_name", "client_aliases", 
                    "industry", "status", "created_date", "modified_date"
                ])
            }
            response = self._make_request("GET", "Client", params=params)
            
            clients = []
            for client_data in response.get("data", []):
                client = {
                    "client_id": client_data.get("client_id") or client_data.get("name"),
                    "client_name": client_data.get("client_name"),
                    "client_aliases": client_data.get("client_aliases", "").split(",") if client_data.get("client_aliases") else [],
                    "industry": client_data.get("industry"),
                    "status": client_data.get("status"),
                    "created_date": client_data.get("created_date"),
                    "modified_date": client_data.get("modified_date")
                }
                clients.append(client)
            
            logger.info(f"Retrieved {len(clients)} clients from ERPNext")
            return clients
            
        except Exception as e:
            logger.error(f"Error getting clients from ERPNext: {str(e)}")
            return []
    
    def create_client(self, client_info):
        """
        Create a new client record in ERPNext
        
        Args:
            client_info (dict): Client information
                {
                    "primary_name": "Client Name",
                    "alternative_names": ["Alt Name 1", "Alt Name 2"],
                    "confidence_score": 0.95
                }
                
        Returns:
            dict: Created client record
        """
        try:
            # Create data for the client record
            client_data = {
                "doctype": "Client",
                "client_id": f"CLI-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "client_name": client_info["primary_name"],
                "client_aliases": ",".join(client_info.get("alternative_names", [])),
                "status": "Active",
                "created_date": datetime.now().strftime("%Y-%m-%d")
            }
            
            # Create the client in ERPNext
            response = self._make_request("POST", "Client", data=client_data)
            
            logger.info(f"Created new client: {client_info['primary_name']}")
            
            # Return the created client
            created_client = {
                "client_id": response.get("data", {}).get("name"),
                "client_name": client_info["primary_name"],
                "client_aliases": client_info.get("alternative_names", []),
                "status": "Active",
                "created_date": datetime.now().strftime("%Y-%m-%d")
            }
            
            return created_client
            
        except Exception as e:
            logger.error(f"Error creating client in ERPNext: {str(e)}")
            raise
    
    def create_contract(self, extraction_result, client_id, document_path):
        """
        Create a new contract record in ERPNext
        
        Args:
            extraction_result (dict): Extracted contract information
            client_id (str): Client ID to associate with the contract
            document_path (str): Path to the document file
            
        Returns:
            dict: Created contract record
        """
        try:
            # Extract relevant data from extraction result
            document_type = extraction_result["document_type"]
            contract_details = extraction_result["contract_details"]
            type_specific_details = extraction_result.get("type_specific_details", {})
            
            # Prepare contract data
            contract_data = {
                "doctype": "ContractCustom",
                "contract_id": f"CON-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "client_id": client_id,
                "contract_type": document_type,
                "contract_name": os.path.basename(document_path),
                "effective_date": contract_details.get("effective_date"),
                "expiration_date": contract_details.get("expiration_date"),
                "auto_renewal": "Yes" if contract_details.get("auto_renewal", {}).get("enabled") else "No",
                "renewal_terms": contract_details.get("auto_renewal", {}).get("terms"),
                "status": "Active",
                "extraction_confidence": extraction_result.get("extraction_confidence", {}).get("overall", 0),
                "extraction_log": json.dumps(extraction_result),
                "created_date": datetime.now().strftime("%Y-%m-%d"),
                "processed_date": datetime.now().strftime("%Y-%m-%d")
            }
            
            # Add type-specific fields
            if document_type == "SoW":
                # Map SoW type values to match doctype options
                sow_type_mapping = {
                    "Time & Material": "T&M",
                    "Time and Material": "T&M", 
                    "T&M": "T&M",
                    "Retainer": "Retainer",
                    "Fixed Cost": "Fixed Cost",
                    "Fixed Price": "Fixed Cost",
                    "Fixed": "Fixed Cost"
                }
                
                raw_sow_type = type_specific_details.get("sow_type", "")
                mapped_sow_type = sow_type_mapping.get(raw_sow_type, "T&M")  # Default to T&M
                
                contract_data.update({
                    "contract_value": type_specific_details.get("total_contract_value"),
                    "sow_type": mapped_sow_type,
                    "payment_terms": type_specific_details.get("payment_schedule"),
                    "deliverables": json.dumps(type_specific_details.get("deliverables", [])),
                    "parent_contract_id": type_specific_details.get("parent_msa_reference")
                })
            
            # TODO: Upload the document file to ERPNext
            # This typically requires a multipart form upload which depends on ERPNext's API
            
            # Create the contract in ERPNext
            response = self._make_request("POST", "ContractCustom", data=contract_data)
            
            logger.info(f"Created new contract: {contract_data['contract_name']} for client {client_id}")
            
            # Return the created contract
            created_contract = {
                "contract_id": response.get("data", {}).get("name"),
                "client_id": client_id,
                "contract_type": document_type,
                "contract_name": contract_data["contract_name"],
                "effective_date": contract_data["effective_date"],
                "expiration_date": contract_data["expiration_date"],
                "status": "Active"
            }
            
            return created_contract
            
        except Exception as e:
            logger.error(f"Error creating contract in ERPNext: {str(e)}")
            raise
    
    def update_records(self, extraction_result, client_mapping_result, document_path):
        """
        Update ERPNext records based on document extraction and client mapping
        
        Args:
            extraction_result (dict): Extracted contract information
            client_mapping_result (dict): Client mapping result
            document_path (str): Path to the document file
            
        Returns:
            dict: Created/updated records
        """
        try:
            # Get or create client
            client_id = client_mapping_result.get("matched_client_id")
            
            if client_id is None:
                # Create new client
                client_info = extraction_result["client_info"]
                client = self.create_client(client_info)
                client_id = client["client_id"]
                logger.info(f"Created new client: {client['client_name']} (ID: {client_id})")
            else:
                logger.info(f"Using existing client: {client_mapping_result['matched_client_name']} (ID: {client_id})")
            
            # Create contract
            contract = self.create_contract(extraction_result, client_id, document_path)
            
            return {
                "client_id": client_id,
                "contract_id": contract["contract_id"],
                "document_type": extraction_result["document_type"],
                "expiration_date": contract["expiration_date"]
            }
            
        except Exception as e:
            logger.error(f"Error updating records in ERPNext: {str(e)}")
            raise
    
    def get_expiring_contracts(self, days_ahead=90):
        """
        Get contracts that will expire within the specified number of days
        
        Args:
            days_ahead (int): Number of days ahead to check for expirations
            
        Returns:
            list: List of expiring contracts
        """
        try:
            # Calculate the date range
            today = datetime.now().date()
            future_date = today + timedelta(days=days_ahead)
            
            # Query contracts that will expire in the date range
            params = {
                "filters": json.dumps([
                    ["expiration_date", ">=", today.strftime("%Y-%m-%d")],
                    ["expiration_date", "<=", future_date.strftime("%Y-%m-%d")],
                    ["status", "=", "Active"]
                ]),
                "fields": json.dumps([
                    "name", "contract_id", "client_id", "contract_type", 
                    "contract_name", "effective_date", "expiration_date",
                    "auto_renewal", "status"
                ])
            }
            
            response = self._make_request("GET", "ContractCustom", params=params)
            
            contracts = []
            for contract_data in response.get("data", []):
                # Calculate days until expiration
                expiration_date = parse_date(contract_data.get("expiration_date"))
                days_until_expiration = (expiration_date - today).days if expiration_date else None
                
                contract = {
                    "contract_id": contract_data.get("contract_id") or contract_data.get("name"),
                    "client_id": contract_data.get("client_id"),
                    "contract_type": contract_data.get("contract_type"),
                    "contract_name": contract_data.get("contract_name"),
                    "expiration_date": contract_data.get("expiration_date"),
                    "days_until_expiration": days_until_expiration,
                    "auto_renewal": contract_data.get("auto_renewal")
                }
                contracts.append(contract)
            
            logger.info(f"Found {len(contracts)} contracts expiring within {days_ahead} days")
            return contracts
            
        except Exception as e:
            logger.error(f"Error getting expiring contracts from ERPNext: {str(e)}")
            return [] 