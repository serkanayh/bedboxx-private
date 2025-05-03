"""
Multi-Language Support Module for StopSale Automation System

This module enhances the AI analyzer with multi-language detection and processing
capabilities for handling emails in different languages.
"""

import re
import logging
from typing import Dict, List, Optional, Any, Tuple

# Set up logging
logger = logging.getLogger(__name__)

# Try to import optional dependencies
try:
    import langdetect
    from langdetect import detect, DetectorFactory
    # Set seed for consistent language detection
    DetectorFactory.seed = 0
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False
    logger.warning("langdetect not installed. Language detection will be limited.")


class LanguageDetector:
    """Class for detecting and handling different languages in emails"""
    
    # Language codes and their full names
    LANGUAGE_NAMES = {
        'en': 'English',
        'tr': 'Turkish',
        'de': 'German',
        'es': 'Spanish',
        'fr': 'French',
        'it': 'Italian',
        'ru': 'Russian',
        'nl': 'Dutch',
        'pt': 'Portuguese',
        'pl': 'Polish',
        'ar': 'Arabic',
        'zh-cn': 'Chinese (Simplified)',
        'ja': 'Japanese',
    }
    
    # Language-specific patterns for stop sale and open sale
    LANGUAGE_PATTERNS = {
        'en': {
            'stop_sale': [r'stop\s+sale', r'close', r'block', r'closure', r'stop\s+booking'],
            'open_sale': [r'open\s+sale', r'release', r'unblock', r'reopen'],
            'room_type': [r'room\s+type', r'room\s+category', r'accommodation'],
            'date': [r'from', r'to', r'period', r'dates', r'between'],
            'market': [r'market', r'country', r'region', r'territory']
        },
        'tr': {
            'stop_sale': [r'satış\s+durdurma', r'durdurulması', r'kapatma', r'bloke', r'satış\s+kapatma'],
            'open_sale': [r'satış\s+açma', r'açılması', r'serbest\s+bırakma', r'açık\s+satış'],
            'room_type': [r'oda\s+tipi', r'oda\s+kategorisi', r'konaklama'],
            'date': [r'başlangıç', r'bitiş', r'tarihler', r'dönem', r'arasında'],
            'market': [r'pazar', r'ülke', r'bölge', r'teritorya']
        },
        'de': {
            'stop_sale': [r'verkaufsstopp', r'schließung', r'blockierung', r'sperren'],
            'open_sale': [r'verkaufsfreigabe', r'öffnung', r'freigabe', r'entsperren'],
            'room_type': [r'zimmertyp', r'zimmerkategorie', r'unterkunft'],
            'date': [r'von', r'bis', r'zeitraum', r'daten', r'zwischen'],
            'market': [r'markt', r'land', r'region', r'gebiet']
        },
        'es': {
            'stop_sale': [r'parada\s+de\s+venta', r'cierre', r'bloqueo', r'stop\s+sale'],
            'open_sale': [r'apertura\s+de\s+venta', r'liberación', r'desbloqueo', r'open\s+sale'],
            'room_type': [r'tipo\s+de\s+habitación', r'categoría\s+de\s+habitación', r'alojamiento'],
            'date': [r'desde', r'hasta', r'período', r'fechas', r'entre'],
            'market': [r'mercado', r'país', r'región', r'territorio']
        },
        'fr': {
            'stop_sale': [r'arrêt\s+des\s+ventes', r'fermeture', r'blocage', r'stop\s+sale'],
            'open_sale': [r'ouverture\s+des\s+ventes', r'libération', r'déblocage', r'open\s+sale'],
            'room_type': [r'type\s+de\s+chambre', r'catégorie\s+de\s+chambre', r'hébergement'],
            'date': [r'du', r'au', r'période', r'dates', r'entre'],
            'market': [r'marché', r'pays', r'région', r'territoire']
        },
    }
    
    def __init__(self):
        """Initialize the language detector"""
        self.default_language = 'en'
    
    def detect_language(self, text: str) -> str:
        """
        Detect the language of a text
        
        Args:
            text: The text to analyze
            
        Returns:
            str: The detected language code (ISO 639-1)
        """
        if not text or not isinstance(text, str):
            return self.default_language
            
        if not LANGDETECT_AVAILABLE:
            logger.warning("langdetect not installed. Using default language.")
            return self.default_language
            
        try:
            # Clean the text to improve detection
            cleaned_text = self._clean_text_for_detection(text)
            
            # Detect language
            lang = detect(cleaned_text)
            
            # Map Chinese variants
            if lang.startswith('zh'):
                lang = 'zh-cn'
                
            logger.info(f"Detected language: {lang} ({self.get_language_name(lang)})")
            return lang
        
        except Exception as e:
            logger.error(f"Error detecting language: {str(e)}")
            return self.default_language
    
    def _clean_text_for_detection(self, text: str) -> str:
        """
        Clean text to improve language detection
        
        Args:
            text: The text to clean
            
        Returns:
            str: The cleaned text
        """
        # Remove URLs
        text = re.sub(r'https?://\S+', '', text)
        
        # Remove email addresses
        text = re.sub(r'\S+@\S+', '', text)
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Remove special characters and numbers
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\d+', '', text)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def get_language_name(self, lang_code: str) -> str:
        """
        Get the full name of a language from its code
        
        Args:
            lang_code: The language code
            
        Returns:
            str: The language name
        """
        return self.LANGUAGE_NAMES.get(lang_code, f"Unknown ({lang_code})")
    
    def get_language_patterns(self, lang_code: str) -> Dict[str, List[str]]:
        """
        Get language-specific patterns for a language
        
        Args:
            lang_code: The language code
            
        Returns:
            dict: Dictionary of patterns for the language
        """
        # If language not supported, fall back to English
        if lang_code not in self.LANGUAGE_PATTERNS:
            logger.info(f"No specific patterns for {lang_code}, using English patterns")
            lang_code = 'en'
            
        return self.LANGUAGE_PATTERNS[lang_code]
    
    def enhance_prompt_for_language(self, prompt: str, lang_code: str) -> str:
        """
        Enhance a prompt with language-specific instructions
        
        Args:
            prompt: The original prompt
            lang_code: The detected language code
            
        Returns:
            str: The enhanced prompt
        """
        # If language is English or not supported, return original prompt
        if lang_code == 'en' or lang_code not in self.LANGUAGE_PATTERNS:
            return prompt
            
        # Get language patterns
        patterns = self.get_language_patterns(lang_code)
        language_name = self.get_language_name(lang_code)
        
        # Create language-specific instructions
        language_instructions = f"""
        IMPORTANT: This email appears to be in {language_name}. Pay special attention to the following language-specific indicators:
        
        - Stop sale indicators: {', '.join([p.replace('\\s+', ' ') for p in patterns['stop_sale']])}
        - Open sale indicators: {', '.join([p.replace('\\s+', ' ') for p in patterns['open_sale']])}
        - Room type indicators: {', '.join([p.replace('\\s+', ' ') for p in patterns['room_type']])}
        - Date indicators: {', '.join([p.replace('\\s+', ' ') for p in patterns['date']])}
        - Market indicators: {', '.join([p.replace('\\s+', ' ') for p in patterns['market']])}
        """
        
        # Add instructions to the prompt
        # Find a good insertion point - after the initial instructions but before the examples
        if "CRITICAL RULES:" in prompt:
            # Insert before the critical rules
            parts = prompt.split("CRITICAL RULES:", 1)
            enhanced_prompt = parts[0] + language_instructions + "\n\nCRITICAL RULES:" + parts[1]
        else:
            # Append to the end if no good insertion point
            enhanced_prompt = prompt + "\n\n" + language_instructions
            
        logger.info(f"Enhanced prompt with {language_name} specific instructions")
        return enhanced_prompt


