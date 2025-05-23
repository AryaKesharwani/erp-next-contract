#!/usr/bin/env python3
"""
Script to view all clients, contracts, and alerts from ERPNext
"""

import sys
import os
import json
from datetime import datetime, timedelta

# Add the src directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from erpnext_integration.api import ERPNextAPI

def print_separator(title):
    """Print a section separator"""
    print("\n" + "="*50)
    print(f" {title}")
    print("="*50)

def print_clients(api):
    """Print all clients"""
    print_separator("CLIENTS")
    
    try:
        clients = api.get_clients()
        
        if not clients:
            print("No clients found.")
            return
        
        print(f"Found {len(clients)} client(s):\n")
        
        for i, client in enumerate(clients, 1):
            print(f"{i}. Client ID: {client.get('client_id', 'N/A')}")
            print(f"   Name: {client.get('client_name', 'N/A')}")
            print(f"   Aliases: {', '.join(client.get('client_aliases', [])) if client.get('client_aliases') else 'None'}")
            print(f"   Industry: {client.get('industry', 'N/A')}")
            print(f"   Status: {client.get('status', 'N/A')}")
            print(f"   Created: {client.get('created_date', 'N/A')}")
            print()
            
    except Exception as e:
        print(f"Error retrieving clients: {e}")

def print_contracts(api):
    """Print all contracts"""
    print_separator("CONTRACTS")
    
    try:
        # Get all contracts by using a very large date range
        future_date = datetime.now() + timedelta(days=3650)  # 10 years ahead
        contracts = api.get_expiring_contracts(days_ahead=3650)
        
        if not contracts:
            print("No contracts found.")
            return
        
        print(f"Found {len(contracts)} contract(s):\n")
        
        for i, contract in enumerate(contracts, 1):
            print(f"{i}. Contract ID: {contract.get('contract_id', 'N/A')}")
            print(f"   Client ID: {contract.get('client_id', 'N/A')}")
            print(f"   Type: {contract.get('contract_type', 'N/A')}")
            print(f"   Name: {contract.get('contract_name', 'N/A')}")
            print(f"   Effective Date: {contract.get('effective_date', 'N/A')}")
            print(f"   Expiration Date: {contract.get('expiration_date', 'N/A')}")
            print(f"   Days Until Expiration: {contract.get('days_until_expiration', 'N/A')}")
            print(f"   Auto Renewal: {contract.get('auto_renewal', 'N/A')}")
            print()
            
    except Exception as e:
        print(f"Error retrieving contracts: {e}")

def print_alerts(api):
    """Print alerts for expiring contracts"""
    print_separator("ALERTS - CONTRACTS EXPIRING IN 90 DAYS")
    
    try:
        expiring_contracts = api.get_expiring_contracts(days_ahead=90)
        
        if not expiring_contracts:
            print("No contracts expiring in the next 90 days.")
            return
        
        print(f"Found {len(expiring_contracts)} contract(s) expiring soon:\n")
        
        # Sort by days until expiration
        expiring_contracts.sort(key=lambda x: x.get('days_until_expiration', 999))
        
        for i, contract in enumerate(expiring_contracts, 1):
            days_left = contract.get('days_until_expiration', 'N/A')
            urgency = "🔴 URGENT" if isinstance(days_left, int) and days_left <= 30 else "🟡 WARNING"
            
            print(f"{i}. {urgency}")
            print(f"   Contract ID: {contract.get('contract_id', 'N/A')}")
            print(f"   Client ID: {contract.get('client_id', 'N/A')}")
            print(f"   Type: {contract.get('contract_type', 'N/A')}")
            print(f"   Expiration Date: {contract.get('expiration_date', 'N/A')}")
            print(f"   Days Left: {days_left}")
            print(f"   Auto Renewal: {'Yes' if contract.get('auto_renewal') else 'No'}")
            print()
            
    except Exception as e:
        print(f"Error retrieving expiring contracts: {e}")

def main():
    """Main function"""
    print("ERPNext Data Viewer")
    print("==================")
    
    # Initialize API
    try:
        api = ERPNextAPI()
        print(f"Connected to ERPNext: {api.base_url}")
    except Exception as e:
        print(f"Error connecting to ERPNext: {e}")
        return
    
    # Print all data
    print_clients(api)
    print_contracts(api)
    print_alerts(api)
    
    print_separator("SUMMARY")
    print("Data retrieval completed!")
    print("\nTip: If you see errors, check the erpnext_logs/ folder for detailed API logs.")

if __name__ == "__main__":
    main() 