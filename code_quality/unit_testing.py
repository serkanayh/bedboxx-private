"""
Unit Testing Framework for StopSale Automation System

This module provides a comprehensive unit testing framework to improve code quality
and ensure the reliability of the system.
"""

import os
import sys
import unittest
import json
import logging
import tempfile
from typing import Dict, List, Any, Optional, Union, Callable
from unittest import mock
from datetime import datetime, timedelta

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Try to import Django test modules
try:
    from django.test import TestCase, Client, RequestFactory
    from django.urls import reverse
    from django.contrib.auth.models import User
    DJANGO_AVAILABLE = True
except ImportError:
    DJANGO_AVAILABLE = False
    logger.warning("Django test modules not available. Some tests will be skipped.")


class BaseTestCase(unittest.TestCase):
    """Base test case with common utilities"""
    
    def setUp(self):
        """Set up test environment"""
        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = self.temp_dir.name
        
        # Set up logging for tests
        self.log_handler = logging.StreamHandler(sys.stdout)
        self.log_handler.setLevel(logging.DEBUG)
        logger.addHandler(self.log_handler)
    
    def tearDown(self):
        """Clean up test environment"""
        # Remove temporary directory
        self.temp_dir.cleanup()
        
        # Remove log handler
        logger.removeHandler(self.log_handler)
    
    def create_test_file(self, filename: str, content: str) -> str:
        """
        Create a test file with content
        
        Args:
            filename: Name of the file
            content: Content to write
            
        Returns:
            str: Full path to the created file
        """
        filepath = os.path.join(self.test_dir, filename)
        with open(filepath, 'w') as f:
            f.write(content)
        return filepath
    
    def create_test_json(self, filename: str, data: Dict[str, Any]) -> str:
        """
        Create a test JSON file
        
        Args:
            filename: Name of the file
            data: JSON data
            
        Returns:
            str: Full path to the created file
        """
        filepath = os.path.join(self.test_dir, filename)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        return filepath
    
    def assert_json_equal(self, json1: Dict[str, Any], json2: Dict[str, Any], 
                          ignore_keys: Optional[List[str]] = None):
        """
        Assert that two JSON objects are equal, optionally ignoring specific keys
        
        Args:
            json1: First JSON object
            json2: Second JSON object
            ignore_keys: List of keys to ignore
        """
        if ignore_keys is None:
            ignore_keys = []
        
        # Create copies without ignored keys
        json1_filtered = {k: v for k, v in json1.items() if k not in ignore_keys}
        json2_filtered = {k: v for k, v in json2.items() if k not in ignore_keys}
        
        self.assertEqual(json1_filtered, json2_filtered)