class MultiLanguageAnalyzer:
    """Class for analyzing emails in multiple languages"""
    
    def __init__(self):
        """Initialize the multi-language analyzer"""
        self.language_detector = LanguageDetector()
    
    def preprocess_email(self, email_content: str, subject: str = "") -> Dict[str, Any]:
        """
        Preprocess an email for analysis
        
        Args:
            email_content: The email content
            subject: The email subject
            
        Returns:
            dict: Preprocessing results including detected language
        """
        # Combine subject and content for better language detection
        full_text = f"{subject}\n\n{email_content}"
        
        # Detect language
        lang_code = self.language_detector.detect_language(full_text)
        
        # Get language patterns
        patterns = self.language_detector.get_language_patterns(lang_code)
        
        return {
            "language": lang_code,
            "language_name": self.language_detector.get_language_name(lang_code),
            "patterns": patterns,
            "preprocessed_content": email_content,  # Could add more preprocessing here
            "preprocessed_subject": subject,        # Could add more preprocessing here
        }
    
    def enhance_prompt(self, prompt: str, preprocessing_result: Dict[str, Any]) -> str:
        """
        Enhance a prompt based on preprocessing results
        
        Args:
            prompt: The original prompt
            preprocessing_result: Results from preprocess_email
            
        Returns:
            str: The enhanced prompt
        """
        lang_code = preprocessing_result.get("language", "en")
        return self.language_detector.enhance_prompt_for_language(prompt, lang_code)
    
    def postprocess_results(self, results: Dict[str, Any], preprocessing_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Postprocess analysis results based on preprocessing
        
        Args:
            results: The analysis results
            preprocessing_result: Results from preprocess_email
            
        Returns:
            dict: The postprocessed results
        """
        # Add language information to results
        results["detected_language"] = preprocessing_result.get("language", "en")
        results["detected_language_name"] = preprocessing_result.get("language_name", "English")
        
        # Could add more language-specific postprocessing here
        
        return results


def install_dependencies():
    """Install required dependencies if not already installed"""
    try:
        import pip
        
        # Check and install dependencies
        if not LANGDETECT_AVAILABLE:
            print("Installing langdetect...")
            pip.main(['install', 'langdetect'])
        
        print("Dependencies installed successfully.")
        
    except Exception as e:
        print(f"Error installing dependencies: {str(e)}")


if __name__ == "__main__":
    # Example usage
    analyzer = MultiLanguageAnalyzer()
    
    # Check if dependencies are installed
    if not LANGDETECT_AVAILABLE:
        print("langdetect is not installed.")
        install = input("Do you want to install it? (y/n): ")
        if install.lower() == 'y':
            install_dependencies()
    
    # Example preprocessing
    test_email = """
    Merhaba,
    
    Lütfen aşağıdaki oteller için satış durdurma işlemi yapınız:
    
    Otel: Grand Hotel Ankara
    Oda Tipi: Tüm Odalar
    Tarih: 15.07.2025 - 30.07.2025
    
    Teşekkürler,
    Rezervasyon Departmanı
    """
    
    preprocessing = analyzer.preprocess_email(test_email, "Satış Durdurma Bildirimi")
    print(f"Detected language: {preprocessing['language_name']} ({preprocessing['language']})")
    
    # Example prompt enhancement
    original_prompt = """
    You are an AI assistant specializing in hotel stop sale and open sale email analysis.
    Extract the following information and format it as JSON.
    
    CRITICAL RULES:
    1. TABLE DETECTION: Pay special attention to HTML tables in the email.
    2. MULTIPLE RULES: Create a separate JSON object for each distinct combination.
    """
    
    enhanced_prompt = analyzer.enhance_prompt(original_prompt, preprocessing)
    print("\nEnhanced prompt:")
    print(enhanced_prompt)
