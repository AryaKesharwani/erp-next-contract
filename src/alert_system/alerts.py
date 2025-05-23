"""
Alert system for Contract Intelligence Agent

This module handles the generation of alerts for contract expirations,
processing errors, and other notifications.
"""

import os
import logging
import json
from datetime import datetime, timedelta

from src.utils.config import Config
from src.utils.helpers import ensure_directory_exists, save_json
from src.erpnext_integration.api import ERPNextAPI

# Logger setup
logger = logging.getLogger("contract_agent.alert_system")

class AlertSystem:
    """Generate alerts for contract management"""
    
    def __init__(self):
        """Initialize the alert system with configuration"""
        self.config = Config()
        self.erpnext_api = ERPNextAPI()
        
        # Alert periods (days before expiration)
        self.alert_periods = self.config.alert_periods
        
        # Directory to store alert logs
        self.log_dir = os.path.join(os.getcwd(), "alert_logs")
        ensure_directory_exists(self.log_dir)
    
    def _create_alert_record(self, alert_type, contract_id, client_id, message, priority="medium", days_until_expiration=None):
        """
        Create an alert record in ERPNext
        
        Args:
            alert_type (str): Type of alert (expiration, missing_info, processing_error)
            contract_id (str): Contract ID
            client_id (str): Client ID
            message (str): Alert message
            priority (str): Alert priority (high, medium, low)
            days_until_expiration (int, optional): Days until contract expiration
            
        Returns:
            dict: Created alert record or None if failed
        """
        try:
            # Create alert data
            alert_data = {
                "doctype": "Alert",
                "alert_type": alert_type,
                "contract_id": contract_id,
                "client_id": client_id,
                "alert_message": message,
                "days_until_expiration": days_until_expiration,
                "priority": priority,
                "status": "pending",
                "created_date": datetime.now().strftime("%Y-%m-%d")
            }
            
            # Create the alert in ERPNext
            response = self.erpnext_api._make_request("POST", "Alert", data=alert_data)
            
            logger.info(f"Created {priority} priority {alert_type} alert for contract {contract_id}")
            
            # Return the created alert
            return {
                "alert_id": response.get("data", {}).get("name"),
                "contract_id": contract_id,
                "client_id": client_id,
                "alert_type": alert_type,
                "status": "pending"
            }
            
        except Exception as e:
            logger.error(f"Error creating alert record in ERPNext: {str(e)}")
            return None
    
    def _log_alert(self, alert_type, data):
        """Log alert information to file"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        log_path = os.path.join(
            self.log_dir, 
            f"{alert_type}_{timestamp}.json"
        )
        save_json(data, log_path)
        logger.info(f"Alert logged to {log_path}")
    
    def generate_expiration_alert(self, contract, days_until_expiration):
        """
        Generate an alert for an expiring contract
        
        Args:
            contract (dict): Contract data
            days_until_expiration (int): Days until expiration
        """
        contract_id = contract["contract_id"]
        client_id = contract["client_id"]
        contract_name = contract["contract_name"]
        contract_type = contract["contract_type"]
        expiration_date = contract["expiration_date"]
        
        # Determine priority based on days until expiration
        if days_until_expiration <= 30:
            priority = "high"
        elif days_until_expiration <= 60:
            priority = "medium"
        else:
            priority = "low"
        
        # Create alert message
        message = f"Contract {contract_name} ({contract_type}) will expire in {days_until_expiration} days on {expiration_date}."
        
        # Create alert record
        alert = self._create_alert_record(
            "expiration", 
            contract_id, 
            client_id, 
            message, 
            priority, 
            days_until_expiration
        )
        
        if not alert:
            return
        
        # Log the alert
        self._log_alert("expiration", {
            "contract_id": contract_id,
            "client_id": client_id,
            "contract_name": contract_name,
            "days_until_expiration": days_until_expiration,
            "message": message,
            "priority": priority,
            "timestamp": datetime.now().isoformat()
        })
        
        logger.info(f"Generated expiration alert for contract {contract_name} - {days_until_expiration} days remaining")
    
    def send_error_alert(self, document, error_message):
        """
        Log an alert for a processing error
        
        Args:
            document (dict): Document metadata
            error_message (str): Error message
        """
        document_name = document.get("name", "Unknown document")
        
        # Create alert message
        message = f"Error processing document {document_name}: {error_message}"
        
        # Log the alert
        self._log_alert("processing_error", {
            "document_name": document_name,
            "error_message": error_message,
            "timestamp": datetime.now().isoformat()
        })
        
        logger.info(f"Logged processing error for document {document_name}")
    
    def generate_alerts(self, erpnext_record):
        """
        Generate appropriate alerts for a newly processed document
        
        Args:
            erpnext_record (dict): ERPNext record data
        """
        try:
            # If document has an expiration date, check if it's within the alert periods
            if "expiration_date" in erpnext_record and erpnext_record["expiration_date"]:
                # Prepare a contract-like object for the expiration alert
                contract = {
                    "contract_id": erpnext_record["contract_id"],
                    "client_id": erpnext_record["client_id"],
                    "contract_name": f"Contract #{erpnext_record['contract_id']}",
                    "contract_type": erpnext_record["document_type"],
                    "expiration_date": erpnext_record["expiration_date"]
                }
                
                # Parse the expiration date
                expiration_date = datetime.strptime(erpnext_record["expiration_date"], "%Y-%m-%d").date()
                today = datetime.now().date()
                days_until_expiration = (expiration_date - today).days
                
                # Generate expiration alerts if needed
                for alert_period in self.alert_periods:
                    if days_until_expiration <= alert_period:
                        self.generate_expiration_alert(contract, days_until_expiration)
                        break  # Only generate one alert for the closest period
            
        except Exception as e:
            logger.error(f"Error generating alerts: {str(e)}")
    
    def check_contract_expirations(self):
        """Check for contracts that will expire soon and generate alerts"""
        try:
            # Check each alert period
            for days_ahead in self.alert_periods:
                # Get contracts expiring exactly at this period
                # This ensures we only generate alerts once per period
                today = datetime.now().date()
                target_date = today + timedelta(days=days_ahead)
                
                # Get contracts expiring on the target date
                expiring_contracts = self.erpnext_api.get_expiring_contracts(days_ahead)
                
                # Filter to only those expiring exactly on the target date
                for contract in expiring_contracts:
                    if contract.get("days_until_expiration") == days_ahead:
                        self.generate_expiration_alert(contract, days_ahead)
            
        except Exception as e:
            logger.error(f"Error checking contract expirations: {str(e)}")
            # Log a system error alert
            self._log_alert("system_error", {
                "error_message": f"Error checking contract expirations: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }) 