class AIAnalyzerTests(BaseTestCase):
    """Tests for the AI analyzer component"""
    
    def setUp(self):
        """Set up test environment"""
        super().setUp()
        
        # Mock the Claude API
        self.claude_patcher = mock.patch('requests.post')
        self.mock_claude = self.claude_patcher.start()
        
        # Set up mock response
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "rows": [
                            {
                                "hotel_name": "Test Hotel",
                                "room_type": "Standard",
                                "market": "ALL",
                                "start_date": "2025-07-01",
                                "end_date": "2025-07-15",
                                "sale_status": "stop"
                            }
                        ]
                    })
                }
            ]
        }
        self.mock_claude.return_value = mock_response
    
    def tearDown(self):
        """Clean up test environment"""
        self.claude_patcher.stop()
        super().tearDown()
    
    def test_analyze_email_content(self):
        """Test analyzing email content"""
        # Import the enhanced analyzer
        sys.path.append('/home/ubuntu/project_analysis/ai_improvements')
        try:
            from enhanced_analyzer import EnhancedClaudeAnalyzer
            
            # Create analyzer instance
            analyzer = EnhancedClaudeAnalyzer(api_key="test_key")
            
            # Test email content
            email_content = """
            Subject: Stop Sale Notification
            
            Please be informed that Test Hotel will be closed for all room types from 01.07.2025 to 15.07.2025.
            """
            
            # Analyze email
            result = analyzer.analyze_email_content(email_content, "Stop Sale Notification")
            
            # Check result
            self.assertIsNotNone(result)
            self.assertIn("rows", result)
            self.assertEqual(len(result["rows"]), 1)
            
            row = result["rows"][0]
            self.assertEqual(row["hotel_name"], "Test Hotel")
            self.assertEqual(row["start_date"], "2025-07-01")
            self.assertEqual(row["end_date"], "2025-07-15")
            self.assertEqual(row["sale_status"], "stop")
            
        except ImportError as e:
            self.skipTest(f"Could not import EnhancedClaudeAnalyzer: {str(e)}")
    
    def test_prompt_optimization(self):
        """Test prompt optimization"""
        sys.path.append('/home/ubuntu/project_analysis/ai_improvements')
        try:
            from prompt_optimization import PromptOptimizer, initialize_optimizer
            
            # Create optimizer
            optimizer = initialize_optimizer()
            
            # Test prompt selection
            prompt_name = optimizer.select_prompt()
            self.assertIsNotNone(prompt_name)
            
            # Test prompt content retrieval
            prompt_content = optimizer.get_prompt_content(prompt_name)
            self.assertIsNotNone(prompt_content)
            
            # Test recording results
            optimizer.record_result(
                prompt_name,
                success=True,
                extraction_count=5,
                confidence=0.9,
                processing_time=1.2
            )
            
            # Test performance report
            report = optimizer.get_performance_report()
            self.assertIn("prompts", report)
            self.assertIn(prompt_name, report["prompts"])
            self.assertEqual(report["prompts"][prompt_name]["calls"], 1)
            
        except ImportError as e:
            self.skipTest(f"Could not import prompt_optimization: {str(e)}")
    
    def test_file_format_processor(self):
        """Test file format processor"""
        sys.path.append('/home/ubuntu/project_analysis/ai_improvements')
        try:
            from file_format_processor import FileFormatProcessor
            
            # Create processor
            processor = FileFormatProcessor()
            
            # Create a test CSV file
            csv_content = "hotel,room_type,start_date,end_date\nTest Hotel,Standard,2025-07-01,2025-07-15"
            csv_file = self.create_test_file("test.csv", csv_content)
            
            # Test CSV processing
            if processor.is_supported(csv_file):
                text, structured_data = processor._extract_tables_from_text(csv_content)
                self.assertGreater(len(structured_data), 0)
            
        except ImportError as e:
            self.skipTest(f"Could not import file_format_processor: {str(e)}")
    
    def test_multi_language_support(self):
        """Test multi-language support"""
        sys.path.append('/home/ubuntu/project_analysis/ai_improvements')
        try:
            from multi_language_support import LanguageDetector
            
            # Create language detector
            detector = LanguageDetector()
            
            # Test English detection
            english_text = "Please stop sale for all rooms from July 1 to July 15."
            self.assertEqual(detector.detect_language(english_text), "en")
            
            # Test pattern retrieval
            patterns = detector.get_language_patterns("en")
            self.assertIn("stop_sale", patterns)
            self.assertIn("open_sale", patterns)
            
        except ImportError as e:
            self.skipTest(f"Could not import multi_language_support: {str(e)}")


class DatabaseOptimizerTests(BaseTestCase):
    """Tests for the database optimizer component"""
    
    def setUp(self):
        """Set up test environment"""
        super().setUp()
        
        # Mock database connection
        self.db_patcher = mock.patch('psycopg2.connect')
        self.mock_db = self.db_patcher.start()
        
        # Set up mock cursor
        self.mock_cursor = mock.Mock()
        self.mock_connection = mock.Mock()
        self.mock_connection.cursor.return_value = self.mock_cursor
        self.mock_db.return_value = self.mock_connection
        
        # Set up mock cursor execution
        self.mock_cursor.fetchall.return_value = [
            ("Seq Scan on emails_email  (cost=0.00..10.00 rows=100 width=100)",),
            ("Index Scan using emails_email_pkey on emails_email  (cost=0.00..8.00 rows=1 width=100)",)
        ]
    
    def tearDown(self):
        """Clean up test environment"""
        self.db_patcher.stop()
        super().tearDown()
    
    def test_analyze_query_performance(self):
        """Test analyzing query performance"""
        sys.path.append('/home/ubuntu/project_analysis/performance_optimizations')
        try:
            from database_optimizer import DatabaseOptimizer
            
            # Create optimizer
            optimizer = DatabaseOptimizer(self.mock_connection)
            
            # Test query analysis
            query = "SELECT * FROM emails_email WHERE status = 'pending'"
            analysis = optimizer.analyze_query_performance(query)
            
            # Check analysis
            self.assertIsNotNone(analysis)
            self.assertIn("operations", analysis)
            self.assertIn("table_scans", analysis)
            self.assertIn("index_scans", analysis)
            
        except ImportError as e:
            self.skipTest(f"Could not import database_optimizer: {str(e)}")
    
    def test_generate_index_recommendations(self):
        """Test generating index recommendations"""
        sys.path.append('/home/ubuntu/project_analysis/performance_optimizations')
        try:
            from database_optimizer import DatabaseOptimizer
            
            # Create optimizer
            optimizer = DatabaseOptimizer(self.mock_connection)
            
            # Test query
            query = "SELECT * FROM emails_email WHERE status = 'pending' ORDER BY received_date"
            analysis = optimizer.analyze_query_performance(query)
            
            # Get recommendations
            recommendations = optimizer.get_index_recommendations()
            
            # Check recommendations
            self.assertIsInstance(recommendations, list)
            
        except ImportError as e:
            self.skipTest(f"Could not import database_optimizer: {str(e)}")
    
    def test_optimize_query(self):
        """Test query optimization"""
        sys.path.append('/home/ubuntu/project_analysis/performance_optimizations')
        try:
            from database_optimizer import DatabaseOptimizer
            
            # Create optimizer
            optimizer = DatabaseOptimizer(self.mock_connection)
            
            # Test query optimization
            query = "SELECT * FROM emails_email WHERE status = 'pending'"
            result = optimizer.optimize_query(query)
            
            # Check result
            self.assertIsNotNone(result)
            self.assertIn("original_query", result)
            self.assertIn("optimized_query", result)
            self.assertNotEqual(result["original_query"], result["optimized_query"])
            
        except ImportError as e:
            self.skipTest(f"Could not import database_optimizer: {str(e)}")


