"""
Prompt Optimization and A/B Testing Module for StopSale Automation System

This module implements different prompt versions and an A/B testing mechanism
to evaluate and optimize AI analysis performance.
"""

import json
import logging
import random
import statistics
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# Set up logging
logger = logging.getLogger(__name__)

class PromptVersion:
    """Class representing a prompt version with performance metrics"""
    
    def __init__(self, name: str, content: str, description: str = ""):
        """
        Initialize a prompt version
        
        Args:
            name: Unique identifier for the prompt
            content: The actual prompt text
            description: Description of what makes this prompt version unique
        """
        self.name = name
        self.content = content
        self.description = description
        self.calls = 0
        self.successful_calls = 0
        self.extraction_counts = []
        self.confidence_scores = []
        self.processing_times = []
        self.created_at = datetime.now()
        
    @property
    def success_rate(self) -> float:
        """Calculate the success rate of this prompt"""
        if self.calls == 0:
            return 0.0
        return (self.successful_calls / self.calls) * 100
    
    @property
    def avg_extraction_count(self) -> float:
        """Calculate the average number of extracted items"""
        if not self.extraction_counts:
            return 0.0
        return statistics.mean(self.extraction_counts)
    
    @property
    def avg_confidence(self) -> float:
        """Calculate the average confidence score"""
        if not self.confidence_scores:
            return 0.0
        return statistics.mean(self.confidence_scores)
    
    @property
    def avg_processing_time(self) -> float:
        """Calculate the average processing time"""
        if not self.processing_times:
            return 0.0
        return statistics.mean(self.processing_times)
    
    def record_result(self, success: bool, extraction_count: int, 
                     confidence: float, processing_time: float) -> None:
        """
        Record the result of using this prompt
        
        Args:
            success: Whether the call was successful
            extraction_count: Number of items extracted
            confidence: Confidence score (0-1)
            processing_time: Processing time in seconds
        """
        self.calls += 1
        if success:
            self.successful_calls += 1
        self.extraction_counts.append(extraction_count)
        self.confidence_scores.append(confidence)
        self.processing_times.append(processing_time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the prompt version to a dictionary"""
        return {
            "name": self.name,
            "description": self.description,
            "calls": self.calls,
            "success_rate": self.success_rate,
            "avg_extraction_count": self.avg_extraction_count,
            "avg_confidence": self.avg_confidence,
            "avg_processing_time": self.avg_processing_time,
            "created_at": self.created_at.isoformat()
        }
    
    def __str__(self) -> str:
        return f"{self.name} - Success Rate: {self.success_rate:.2f}% - Calls: {self.calls}"


class PromptOptimizer:
    """Class for managing and optimizing prompts through A/B testing"""
    
    def __init__(self):
        """Initialize the prompt optimizer"""
        self.prompts: Dict[str, PromptVersion] = {}
        self.active_prompt: Optional[str] = None
        self.test_mode = False
        self.test_distribution = {}  # For weighted testing
        
    def add_prompt(self, name: str, content: str, description: str = "") -> None:
        """
        Add a new prompt version
        
        Args:
            name: Unique identifier for the prompt
            content: The actual prompt text
            description: Description of what makes this prompt version unique
        """
        if name in self.prompts:
            logger.warning(f"Prompt '{name}' already exists and will be overwritten")
        
        self.prompts[name] = PromptVersion(name, content, description)
        logger.info(f"Added prompt version '{name}'")
        
        # If this is the first prompt, make it active
        if self.active_prompt is None:
            self.active_prompt = name
            logger.info(f"Set '{name}' as the active prompt")
    
    def set_active_prompt(self, name: str) -> bool:
        """
        Set the active prompt
        
        Args:
            name: Name of the prompt to set as active
            
        Returns:
            bool: True if successful, False otherwise
        """
        if name not in self.prompts:
            logger.error(f"Cannot set active prompt: '{name}' does not exist")
            return False
        
        self.active_prompt = name
        logger.info(f"Set '{name}' as the active prompt")
        return True
    
    def get_prompt_content(self, name: Optional[str] = None) -> Optional[str]:
        """
        Get the content of a prompt
        
        Args:
            name: Name of the prompt (uses active prompt if None)
            
        Returns:
            str: The prompt content or None if not found
        """
        if name is None:
            if self.active_prompt is None:
                logger.error("No active prompt set")
                return None
            name = self.active_prompt
        
        if name not in self.prompts:
            logger.error(f"Prompt '{name}' does not exist")
            return None
        
        return self.prompts[name].content
    
    def enable_testing(self, distribution: Optional[Dict[str, float]] = None) -> None:
        """
        Enable A/B testing mode
        
        Args:
            distribution: Optional dictionary mapping prompt names to weights
                          If None, equal distribution is used
        """
        if not self.prompts:
            logger.error("Cannot enable testing: no prompts defined")
            return
        
        self.test_mode = True
        
        # Set up distribution
        if distribution is None:
            # Equal distribution
            weight = 1.0 / len(self.prompts)
            self.test_distribution = {name: weight for name in self.prompts}
        else:
            # Validate and normalize the provided distribution
            total_weight = sum(weight for name, weight in distribution.items() if name in self.prompts)
            if total_weight <= 0:
                logger.error("Invalid distribution weights")
                return
            
            self.test_distribution = {
                name: (weight / total_weight) 
                for name, weight in distribution.items() 
                if name in self.prompts
            }
        
        logger.info(f"Enabled A/B testing with distribution: {self.test_distribution}")
    
    def disable_testing(self) -> None:
        """Disable A/B testing mode"""
        self.test_mode = False
        logger.info("Disabled A/B testing")
    
    def select_prompt(self) -> str:
        """
        Select a prompt based on current mode (testing or active)
        
        Returns:
            str: The selected prompt name
        """
        if not self.test_mode:
            if self.active_prompt is None and self.prompts:
                # If no active prompt but prompts exist, use the first one
                self.active_prompt = next(iter(self.prompts))
            return self.active_prompt
        
        # In test mode, select based on distribution
        if not self.test_distribution:
            # Equal distribution if not set
            prompt_names = list(self.prompts.keys())
            return random.choice(prompt_names)
        
        # Weighted random selection
        r = random.random()
        cumulative = 0.0
        for name, weight in self.test_distribution.items():
            cumulative += weight
            if r <= cumulative:
                return name
        
        # Fallback to active prompt
        return self.active_prompt
    
    def record_result(self, prompt_name: str, success: bool, extraction_count: int,
                     confidence: float, processing_time: float) -> None:
        """
        Record the result of using a prompt
        
        Args:
            prompt_name: Name of the prompt used
            success: Whether the call was successful
            extraction_count: Number of items extracted
            confidence: Confidence score (0-1)
            processing_time: Processing time in seconds
        """
        if prompt_name not in self.prompts:
            logger.error(f"Cannot record result: prompt '{prompt_name}' does not exist")
            return
        
        self.prompts[prompt_name].record_result(
            success, extraction_count, confidence, processing_time
        )
        logger.debug(f"Recorded result for prompt '{prompt_name}'")
    
    def get_best_prompt(self, min_calls: int = 10) -> Optional[str]:
        """
        Get the best performing prompt based on success rate
        
        Args:
            min_calls: Minimum number of calls required to consider a prompt
            
        Returns:
            str: Name of the best prompt or None if no qualifying prompts
        """
        qualifying_prompts = {
            name: prompt for name, prompt in self.prompts.items()
            if prompt.calls >= min_calls
        }
        
        if not qualifying_prompts:
            logger.warning(f"No prompts with at least {min_calls} calls")
            return None
        
        best_prompt = max(qualifying_prompts.values(), key=lambda p: p.success_rate)
        return best_prompt.name
    
    def get_performance_report(self) -> Dict[str, Any]:
        """
        Generate a performance report for all prompts
        
        Returns:
            dict: Performance metrics for all prompts
        """
        return {
            "prompts": {name: prompt.to_dict() for name, prompt in self.prompts.items()},
            "active_prompt": self.active_prompt,
            "test_mode": self.test_mode,
            "test_distribution": self.test_distribution,
            "generated_at": datetime.now().isoformat()
        }
    
    def save_report(self, filename: str) -> bool:
        """
        Save the performance report to a file
        
        Args:
            filename: Path to save the report
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            report = self.get_performance_report()
            with open(filename, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"Saved performance report to {filename}")
            return True
        except Exception as e:
            logger.error(f"Failed to save report: {str(e)}")
            return False
    
    def load_report(self, filename: str) -> bool:
        """
        Load a performance report from a file
        
        Args:
            filename: Path to the report file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(filename, 'r') as f:
                report = json.load(f)
            
            # Process the report data
            logger.info(f"Loaded performance report from {filename}")
            return True
        except Exception as e:
            logger.error(f"Failed to load report: {str(e)}")
            return False


# Create optimized prompt versions
def create_prompt_versions() -> Dict[str, str]:
    """
    Create different versions of prompts for testing
    
    Returns:
        dict: Mapping of prompt names to content
    """
    prompts = {}
    
    # Original prompt (baseline)
    prompts["original"] = """
    You are an AI assistant specializing in hotel stop sale and open sale email analysis. Your task is to extract structured information from emails and return it in a specific JSON format.

    Extract the following information and format it as:
    {
        "rows": [
            {
                "hotel_name": "Hotel name as mentioned in the email",
                "room_type": "Room type (or 'All Rooms' if not specified)",
                "market": "Market code or name (or 'ALL' if not specified)",
                "start_date": "Start date in YYYY-MM-DD format",
                "end_date": "End date in YYYY-MM-DD format", 
                "sale_status": "stop" or "open"
            },
            // Additional rows for other rules...
        ]
    }

    CRITICAL RULES:
    1. TABLE DETECTION: Pay special attention to HTML tables in the email. TREAT EACH TABLE ROW AS A SEPARATE RULE WITH ITS OWN DISTINCT ROOM TYPE AND DATE RANGE.
    2. MULTIPLE RULES: Create a separate JSON object for each distinct combination of hotel, room type, and date range.
    3. DATE FORMAT: Always convert all dates to YYYY-MM-DD format.
    4. MARKETS: If markets are not specified, use "ALL". Look for market information in both subject and body.
    5. JSON ONLY: Return only the JSON structure, no additional text or explanation.
    6. HTML PARSING: Pay attention to formatting in HTML emails - bold text often indicates hotel names, tables contain room and date information.
    7. COMPLETENESS: Each row must have hotel_name, room_type, market, start_date, end_date, and sale_status.
    
    Examples of stop sale indicators: "stop sale", "durdurulması", "stopsale", "close", "block", "kapatma"
    Examples of open sale indicators: "open sale", "açılması", "release", "unblock"
    """
    
    # Enhanced prompt with more detailed instructions
    prompts["enhanced_detail"] = """
    You are an AI assistant specializing in hotel stop sale and open sale email analysis. Your task is to extract structured information from emails and return it in a specific JSON format.

    Extract the following information and format it as:
    {
        "rows": [
            {
                "hotel_name": "Hotel name as mentioned in the email",
                "room_type": "Room type (or 'All Rooms' if not specified)",
                "market": "Market code or name (or 'ALL' if not specified)",
                "start_date": "Start date in YYYY-MM-DD format",
                "end_date": "End date in YYYY-MM-DD format", 
                "sale_status": "stop" or "open"
            },
            // Additional rows for other rules...
        ]
    }

    CRITICAL RULES:
    1. TABLE DETECTION: Pay special attention to HTML tables in the email. TREAT EACH TABLE ROW AS A SEPARATE RULE WITH ITS OWN DISTINCT ROOM TYPE AND DATE RANGE. Tables often contain the most structured information.
    2. MULTIPLE RULES: Create a separate JSON object for each distinct combination of hotel, room type, and date range. Be exhaustive in identifying all combinations.
    3. DATE FORMAT: Always convert all dates to YYYY-MM-DD format. Parse dates in any format (DD/MM/YYYY, MM/DD/YYYY, etc.) and standardize them.
    4. MARKETS: If markets are not specified, use "ALL". Look for market information in both subject and body. Market information may be indicated by country names, region codes, or specific market identifiers.
    5. JSON ONLY: Return only the JSON structure, no additional text or explanation. Ensure the JSON is valid and properly formatted.
    6. HTML PARSING: Pay attention to formatting in HTML emails - bold text often indicates hotel names, tables contain room and date information. Look for patterns in formatting that indicate important information.
    7. COMPLETENESS: Each row must have hotel_name, room_type, market, start_date, end_date, and sale_status. If any field is missing, make a reasonable inference based on context.
    8. MULTI-LANGUAGE SUPPORT: Recognize hotel information in multiple languages, including English, Turkish, German, and others.
    9. SPECIAL PHRASES: When "ALL ROOM TYPES" or similar phrases are mentioned, create separate entries for each room type if they can be inferred from context.
    10. CONFIDENCE SCORING: For each extracted field, assess your confidence level. Only include high-confidence extractions.
    
    Examples of stop sale indicators: "stop sale", "durdurulması", "stopsale", "close", "block", "kapatma", "kapama", "durdurma"
    Examples of open sale indicators: "open sale", "açılması", "release", "unblock", "açma", "serbest bırakma"
    
    Common date formats to recognize:
    - DD.MM.YYYY (e.g., 15.06.2025)
    - MM/DD/YYYY (e.g., 06/15/2025)
    - YYYY-MM-DD (e.g., 2025-06-15)
    - DD-MM-YYYY (e.g., 15-06-2025)
    - Text dates (e.g., "15 June 2025", "15 Haziran 2025")
    """
    
    # Prompt with examples
    prompts["with_examples"] = """
    You are an AI assistant specializing in hotel stop sale and open sale email analysis. Your task is to extract structured information from emails and return it in a specific JSON format.

    Extract the following information and format it as:
    {
        "rows": [
            {
                "hotel_name": "Hotel name as mentioned in the email",
                "room_type": "Room type (or 'All Rooms' if not specified)",
                "market": "Market code or name (or 'ALL' if not specified)",
                "start_date": "Start date in YYYY-MM-DD format",
                "end_date": "End date in YYYY-MM-DD format", 
                "sale_status": "stop" or "open"
            },
            // Additional rows for other rules...
        ]
    }

    CRITICAL RULES:
    1. TABLE DETECTION: Pay special attention to HTML tables in the email. TREAT EACH TABLE ROW AS A SEPARATE RULE WITH ITS OWN DISTINCT ROOM TYPE AND DATE RANGE.
    2. MULTIPLE RULES: Create a separate JSON object for each distinct combination of hotel, room type, and date range.
    3. DATE FORMAT: Always convert all dates to YYYY-MM-DD format.
    4. MARKETS: If markets are not specified, use "ALL". Look for market information in both subject and body.
    5. JSON ONLY: Return only the JSON structure, no additional text or explanation.
    6. HTML PARSING: Pay attention to formatting in HTML emails - bold text often indicates hotel names, tables contain room and date information.
    7. COMPLETENESS: Each row must have hotel_name, room_type, market, start_date, end_date, and sale_status.
    
    Examples of stop sale indicators: "stop sale", "durdurulması", "stopsale", "close", "block", "kapatma"
    Examples of open sale indicators: "open sale", "açılması", "release", "unblock"
    
    EXAMPLES:
    
    Example 1:
    Subject: Stop Sale - Hotel Sunshine - 01.07.2025-15.07.2025
    Body: Please be informed that Hotel Sunshine will be closed for all room types from 01.07.2025 to 15.07.2025 for the German market.
    
    Expected output:
    {
        "rows": [
            {
                "hotel_name": "Hotel Sunshine",
                "room_type": "All Rooms",
                "market": "GERMAN",
                "start_date": "2025-07-01",
                "end_date": "2025-07-15",
                "sale_status": "stop"
            }
        ]
    }
    
    Example 2:
    Subject: Open Sale Notification
    Body: <table>
    <tr><th>Hotel</th><th>Room Type</th><th>From</th><th>To</th></tr>
    <tr><td>Grand Resort</td><td>Standard</td><td>15/08/2025</td><td>30/08/2025</td></tr>
    <tr><td>Grand Resort</td><td>Deluxe</td><td>15/08/2025</td><td>30/08/2025</td></tr>
    </table>
    Please open sales for the above dates for all markets.
    
    Expected output:
    {
        "rows": [
            {
                "hotel_name": "Grand Resort",
                "room_type": "Standard",
                "market": "ALL",
                "start_date": "2025-08-15",
                "end_date": "2025-08-30",
                "sale_status": "open"
            },
            {
                "hotel_name": "Grand Resort",
                "room_type": "Deluxe",
                "market": "ALL",
                "start_date": "2025-08-15",
                "end_date": "2025-08-30",
                "sale_status": "open"
            }
        ]
    }
    """
    
    # Prompt optimized for multi-language support
    prompts["multilingual"] = """
    You are an AI assistant specializing in hotel stop sale and open sale email analysis. Your task is to extract structured information from emails and return it in a specific JSON format.

    Extract the following information and format it as:
    {
        "rows": [
            {
                "hotel_name": "Hotel name as mentioned in the email",
                "room_type": "Room type (or 'All Rooms' if not specified)",
                "market": "Market code or name (or 'ALL' if not specified)",
                "start_date": "Start date in YYYY-MM-DD format",
                "end_date": "End date in YYYY-MM-DD format", 
                "sale_status": "stop" or "open"
            },
            // Additional rows for other rules...
        ]
    }

    CRITICAL RULES:
    1. TABLE DETECTION: Pay special attention to HTML tables in the email. TREAT EACH TABLE ROW AS A SEPARATE RULE WITH ITS OWN DISTINCT ROOM TYPE AND DATE RANGE.
    2. MULTIPLE RULES: Create a separate JSON object for each distinct combination of hotel, room type, and date range.
    3. DATE FORMAT: Always convert all dates to YYYY-MM-DD format.
    4. MARKETS: If markets are not specified, use "ALL". Look for market information in both subject and body.
    5. JSON ONLY: Return only the JSON structure, no additional text or explanation.
    6. HTML PARSING: Pay attention to formatting in HTML emails - bold text often indicates hotel names, tables contain room and date information.
    7. COMPLETENESS: Each row must have hotel_name, room_type, market, start_date, end_date, and sale_status.
    8. MULTI-LANGUAGE SUPPORT: Recognize hotel information in multiple languages.
    
    LANGUAGE SPECIFIC INDICATORS:
    
    English:
    - Stop sale indicators: "stop sale", "close", "block", "closure"
    - Open sale indicators: "open sale", "release", "unblock"
    - Room type indicators: "room type", "room category", "accommodation"
    - Date indicators: "from", "to", "period", "dates"
    
    Turkish:
    - Stop sale indicators: "satış durdurma", "durdurulması", "kapatma", "bloke"
    - Open sale indicators: "satış açma", "açılması", "serbest bırakma"
    - Room type indicators: "oda tipi", "oda kategorisi", "konaklama"
    - Date indicators: "başlangıç", "bitiş", "tarihler", "dönem"
    
    German:
    - Stop sale indicators: "verkaufsstopp", "schließung", "blockierung"
    - Open sale indicators: "verkaufsfreigabe", "öffnung", "freigabe"
    - Room type indicators: "zimmertyp", "zimmerkategorie", "unterkunft"
    - Date indicators: "von", "bis", "zeitraum", "daten"
    
    Spanish:
    - Stop sale indicators: "parada de venta", "cierre", "bloqueo"
    - Open sale indicators: "apertura de venta", "liberación", "desbloqueo"
    - Room type indicators: "tipo de habitación", "categoría de habitación", "alojamiento"
    - Date indicators: "desde", "hasta", "período", "fechas"
    """
    
    # Prompt optimized for structured data extraction
    prompts["structured_extraction"] = """
    You are an AI assistant specializing in hotel stop sale and open sale email analysis. Your task is to extract structured information from emails and return it in a specific JSON format.

    EXTRACTION PROCESS:
    1. First, identify all hotel names mentioned in the email
    2. For each hotel, identify all room types mentioned (or use "All Rooms" if not specified)
    3. For each hotel-room combination, identify the date ranges mentioned
    4. For each hotel-room-date combination, determine if it's a stop sale or open sale
    5. For each combination, identify the market (or use "ALL" if not specified)
    6. Format all extracted information into the required JSON structure

    OUTPUT FORMAT:
    {
        "rows": [
            {
                "hotel_name": "Hotel name as mentioned in the email",
                "room_type": "Room type (or 'All Rooms' if not specified)",
                "market": "Market code or name (or 'ALL' if not specified)",
                "start_date": "Start date in YYYY-MM-DD format",
                "end_date": "End date in YYYY-MM-DD format", 
                "sale_status": "stop" or "open"
            },
            // Additional rows for other rules...
        ]
    }

    CRITICAL RULES:
    1. TABLE DETECTION: Pay special attention to HTML tables in the email. TREAT EACH TABLE ROW AS A SEPARATE RULE WITH ITS OWN DISTINCT ROOM TYPE AND DATE RANGE.
    2. MULTIPLE RULES: Create a separate JSON object for each distinct combination of hotel, room type, and date range.
    3. DATE FORMAT: Always convert all dates to YYYY-MM-DD format.
    4. MARKETS: If markets are not specified, use "ALL". Look for market information in both subject and body.
    5. JSON ONLY: Return only the JSON structure, no additional text or explanation.
    6. HTML PARSING: Pay attention to formatting in HTML emails - bold text often indicates hotel names, tables contain room and date information.
    7. COMPLETENESS: Each row must have hotel_name, room_type, market, start_date, end_date, and sale_status.
    
    Examples of stop sale indicators: "stop sale", "durdurulması", "stopsale", "close", "block", "kapatma"
    Examples of open sale indicators: "open sale", "açılması", "release", "unblock"
    """
    
    return prompts


# Initialize the optimizer with prompt versions
def initialize_optimizer() -> PromptOptimizer:
    """
    Initialize the prompt optimizer with different prompt versions
    
    Returns:
        PromptOptimizer: Initialized optimizer
    """
    optimizer = PromptOptimizer()
    
    prompts = create_prompt_versions()
    
    # Add each prompt version
    optimizer.add_prompt(
        "original", 
        prompts["original"],
        "Original baseline prompt"
    )
    
    optimizer.add_prompt(
        "enhanced_detail", 
        prompts["enhanced_detail"],
        "Enhanced prompt with more detailed instructions"
    )
    
    optimizer.add_prompt(
        "with_examples", 
        prompts["with_examples"],
        "Prompt with concrete examples"
    )
    
    optimizer.add_prompt(
        "multilingual", 
        prompts["multilingual"],
        "Prompt optimized for multi-language support"
    )
    
    optimizer.add_prompt(
        "structured_extraction", 
        prompts["structured_extraction"],
        "Prompt optimized for structured data extraction"
    )
    
    # Set the enhanced_detail as the active prompt initially
    optimizer.set_active_prompt("enhanced_detail")
    
    return optimizer


if __name__ == "__main__":
    # Example usage
    optimizer = initialize_optimizer()
    print(f"Created optimizer with {len(optimizer.prompts)} prompt versions")
    print(f"Active prompt: {optimizer.active_prompt}")
    
    # Enable A/B testing
    optimizer.enable_testing()
    
    # Example of selecting a prompt
    selected_prompt = optimizer.select_prompt()
    print(f"Selected prompt: {selected_prompt}")
    
    # Example of recording results
    optimizer.record_result(
        selected_prompt,
        success=True,
        extraction_count=5,
        confidence=0.85,
        processing_time=1.2
    )
    
    # Generate a report
    report = optimizer.get_performance_report()
    print(f"Performance report generated with {len(report['prompts'])} prompts")
