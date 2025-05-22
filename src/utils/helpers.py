"""
Helper utilities for the Contract Intelligence Agent
"""

import os
import json
import logging
from datetime import datetime, date
import re

logger = logging.getLogger("contract_agent.utils")

def ensure_directory_exists(directory_path):
    """Ensure that a directory exists, creating it if necessary"""
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)
        logger.info(f"Created directory: {directory_path}")

def save_json(data, filepath):
    """Save data as JSON to a file"""
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=json_serializer)
        return True
    except Exception as e:
        logger.error(f"Error saving JSON to {filepath}: {str(e)}")
        return False

def load_json(filepath):
    """Load JSON data from a file"""
    try:
        if not os.path.exists(filepath):
            logger.warning(f"JSON file not found: {filepath}")
            return None
        
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading JSON from {filepath}: {str(e)}")
        return None

def json_serializer(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

def parse_date(date_string):
    """
    Parse a date string into a datetime object.
    Handles various date formats.
    """
    if not date_string:
        return None
    
    # Remove any non-alphanumeric characters except for / and -
    date_string = re.sub(r'[^\w\s\-\/]', '', date_string.strip())
    
    # Try various date formats
    formats = [
        '%Y-%m-%d',      # 2023-01-15
        '%d-%m-%Y',      # 15-01-2023
        '%m-%d-%Y',      # 01-15-2023
        '%Y/%m/%d',      # 2023/01/15
        '%d/%m/%Y',      # 15/01/2023
        '%m/%d/%Y',      # 01/15/2023
        '%B %d, %Y',     # January 15, 2023
        '%d %B %Y',      # 15 January 2023
        '%b %d, %Y',     # Jan 15, 2023
        '%d %b %Y',      # 15 Jan 2023
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_string, fmt).date()
        except ValueError:
            continue
    
    logger.warning(f"Could not parse date: {date_string}")
    return None

def calculate_days_between(start_date, end_date):
    """Calculate days between two dates"""
    if not start_date or not end_date:
        return None
    
    if isinstance(start_date, str):
        start_date = parse_date(start_date)
    
    if isinstance(end_date, str):
        end_date = parse_date(end_date)
    
    if not start_date or not end_date:
        return None
    
    return (end_date - start_date).days

def get_file_extension(file_path):
    """Get the file extension from a path"""
    _, ext = os.path.splitext(file_path)
    return ext.lower() 