class CacheMechanismTests(BaseTestCase):
    """Tests for the cache mechanism component"""
    
    def test_memory_cache(self):
        """Test in-memory cache"""
        sys.path.append('/home/ubuntu/project_analysis/performance_optimizations')
        try:
            from cache_mechanism import CacheManager
            
            # Create cache manager with memory backend
            cache = CacheManager()
            
            # Test setting and getting values
            cache.set("test_key", "test_value")
            value = cache.get("test_key")
            self.assertEqual(value, "test_value")
            
            # Test complex values
            complex_value = {"name": "Test", "value": 42, "nested": {"a": 1, "b": 2}}
            cache.set("complex_key", complex_value)
            retrieved_value = cache.get("complex_key")
            self.assertEqual(retrieved_value, complex_value)
            
            # Test deletion
            cache.delete("test_key")
            value = cache.get("test_key")
            self.assertIsNone(value)
            
            # Test expiration
            cache.set("expiring_key", "expiring_value", ttl=1)  # 1 second TTL
            value = cache.get("expiring_key")
            self.assertEqual(value, "expiring_value")
            
            # Wait for expiration
            import time
            time.sleep(1.1)
            
            value = cache.get("expiring_key")
            self.assertIsNone(value)
            
        except ImportError as e:
            self.skipTest(f"Could not import cache_mechanism: {str(e)}")
    
    def test_cache_decorator(self):
        """Test cache decorator"""
        sys.path.append('/home/ubuntu/project_analysis/performance_optimizations')
        try:
            from cache_mechanism import cached
            
            # Create a function with cache decorator
            @cached(ttl=60)
            def expensive_function(a, b):
                # This would normally be an expensive operation
                return a + b
            
            # Call the function multiple times with the same arguments
            result1 = expensive_function(1, 2)
            result2 = expensive_function(1, 2)
            
            # Results should be the same
            self.assertEqual(result1, result2)
            
            # Call with different arguments
            result3 = expensive_function(3, 4)
            
            # Result should be different
            self.assertNotEqual(result1, result3)
            
        except ImportError as e:
            self.skipTest(f"Could not import cache_mechanism: {str(e)}")
    
    def test_model_cache(self):
        """Test model cache"""
        sys.path.append('/home/ubuntu/project_analysis/performance_optimizations')
        try:
            from cache_mechanism import ModelCache
            
            # Create model cache
            model_cache = ModelCache()
            
            # Test object caching
            obj = {"id": 1, "name": "Test Object", "value": 42}
            model_cache.set_object("test_model", 1, obj)
            
            # Retrieve object
            retrieved_obj = model_cache.get_object("test_model", 1)
            self.assertEqual(retrieved_obj, obj)
            
            # Test queryset caching
            queryset = [{"id": 1, "name": "Object 1"}, {"id": 2, "name": "Object 2"}]
            model_cache.set_queryset("test_model", "query_hash", queryset)
            
            # Retrieve queryset
            retrieved_queryset = model_cache.get_queryset("test_model", "query_hash")
            self.assertEqual(retrieved_queryset, queryset)
            
            # Test invalidation
            model_cache.invalidate_model("test_model")
            
            # Objects should be gone
            self.assertIsNone(model_cache.get_object("test_model", 1))
            self.assertIsNone(model_cache.get_queryset("test_model", "query_hash"))
            
        except ImportError as e:
            self.skipTest(f"Could not import cache_mechanism: {str(e)}")


