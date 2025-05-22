"""
Google Drive integration for Contract Intelligence Agent

This module handles the monitoring of Google Drive folders for new documents.
"""

import os
import pickle
import logging
from datetime import datetime
import mimetypes
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from src.utils.config import Config
from src.utils.helpers import ensure_directory_exists

# Logger setup
logger = logging.getLogger("contract_agent.google_drive")

# Define scopes
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

class GoogleDriveMonitor:
    """Monitor Google Drive for new documents"""
    
    def __init__(self):
        """Initialize the Google Drive monitor with configuration"""
        self.config = Config()
        self.credentials_file = self.config.credentials_file
        self.token_file = self.config.token_file
        self.folder_id = self.config.watch_folder_id
        
        # Directory to save downloaded files
        self.download_dir = os.path.join(os.getcwd(), "downloads")
        ensure_directory_exists(self.download_dir)
        
        # Directory to store processed document IDs
        self.data_dir = os.path.join(os.getcwd(), "data")
        ensure_directory_exists(self.data_dir)
        
        # File to store processed document IDs
        self.processed_ids_file = os.path.join(self.data_dir, "processed_documents.pickle")
        
        # Load previously processed document IDs
        self.processed_ids = self._load_processed_ids()
        
        # Initialize the Drive API client
        self.drive_service = self._get_drive_service()
    
    def _get_drive_service(self):
        """Initialize and authenticate the Google Drive API service"""
        creds = None
        
        # Check if token file exists
        if os.path.exists(self.token_file):
            with open(self.token_file, 'rb') as token:
                creds = pickle.load(token)
        
        # If credentials not valid, refresh or get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save the credentials for the next run
            with open(self.token_file, 'wb') as token:
                pickle.dump(creds, token)
        
        # Build the service
        return build('drive', 'v3', credentials=creds)
    
    def _load_processed_ids(self):
        """Load the list of already processed document IDs"""
        if os.path.exists(self.processed_ids_file):
            try:
                with open(self.processed_ids_file, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                logger.error(f"Error loading processed document IDs: {str(e)}")
        
        # Return empty set if file doesn't exist or error occurred
        return set()
    
    def _save_processed_ids(self):
        """Save the list of processed document IDs"""
        try:
            with open(self.processed_ids_file, 'wb') as f:
                pickle.dump(self.processed_ids, f)
        except Exception as e:
            logger.error(f"Error saving processed document IDs: {str(e)}")
    
    def get_new_documents(self):
        """
        Get a list of new documents in the monitored folder
        
        Returns:
            list: List of document metadata for new documents
        """
        try:
            # Query for files in the specified folder
            query = f"'{self.folder_id}' in parents and trashed = false"
            fields = "files(id, name, mimeType, createdTime, modifiedTime)"
            
            results = self.drive_service.files().list(
                q=query,
                spaces='drive',
                fields=fields
            ).execute()
            
            items = results.get('files', [])
            
            # Filter for new documents (not processed before)
            new_documents = [doc for doc in items if doc['id'] not in self.processed_ids]
            
            logger.info(f"Found {len(new_documents)} new documents out of {len(items)} total")
            
            return new_documents
            
        except HttpError as error:
            logger.error(f"Error accessing Google Drive API: {str(error)}")
            return []
    
    def download_document(self, document):
        """
        Download a document from Google Drive
        
        Args:
            document (dict): Document metadata from the API
            
        Returns:
            str: Path to the downloaded file
        """
        try:
            file_id = document['id']
            file_name = document['name']
            
            # Generate timestamp for unique filename
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            
            # Determine file extension
            mime_type = document.get('mimeType', '')
            extension = mimetypes.guess_extension(mime_type)
            
            if not extension and '.' in file_name:
                extension = file_name.split('.')[-1]
                if extension:
                    extension = f".{extension}"
            
            # Create download path
            download_path = os.path.join(
                self.download_dir, 
                f"{file_name.split('.')[0]}_{timestamp}{extension}"
            )
            
            # Download the file
            request = self.drive_service.files().get_media(fileId=file_id)
            
            with open(download_path, 'wb') as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
            
            logger.info(f"Downloaded {file_name} to {download_path}")
            
            return download_path
            
        except Exception as e:
            logger.error(f"Error downloading document {document.get('name', 'unknown')}: {str(e)}")
            raise
    
    def mark_as_processed(self, document):
        """
        Mark a document as processed
        
        Args:
            document (dict): Document metadata
        """
        try:
            # Add document ID to processed set
            self.processed_ids.add(document['id'])
            
            # Save updated processed IDs
            self._save_processed_ids()
            
            logger.debug(f"Marked document {document['name']} as processed")
            
        except Exception as e:
            logger.error(f"Error marking document as processed: {str(e)}")
    
    def get_document_content(self, document_id):
        """
        Get the content of a Google Doc directly (for non-downloadable formats)
        
        Args:
            document_id (str): Google Document ID
            
        Returns:
            str: Document content as text
        """
        try:
            # Get the document content
            doc = self.drive_service.files().export(
                fileId=document_id,
                mimeType='text/plain'
            ).execute()
            
            return doc.decode('utf-8')
            
        except Exception as e:
            logger.error(f"Error getting document content: {str(e)}")
            return None 