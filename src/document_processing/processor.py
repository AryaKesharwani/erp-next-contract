"""
Document processing module for Contract Intelligence Agent

This module handles the extraction of information from legal documents
using the Google Gemini API and specialized prompts.
"""

import os
import logging
import json
from datetime import datetime

import PyPDF2
import docx
import google.generativeai as genai

from src.utils.config import Config
from src.utils.helpers import get_file_extension, save_json, ensure_directory_exists

# Logger setup
logger = logging.getLogger("contract_agent.document_processing")

class DocumentProcessor:
    """Process documents and extract contract information using LLMs"""
    
    def __init__(self):
        """Initialize the document processor with configuration"""
        self.config = Config()
        genai.configure(api_key=self.config.google_ai_api_key)
        
        # Directory to store extraction results
        self.results_dir = os.path.join(os.getcwd(), "extraction_results")
        ensure_directory_exists(self.results_dir)
        
        # Load prompts
        self.master_prompt = self._load_prompt("master_prompt")
        
        # Configure Gemini model
        self.generation_config = {
            "temperature": 0.1,  # Low temperature for factual extraction
            "max_output_tokens": 2048,
            "top_p": 0.95,
            "top_k": 40,
        }
        
        # List available models to select the correct one
        try:
            self.models = genai.list_models()
            self.model_name = None
            # for model in self.models:
            #     if "gemini" in model.name.lower() and model.supported_generation_methods.count("generateContent") > 0:
            #         self.model_name = model.name
            #         logger.info(f"Selected Gemini model: {self.model_name}")
            #         break
            
            if not self.model_name:
                logger.warning("No suitable Gemini model found. Using default gemini model.")
                self.model_name = "gemini-2.0-flash"
        except Exception as e:
            logger.warning(f"Error listing Gemini models: {str(e)}. Using default model.")
            self.model_name = "gemini-2.0-flash"
    
    def _load_prompt(self, prompt_name):
        """Load a prompt template from the config directory"""
        # The prompt is hardcoded here but could be loaded from a file
        if prompt_name == "master_prompt":
            return """
You are an AI assistant specialized in analyzing legal contracts. You will be provided with a contract document and need to extract specific information.

DOCUMENT TYPE IDENTIFICATION:
First, identify if this is an NDA, MSA (Master Service Agreement), or SoW (Statement of Work).

CLIENT IDENTIFICATION:
Extract the client/customer name. Look for:
- Party names in the preamble
- "Company", "Customer", "Client" references
- Signature blocks
- Any entity that is NOT the service provider

For client mapping, also identify:
- Alternative names or DBA (Doing Business As)
- Parent company references
- Subsidiary mentions

CONTRACT INFORMATION EXTRACTION:

For ALL document types, extract:
1. Effective Date/Start Date
2. Expiration Date/End Date
3. Auto-renewal clauses (Yes/No and terms)
4. Key parties involved
5. Governing law/jurisdiction

For NDAs specifically, also extract:
- Type of NDA (mutual/unilateral)
- Confidentiality period
- Key restrictions or exceptions
- Permitted disclosures

For MSAs specifically, also extract:
- Payment terms
- Termination clauses
- Liability limitations
- Intellectual property ownership
- Service level agreements (if any)

For SoWs specifically, also extract:
- SoW Type (Time & Material, Retainer, or Fixed Cost)
- Total contract value
- Payment schedule
- Deliverables list
- Project milestones
- Reference to parent MSA (if mentioned)
- Resource allocation

OUTPUT FORMAT:
Return the extracted information in the following JSON structure:

{
  "document_type": "NDA|MSA|SoW",
  "client_info": {
    "primary_name": "extracted client name",
    "alternative_names": ["list of any alternative names found"],
    "confidence_score": 0.95
  },
  "contract_details": {
    "effective_date": "YYYY-MM-DD",
    "expiration_date": "YYYY-MM-DD",
    "auto_renewal": {
      "enabled": true/false,
      "terms": "renewal terms if applicable"
    },
    "governing_law": "jurisdiction"
  },
  "type_specific_details": {
    // Fields specific to document type
  },
  "extraction_confidence": {
    "overall": 0.85,
    "field_level": {
      "client_name": 0.95,
      "dates": 0.90,
      // ... other fields
    }
  },
  "extraction_notes": [
    "Any ambiguities or issues encountered"
  ]
}

CONFIDENCE SCORING:
- High confidence (0.9+): Clear, unambiguous extraction
- Medium confidence (0.7-0.89): Some interpretation required
- Low confidence (<0.7): Multiple interpretations possible or information unclear

Flag any fields with confidence below 0.8 for human review.
"""
    
    def _extract_text_from_pdf(self, file_path):
        """Extract text content from a PDF file"""
        try:
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    text += page.extract_text() + "\n"
            return text
        except Exception as e:
            logger.error(f"Error extracting text from PDF {file_path}: {str(e)}")
            raise
    
    def _extract_text_from_docx(self, file_path):
        """Extract text content from a DOCX file"""
        try:
            doc = docx.Document(file_path)
            text = ""
            for para in doc.paragraphs:
                text += para.text + "\n"
            return text
        except Exception as e:
            logger.error(f"Error extracting text from DOCX {file_path}: {str(e)}")
            raise
    
    def _extract_text(self, file_path):
        """Extract text content from a document based on file type"""
        extension = get_file_extension(file_path)
        
        if extension == '.pdf':
            return self._extract_text_from_pdf(file_path)
        elif extension == '.docx':
            return self._extract_text_from_docx(file_path)
        else:
            raise ValueError(f"Unsupported file format: {extension}")
    
    def _process_with_llm(self, document_text):
        """Process document text with Google Gemini API"""
        try:
            # Check if text is too large and truncate if necessary
            # Gemini has a context limit, so we may need to truncate
            max_tokens = 30000  # Approximate token limit for Gemini
            if len(document_text.split()) > max_tokens:
                logger.warning(f"Document text is too large, truncating to {max_tokens} tokens")
                document_text = " ".join(document_text.split()[:max_tokens])
            
            # Create the prompt with the document text
            prompt = self.master_prompt + "\n\nDOCUMENT TEXT:\n" + document_text
            
            # Initialize Gemini model
            model = genai.GenerativeModel(
                model_name=self.model_name,
                generation_config=self.generation_config
            )
            
            # Call the Gemini API
            response = model.generate_content(prompt)
            
            # Extract the response text
            result_text = response.text
            
            # Try to parse the JSON from the response
            # It might be wrapped in markdown code blocks
            if "```json" in result_text and "```" in result_text:
                json_str = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                json_str = result_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = result_text
            
            # Parse the JSON
            try:
                result = json.loads(json_str)
                return result
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON from LLM response: {result_text}")
                raise
                
        except Exception as e:
            logger.error(f"Error processing document with LLM: {str(e)}")
            raise
    
    def process_document(self, file_path):
        """
        Process a document to extract contract information
        
        Args:
            file_path (str): Path to the document file
            
        Returns:
            dict: Extracted contract information
        """
        try:
            logger.info(f"Processing document: {file_path}")
            
            # Extract text from document
            document_text = self._extract_text(file_path)
            
            # Process text with LLM
            extraction_result = self._process_with_llm(document_text)
            
            # Save extraction result
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            filename = os.path.basename(file_path)
            result_path = os.path.join(
                self.results_dir, 
                f"{filename}_{timestamp}_extraction.json"
            )
            save_json(extraction_result, result_path)
            
            # Check confidence levels and log warnings for low confidence
            overall_confidence = extraction_result.get("extraction_confidence", {}).get("overall", 0)
            if overall_confidence < self.config.extraction_confidence_threshold:
                logger.warning(f"Low confidence extraction ({overall_confidence}) for {filename}")
            
            return extraction_result
            
        except Exception as e:
            logger.error(f"Error processing document {file_path}: {str(e)}")
            raise 