class AsyncProcessorTests(BaseTestCase):
    """Tests for the asynchronous processor component"""
    
    def test_threading_task_manager(self):
        """Test threading task manager"""
        sys.path.append('/home/ubuntu/project_analysis/performance_optimizations')
        try:
            from async_processor import ThreadingTaskManager
            
            # Create task manager
            manager = ThreadingTaskManager(max_workers=2)
            manager.start()
            
            # Define a test task
            def test_task(a, b):
                return a + b
            
            # Submit task
            task_id = manager.submit_task(test_task, 1, 2)
            
            # Wait for task to complete
            import time
            time.sleep(0.5)
            
            # Get result
            result = manager.get_task_result(task_id)
            self.assertIsNotNone(result)
            self.assertEqual(result.status, "completed")
            self.assertEqual(result.result, 3)
            
            # Clean up
            manager.stop()
            
        except ImportError as e:
            self.skipTest(f"Could not import async_processor: {str(e)}")
    
    def test_async_processor(self):
        """Test async processor"""
        sys.path.append('/home/ubuntu/project_analysis/performance_optimizations')
        try:
            from async_processor import AsyncProcessor
            
            # Create processor with threading backend
            processor = AsyncProcessor(use_celery=False)
            
            # Define a test task
            def test_task(a, b):
                return a + b
            
            # Process task
            task_id = processor.process_async(test_task, 1, 2)
            
            # Wait for task to complete
            import time
            time.sleep(0.5)
            
            # Get result
            result = processor.get_result(task_id)
            self.assertIsNotNone(result)
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["result"], 3)
            
            # Clean up
            processor.shutdown()
            
        except ImportError as e:
            self.skipTest(f"Could not import async_processor: {str(e)}")
    
    def test_task_cancellation(self):
        """Test task cancellation"""
        sys.path.append('/home/ubuntu/project_analysis/performance_optimizations')
        try:
            from async_processor import AsyncProcessor
            
            # Create processor with threading backend
            processor = AsyncProcessor(use_celery=False)
            
            # Define a long-running task
            def long_task():
                import time
                time.sleep(10)
                return "Done"
            
            # Process task
            task_id = processor.process_async(long_task)
            
            # Cancel task
            result = processor.cancel_task(task_id)
            self.assertTrue(result)
            
            # Wait a bit
            import time
            time.sleep(0.5)
            
            # Get result
            result = processor.get_result(task_id)
            self.assertIsNotNone(result)
            self.assertEqual(result["status"], "canceled")
            
            # Clean up
            processor.shutdown()
            
        except ImportError as e:
            self.skipTest(f"Could not import async_processor: {str(e)}")


