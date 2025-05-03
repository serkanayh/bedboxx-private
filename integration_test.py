"""
Modified Integration Test Runner for StopSale Automation System

This script runs integration tests for the StopSale Automation System
with improved error handling and non-interactive mode.
"""

import os
import sys
import logging
import importlib
import unittest
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path
project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.append(project_root)

class IntegrationTestRunner:
    """Class for running integration tests"""
    
    def __init__(self, output_dir=None, non_interactive=True):
        """
        Initialize the integration test runner
        
        Args:
            output_dir: Directory to store test results (if None, uses project_root/test_results)
            non_interactive: Whether to run in non-interactive mode (no password prompts)
        """
        self.non_interactive = non_interactive
        
        if output_dir is None:
            self.output_dir = os.path.join(project_root, "test_results")
        else:
            self.output_dir = os.path.abspath(output_dir)
        
        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Initialize test results
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "components": {},
            "summary": {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "errors": 0
            }
        }
        
        # Set environment variables for non-interactive mode
        if self.non_interactive:
            os.environ['STOPSALE_NON_INTERACTIVE'] = 'true'
            os.environ['STOPSALE_TEST_API_KEY'] = 'test_api_key_12345'
            os.environ['STOPSALE_TEST_MASTER_PASSWORD'] = 'test_master_password'
    
    def test_ai_integration(self):
        """
        Test AI analysis component integration
        
        Returns:
            dict: Test results
        """
        logger.info("Testing AI analysis component integration")
        
        results = {
            "name": "AI Analysis Component",
            "tests": [],
            "summary": {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "errors": 0
            }
        }
        
        # Test 1: Import AI modules
        try:
            # Mock imports for modules that might not be installed
            sys.modules['PyPDF2'] = type('MockPyPDF2', (), {})
            sys.modules['docx'] = type('MockDocx', (), {})
            sys.modules['pdfplumber'] = type('MockPdfPlumber', (), {})
            
            from ai.analyzer import ClaudeAnalyzer
            from ai.improvements.prompt_optimization import PromptOptimizer
            from ai.improvements.file_format_processor import FileFormatProcessor
            from ai.improvements.multi_language_support import LanguageDetector
            
            results["tests"].append({
                "name": "Import AI modules",
                "status": "passed",
                "message": "Successfully imported AI modules"
            })
            results["summary"]["passed"] += 1
        except Exception as e:
            results["tests"].append({
                "name": "Import AI modules",
                "status": "error",
                "message": f"Error importing AI modules: {str(e)}"
            })
            results["summary"]["errors"] += 1
        
        results["summary"]["total"] += 1
        
        # Test 2: Create ClaudeAnalyzer instance
        try:
            analyzer = ClaudeAnalyzer(api_key="test_key")
            
            results["tests"].append({
                "name": "Create ClaudeAnalyzer instance",
                "status": "passed",
                "message": "Successfully created ClaudeAnalyzer instance"
            })
            results["summary"]["passed"] += 1
        except Exception as e:
            results["tests"].append({
                "name": "Create ClaudeAnalyzer instance",
                "status": "error",
                "message": f"Error creating ClaudeAnalyzer instance: {str(e)}"
            })
            results["summary"]["errors"] += 1
        
        results["summary"]["total"] += 1
        
        # Test 3: File format processor integration
        try:
            processor = FileFormatProcessor()
            supported_formats = processor.get_supported_formats()
            
            if supported_formats and len(supported_formats) > 0:
                results["tests"].append({
                    "name": "File format processor integration",
                    "status": "passed",
                    "message": f"File format processor supports {len(supported_formats)} formats"
                })
                results["summary"]["passed"] += 1
            else:
                results["tests"].append({
                    "name": "File format processor integration",
                    "status": "failed",
                    "message": "File format processor does not support any formats"
                })
                results["summary"]["failed"] += 1
        except Exception as e:
            results["tests"].append({
                "name": "File format processor integration",
                "status": "error",
                "message": f"Error testing file format processor: {str(e)}"
            })
            results["summary"]["errors"] += 1
        
        results["summary"]["total"] += 1
        
        # Test 4: Language detector integration
        try:
            detector = LanguageDetector()
            test_text = "This is a test message in English."
            language = detector.detect_language(test_text)
            
            if language == "en":
                results["tests"].append({
                    "name": "Language detector integration",
                    "status": "passed",
                    "message": f"Language detector correctly identified English text"
                })
                results["summary"]["passed"] += 1
            else:
                results["tests"].append({
                    "name": "Language detector integration",
                    "status": "failed",
                    "message": f"Language detector identified '{language}' instead of 'en'"
                })
                results["summary"]["failed"] += 1
        except Exception as e:
            results["tests"].append({
                "name": "Language detector integration",
                "status": "error",
                "message": f"Error testing language detector: {str(e)}"
            })
            results["summary"]["errors"] += 1
        
        results["summary"]["total"] += 1
        
        return results
    
    def test_performance_integration(self):
        """
        Test performance optimization integration
        
        Returns:
            dict: Test results
        """
        logger.info("Testing performance optimization integration")
        
        results = {
            "name": "Performance Optimization",
            "tests": [],
            "summary": {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "errors": 0
            }
        }
        
        # Test 1: Import performance modules
        try:
            # Mock imports for modules that might not be installed
            sys.modules['redis'] = type('MockRedis', (), {})
            sys.modules['celery'] = type('MockCelery', (), {})
            
            from performance.database_optimizer import DatabaseOptimizer
            from performance.cache_mechanism import CacheManager
            from performance.async_processor import AsyncProcessor
            from performance.settings_integration import integrate_all_performance_settings
            
            results["tests"].append({
                "name": "Import performance modules",
                "status": "passed",
                "message": "Successfully imported performance modules"
            })
            results["summary"]["passed"] += 1
        except Exception as e:
            results["tests"].append({
                "name": "Import performance modules",
                "status": "error",
                "message": f"Error importing performance modules: {str(e)}"
            })
            results["summary"]["errors"] += 1
        
        results["summary"]["total"] += 1
        
        # Test 2: Create CacheManager instance
        try:
            cache = CacheManager()
            
            results["tests"].append({
                "name": "Create CacheManager instance",
                "status": "passed",
                "message": "Successfully created CacheManager instance"
            })
            results["summary"]["passed"] += 1
        except Exception as e:
            results["tests"].append({
                "name": "Create CacheManager instance",
                "status": "error",
                "message": f"Error creating CacheManager instance: {str(e)}"
            })
            results["summary"]["errors"] += 1
        
        results["summary"]["total"] += 1
        
        # Test 3: Create AsyncProcessor instance
        try:
            processor = AsyncProcessor(use_celery=False)
            
            results["tests"].append({
                "name": "Create AsyncProcessor instance",
                "status": "passed",
                "message": "Successfully created AsyncProcessor instance"
            })
            results["summary"]["passed"] += 1
            
            # Clean up
            processor.shutdown()
        except Exception as e:
            results["tests"].append({
                "name": "Create AsyncProcessor instance",
                "status": "error",
                "message": f"Error creating AsyncProcessor instance: {str(e)}"
            })
            results["summary"]["errors"] += 1
        
        results["summary"]["total"] += 1
        
        # Test 4: Create DatabaseOptimizer instance
        try:
            optimizer = DatabaseOptimizer()
            
            results["tests"].append({
                "name": "Create DatabaseOptimizer instance",
                "status": "passed",
                "message": "Successfully created DatabaseOptimizer instance"
            })
            results["summary"]["passed"] += 1
        except Exception as e:
            results["tests"].append({
                "name": "Create DatabaseOptimizer instance",
                "status": "error",
                "message": f"Error creating DatabaseOptimizer instance: {str(e)}"
            })
            results["summary"]["errors"] += 1
        
        results["summary"]["total"] += 1
        
        return results
    
    def test_security_integration(self):
        """
        Test security improvements integration
        
        Returns:
            dict: Test results
        """
        logger.info("Testing security improvements integration")
        
        results = {
            "name": "Security Improvements",
            "tests": [],
            "summary": {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "errors": 0
            }
        }
        
        # Test 1: Import security modules
        try:
            # Mock imports for modules that might not be installed
            sys.modules['cryptography'] = type('MockCryptography', (), {})
            
            from security.secure_api_key_manager import ApiKeyManager
            from security.sensitive_data_encryption import SensitiveDataHandler, EncryptionManager
            from security.auth_manager import AuthManager
            from security.middleware import SecurityHeadersMiddleware, ContentSecurityPolicyMiddleware
            from security.settings_integration import integrate_security_settings
            
            results["tests"].append({
                "name": "Import security modules",
                "status": "passed",
                "message": "Successfully imported security modules"
            })
            results["summary"]["passed"] += 1
        except Exception as e:
            results["tests"].append({
                "name": "Import security modules",
                "status": "error",
                "message": f"Error importing security modules: {str(e)}"
            })
            results["summary"]["errors"] += 1
        
        results["summary"]["total"] += 1
        
        # Test 2: Create ApiKeyManager instance
        try:
            # Create temporary directory for testing
            import tempfile
            temp_dir = tempfile.TemporaryDirectory()
            
            # Use non-interactive mode
            key_manager = ApiKeyManager(
                storage_path=os.path.join(temp_dir.name, "keys.enc"),
                master_password="test_master_password" if self.non_interactive else None
            )
            
            results["tests"].append({
                "name": "Create ApiKeyManager instance",
                "status": "passed",
                "message": "Successfully created ApiKeyManager instance"
            })
            results["summary"]["passed"] += 1
            
            # Clean up
            temp_dir.cleanup()
        except Exception as e:
            results["tests"].append({
                "name": "Create ApiKeyManager instance",
                "status": "error",
                "message": f"Error creating ApiKeyManager instance: {str(e)}"
            })
            results["summary"]["errors"] += 1
        
        results["summary"]["total"] += 1
        
        # Test 3: Create EncryptionManager instance
        try:
            # Create temporary directory for testing
            import tempfile
            temp_dir = tempfile.TemporaryDirectory()
            
            encryption_manager = EncryptionManager(
                key_path=os.path.join(temp_dir.name, "crypto"),
                master_password="test_master_password" if self.non_interactive else None
            )
            
            results["tests"].append({
                "name": "Create EncryptionManager instance",
                "status": "passed",
                "message": "Successfully created EncryptionManager instance"
            })
            results["summary"]["passed"] += 1
            
            # Clean up
            temp_dir.cleanup()
        except Exception as e:
            results["tests"].append({
                "name": "Create EncryptionManager instance",
                "status": "error",
                "message": f"Error creating EncryptionManager instance: {str(e)}"
            })
            results["summary"]["errors"] += 1
        
        results["summary"]["total"] += 1
        
        # Test 4: Create SecurityHeadersMiddleware instance
        try:
            middleware = SecurityHeadersMiddleware(get_response=lambda r: None)
            
            results["tests"].append({
                "name": "Create SecurityHeadersMiddleware instance",
                "status": "passed",
                "message": "Successfully created SecurityHeadersMiddleware instance"
            })
            results["summary"]["passed"] += 1
        except Exception as e:
            results["tests"].append({
                "name": "Create SecurityHeadersMiddleware instance",
                "status": "error",
                "message": f"Error creating SecurityHeadersMiddleware instance: {str(e)}"
            })
            results["summary"]["errors"] += 1
        
        results["summary"]["total"] += 1
        
        return results
    
    def test_code_quality_integration(self):
        """
        Test code quality improvements integration
        
        Returns:
            dict: Test results
        """
        logger.info("Testing code quality improvements integration")
        
        results = {
            "name": "Code Quality Improvements",
            "tests": [],
            "summary": {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "errors": 0
            }
        }
        
        # Test 1: Import code quality modules
        try:
            # Mock imports for modules that might not be installed
            sys.modules['flake8'] = type('MockFlake8', (), {})
            sys.modules['black'] = type('MockBlack', (), {})
            sys.modules['isort'] = type('MockIsort', (), {})
            sys.modules['mypy'] = type('MockMyPy', (), {})
            
            from code_quality.unit_testing import TestRunner
            from code_quality.dependency_manager import DependencyManager
            from code_quality.code_style_and_documentation import CodeStyleChecker, DocumentationGenerator
            from code_quality.management_commands import CheckCodeStyleCommand, GenerateDocsCommand
            
            results["tests"].append({
                "name": "Import code quality modules",
                "status": "passed",
                "message": "Successfully imported code quality modules"
            })
            results["summary"]["passed"] += 1
        except Exception as e:
            results["tests"].append({
                "name": "Import code quality modules",
                "status": "error",
                "message": f"Error importing code quality modules: {str(e)}"
            })
            results["summary"]["errors"] += 1
        
        results["summary"]["total"] += 1
        
        # Test 2: Create CodeStyleChecker instance
        try:
            checker = CodeStyleChecker(project_root=project_root)
            
            results["tests"].append({
                "name": "Create CodeStyleChecker instance",
                "status": "passed",
                "message": "Successfully created CodeStyleChecker instance"
            })
            results["summary"]["passed"] += 1
        except Exception as e:
            results["tests"].append({
                "name": "Create CodeStyleChecker instance",
                "status": "error",
                "message": f"Error creating CodeStyleChecker instance: {str(e)}"
            })
            results["summary"]["errors"] += 1
        
        results["summary"]["total"] += 1
        
        # Test 3: Create DocumentationGenerator instance
        try:
            # Create temporary directory for testing
            import tempfile
            temp_dir = tempfile.TemporaryDirectory()
            
            generator = DocumentationGenerator(
                project_root=project_root,
                output_dir=temp_dir.name
            )
            
            results["tests"].append({
                "name": "Create DocumentationGenerator instance",
                "status": "passed",
                "message": "Successfully created DocumentationGenerator instance"
            })
            results["summary"]["passed"] += 1
            
            # Clean up
            temp_dir.cleanup()
        except Exception as e:
            results["tests"].append({
                "name": "Create DocumentationGenerator instance",
                "status": "error",
                "message": f"Error creating DocumentationGenerator instance: {str(e)}"
            })
            results["summary"]["errors"] += 1
        
        results["summary"]["total"] += 1
        
        # Test 4: Create DependencyManager instance
        try:
            manager = DependencyManager(project_root=project_root)
            
            results["tests"].append({
                "name": "Create DependencyManager instance",
                "status": "passed",
                "message": "Successfully created DependencyManager instance"
            })
            results["summary"]["passed"] += 1
        except Exception as e:
            results["tests"].append({
                "name": "Create DependencyManager instance",
                "status": "error",
                "message": f"Error creating DependencyManager instance: {str(e)}"
            })
            results["summary"]["errors"] += 1
        
        results["summary"]["total"] += 1
        
        return results
    
    def run_all_tests(self):
        """
        Run all integration tests
        
        Returns:
            dict: Test results
        """
        logger.info("Running all integration tests")
        
        # Test AI integration
        ai_results = self.test_ai_integration()
        self.results["components"]["ai"] = ai_results
        
        # Test performance integration
        performance_results = self.test_performance_integration()
        self.results["components"]["performance"] = performance_results
        
        # Test security integration
        security_results = self.test_security_integration()
        self.results["components"]["security"] = security_results
        
        # Test code quality integration
        code_quality_results = self.test_code_quality_integration()
        self.results["components"]["code_quality"] = code_quality_results
        
        # Update summary
        for component, component_results in self.results["components"].items():
            self.results["summary"]["total"] += component_results["summary"]["total"]
            self.results["summary"]["passed"] += component_results["summary"]["passed"]
            self.results["summary"]["failed"] += component_results["summary"]["failed"]
            self.results["summary"]["errors"] += component_results["summary"]["errors"]
        
        return self.results
    
    def generate_report(self, format="html"):
        """
        Generate test report
        
        Args:
            format: Report format ('html', 'json', or 'text')
            
        Returns:
            str: Path to generated report file
        """
        if format.lower() == "json":
            return self._generate_json_report()
        elif format.lower() == "text":
            return self._generate_text_report()
        else:
            return self._generate_html_report()
    
    def _generate_text_report(self):
        """
        Generate text test report
        
        Returns:
            str: Path to generated report file
        """
        output_file = os.path.join(self.output_dir, "integration_test_report.txt")
        
        try:
            with open(output_file, 'w') as f:
                f.write("Integration Test Report\n")
                f.write("======================\n\n")
                f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                # Write summary
                f.write("Summary\n")
                f.write("-------\n")
                f.write(f"Total tests: {self.results['summary']['total']}\n")
                f.write(f"Passed: {self.results['summary']['passed']}\n")
                f.write(f"Failed: {self.results['summary']['failed']}\n")
                f.write(f"Errors: {self.results['summary']['errors']}\n\n")
                
                # Write component results
                for component_name, component_results in self.results["components"].items():
                    f.write(f"Component: {component_results['name']}\n")
                    f.write(f"{'-' * (len(component_results['name']) + 11)}\n")
                    f.write(f"Total: {component_results['summary']['total']}\n")
                    f.write(f"Passed: {component_results['summary']['passed']}\n")
                    f.write(f"Failed: {component_results['summary']['failed']}\n")
                    f.write(f"Errors: {component_results['summary']['errors']}\n\n")
                    
                    # Write test results
                    for test in component_results["tests"]:
                        f.write(f"  {test['name']}: {test['status'].upper()}\n")
                        f.write(f"    {test['message']}\n\n")
                    
                    f.write("\n")
            
            logger.info(f"Text report generated: {output_file}")
            return output_file
        
        except Exception as e:
            logger.error(f"Error generating text report: {str(e)}")
            return None
    
    def _generate_html_report(self):
        """
        Generate HTML test report
        
        Returns:
            str: Path to generated report file
        """
        output_file = os.path.join(self.output_dir, "integration_test_report.html")
        
        try:
            with open(output_file, 'w') as f:
                f.write("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Integration Test Report</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            color: #333;
        }
        h1, h2, h3 {
            color: #2c3e50;
        }
        .summary {
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        .component {
            margin-bottom: 30px;
            border: 1px solid #ddd;
            border-radius: 5px;
            padding: 15px;
        }
        .component-header {
            background-color: #f8f9fa;
            padding: 10px;
            margin: -15px -15px 15px -15px;
            border-bottom: 1px solid #ddd;
            border-radius: 5px 5px 0 0;
        }
        .test {
            margin-bottom: 10px;
            padding: 10px;
            border-radius: 5px;
        }
        .passed {
            background-color: #d4edda;
            color: #155724;
        }
        .failed {
            background-color: #f8d7da;
            color: #721c24;
        }
        .error {
            background-color: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
    </style>
</head>
<body>
    <h1>Integration Test Report</h1>
    <p>Date: """)
                
                f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>")
                
                # Write summary
                f.write("""
    <div class="summary">
        <h2>Summary</h2>
""")
                f.write(f"        <p><strong>Total tests:</strong> {self.results['summary']['total']}</p>")
                f.write(f"        <p><strong>Passed:</strong> {self.results['summary']['passed']}</p>")
                f.write(f"        <p><strong>Failed:</strong> {self.results['summary']['failed']}</p>")
                f.write(f"        <p><strong>Errors:</strong> {self.results['summary']['errors']}</p>")
                f.write("    </div>")
                
                # Write component results
                for component_name, component_results in self.results["components"].items():
                    f.write(f"""
    <div class="component">
        <div class="component-header">
            <h2>{component_results['name']}</h2>
        </div>
        <p><strong>Total:</strong> {component_results['summary']['total']}</p>
        <p><strong>Passed:</strong> {component_results['summary']['passed']}</p>
        <p><strong>Failed:</strong> {component_results['summary']['failed']}</p>
        <p><strong>Errors:</strong> {component_results['summary']['errors']}</p>
        
        <h3>Tests</h3>
""")
                    
                    # Write test results
                    for test in component_results["tests"]:
                        status_class = test["status"].lower()
                        f.write(f"""
        <div class="test {status_class}">
            <h4>{test['name']}</h4>
            <p>{test['message']}</p>
        </div>
""")
                    
                    f.write("    </div>")
                
                f.write("""
</body>
</html>
""")
            
            logger.info(f"HTML report generated: {output_file}")
            return output_file
        
        except Exception as e:
            logger.error(f"Error generating HTML report: {str(e)}")
            return None
    
    def _generate_json_report(self):
        """
        Generate JSON test report
        
        Returns:
            str: Path to generated report file
        """
        output_file = os.path.join(self.output_dir, "integration_test_report.json")
        
        try:
            import json
            
            with open(output_file, 'w') as f:
                json.dump(self.results, f, indent=2)
            
            logger.info(f"JSON report generated: {output_file}")
            return output_file
        
        except Exception as e:
            logger.error(f"Error generating JSON report: {str(e)}")
            return None


if __name__ == "__main__":
    # Create test runner
    runner = IntegrationTestRunner(non_interactive=True)
    
    # Run tests
    results = runner.run_all_tests()
    
    # Generate report
    report_file = runner.generate_report(format="html")
    
    # Print summary
    print("\nIntegration Test Summary:")
    print(f"Total tests: {results['summary']['total']}")
    print(f"Passed: {results['summary']['passed']}")
    print(f"Failed: {results['summary']['failed']}")
    print(f"Errors: {results['summary']['errors']}")
    
    if report_file:
        print(f"\nReport generated: {report_file}")
    
    # Exit with error code if any tests failed
    if results['summary']['failed'] > 0 or results['summary']['errors'] > 0:
        sys.exit(1)
    else:
        sys.exit(0)
