#!/usr/bin/env python3
"""
Contract Intelligence Agent (CIA)
Main application entry point

This script initializes and runs the CIA system that monitors Google Drive for legal documents,
processes them using AI, and integrates with ERPNext for contract management.
"""

import os
import time
import logging
import schedule
from dotenv import load_dotenv

from src.google_drive.monitor import GoogleDriveMonitor
from src.document_processing.processor import DocumentProcessor
from src.client_mapping.mapper import ClientMapper
from src.erpnext_integration.api import ERPNextAPI
from src.alert_system.alerts import AlertSystem
from src.utils.config import Config

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("contract_agent.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("contract_agent")

def process_documents():
    """Main processing function that runs at scheduled intervals"""
    try:
        logger.info("Starting document processing cycle")
        
        # Initialize components
        drive_monitor = GoogleDriveMonitor()
        document_processor = DocumentProcessor()
        client_mapper = ClientMapper()
        erpnext_api = ERPNextAPI()
        alert_system = AlertSystem()
        
        # Get new documents from Google Drive
        new_documents = drive_monitor.get_new_documents()
        
        if not new_documents:
            logger.info("No new documents found")
            return
        
        logger.info(f"Found {len(new_documents)} new documents")
        
        # Process each document
        for doc in new_documents:
            try:
                # Download document
                local_path = drive_monitor.download_document(doc)
                
                # Process document to extract information
                try:
                    extraction_result = document_processor.process_document(local_path)
                except Exception as e:
                    logger.error(f"Error processing document {doc.get('name', 'unknown')}: {str(e)}")
                    alert_system.send_error_alert(doc, str(e))
                    # Mark as processed to avoid endless retries
                    drive_monitor.mark_as_processed(doc)
                    continue
                
                # Map client to existing clients or create new
                client_mapping_result = client_mapper.map_client(extraction_result["client_info"])
                
                # Create/update records in ERPNext
                try:
                    erpnext_record = erpnext_api.update_records(
                        extraction_result,
                        client_mapping_result,
                        local_path
                    )
                    
                    # Generate necessary alerts
                    alert_system.generate_alerts(erpnext_record)
                except Exception as e:
                    logger.error(f"Error updating ERPNext records: {str(e)}")
                    alert_system.send_error_alert(doc, f"Document processed but ERPNext update failed: {str(e)}")
                
                # Mark document as processed
                drive_monitor.mark_as_processed(doc)
                
                logger.info(f"Successfully processed document: {doc['name']}")
                
            except Exception as e:
                logger.error(f"Error processing document {doc.get('name', 'unknown')}: {str(e)}")
                alert_system.send_error_alert(doc, str(e))
                continue
        
        # Generate expiration alerts for existing contracts
        try:
            alert_system.check_contract_expirations()
        except Exception as e:
            logger.error(f"Error checking contract expirations: {str(e)}")
        
    except Exception as e:
        logger.error(f"Error in processing cycle: {str(e)}")

def main():
    """Main entry point"""
    logger.info("Contract Intelligence Agent starting")
    
    # Load configuration
    config = Config()
    processing_interval = int(os.getenv("PROCESSING_INTERVAL", 300))  # 5 minutes by default
    
    # Run once at startup
    process_documents()
    
    # Schedule regular processing
    schedule.every(processing_interval).seconds.do(process_documents)
    
    # Run scheduled tasks
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main() 