class SecurityTests(BaseTestCase):
    """Tests for the security components"""
    
    def test_api_key_manager(self):
        """Test API key manager"""
        sys.path.append('/home/ubuntu/project_analysis/security_improvements')
        try:
            from secure_api_key_manager import ApiKeyManager
            
            # Create API key manager with test directory
            key_manager = ApiKeyManager(storage_path=os.path.join(self.test_dir, "keys.enc"))
            
            # Test setting and getting keys
            key_manager.set_key("test_key", "test_value")
            value = key_manager.get_key("test_key")
            self.assertEqual(value, "test_value")
            
            # Test listing keys
            keys = key_manager.list_keys()
            self.assertIn("test_key", keys)
            
            # Test deleting keys
            key_manager.delete_key("test_key")
            value = key_manager.get_key("test_key")
            self.assertIsNone(value)
            
        except ImportError as e:
            self.skipTest(f"Could not import secure_api_key_manager: {str(e)}")
    
    def test_sensitive_data_encryption(self):
        """Test sensitive data encryption"""
        sys.path.append('/home/ubuntu/project_analysis/security_improvements')
        try:
            from sensitive_data_encryption import SensitiveDataHandler, EncryptionManager
            
            # Create encryption manager with test directory
            encryption_manager = EncryptionManager(
                key_path=os.path.join(self.test_dir, "crypto"),
                master_password="test_password"
            )
            
            # Create sensitive data handler
            handler = SensitiveDataHandler(encryption_manager)
            
            # Test field encryption
            encrypted = handler.encrypt_field("sensitive_value")
            self.assertNotEqual(encrypted, "sensitive_value")
            
            # Test field decryption
            decrypted = handler.decrypt_field(encrypted)
            self.assertEqual(decrypted, "sensitive_value")
            
            # Test JSON encryption
            data = {
                "name": "John Doe",
                "email": "john.doe@example.com",
                "ssn": "123-45-6789"
            }
            
            encrypted_data = handler.encrypt_json(data, ["email", "ssn"])
            self.assertNotIn("email", encrypted_data)
            self.assertNotIn("ssn", encrypted_data)
            self.assertIn("email_encrypted", encrypted_data)
            self.assertIn("ssn_encrypted", encrypted_data)
            
            # Test JSON decryption
            decrypted_data = handler.decrypt_json(encrypted_data)
            self.assertEqual(decrypted_data["email"], "john.doe@example.com")
            self.assertEqual(decrypted_data["ssn"], "123-45-6789")
            
            # Test password hashing
            password_hash = handler.hash_password("secure_password")
            self.assertNotEqual(password_hash, "secure_password")
            
            # Test password verification
            is_valid = handler.verify_password("secure_password", password_hash)
            self.assertTrue(is_valid)
            
            is_valid = handler.verify_password("wrong_password", password_hash)
            self.assertFalse(is_valid)
            
        except ImportError as e:
            self.skipTest(f"Could not import sensitive_data_encryption: {str(e)}")
    
    def test_auth_manager(self):
        """Test authentication manager"""
        sys.path.append('/home/ubuntu/project_analysis/security_improvements')
        try:
            from auth_manager import AuthManager, User, Role
            
            # Create auth manager with test directory
            auth_manager = AuthManager(storage_dir=os.path.join(self.test_dir, "auth"))
            
            # Test user creation
            auth_manager.create_user(
                username="testuser",
                email="test@example.com",
                password="password123",
                full_name="Test User",
                roles=["user"]
            )
            
            # Test authentication
            token = auth_manager.authenticate("testuser", "password123")
            self.assertIsNotNone(token)
            
            # Test session validation
            user_id = auth_manager.validate_session(token)
            self.assertEqual(user_id, "testuser")
            
            # Test permission checking
            has_permission = auth_manager.has_permission("testuser", "view_dashboard")
            self.assertTrue(has_permission)
            
            # Test logout
            auth_manager.logout(token)
            user_id = auth_manager.validate_session(token)
            self.assertIsNone(user_id)
            
        except ImportError as e:
            self.skipTest(f"Could not import auth_manager: {str(e)}")


class DjangoIntegrationTests(unittest.TestCase):
    """Tests for Django integration"""
    
    @unittest.skipIf(not DJANGO_AVAILABLE, "Django not available")
    def test_django_models(self):
        """Test Django models"""
        # This is a placeholder for Django model tests
        # In a real implementation, we would test the Django models
        # using Django's TestCase
        pass
    
    @unittest.skipIf(not DJANGO_AVAILABLE, "Django not available")
    def test_django_views(self):
        """Test Django views"""
        # This is a placeholder for Django view tests
        # In a real implementation, we would test the Django views
        # using Django's TestCase and Client
        pass
    
    @unittest.skipIf(not DJANGO_AVAILABLE, "Django not available")
    def test_django_forms(self):
        """Test Django forms"""
        # This is a placeholder for Django form tests
        # In a real implementation, we would test the Django forms
        # using Django's TestCase
        pass


def run_tests():
    """Run all tests"""
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test cases
    test_suite.addTest(unittest.makeSuite(AIAnalyzerTests))
    test_suite.addTest(unittest.makeSuite(DatabaseOptimizerTests))
    test_suite.addTest(unittest.makeSuite(CacheMechanismTests))
    test_suite.addTest(unittest.makeSuite(AsyncProcessorTests))
    test_suite.addTest(unittest.makeSuite(SecurityTests))
    
    # Add Django tests if available
    if DJANGO_AVAILABLE:
        test_suite.addTest(unittest.makeSuite(DjangoIntegrationTests))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(test_suite)


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    print("Unit Testing Framework")
    print("---------------------")
    print("This module provides a comprehensive unit testing framework.")
    
    # Run tests
    run_tests()
