"""
Asynchronous Processing Module for StopSale Automation System

This module implements asynchronous processing capabilities to improve system performance
by handling time-consuming tasks in the background.
"""

import os
import time
import logging
import json
import uuid
import threading
import queue
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from datetime import datetime, timedelta

# Set up logging
logger = logging.getLogger(__name__)

# Try to import Celery
try:
    from celery import Celery
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    logger.warning("Celery not installed. Asynchronous processing will use threading fallback.")


class TaskStatus:
    """Task status constants"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class TaskResult:
    """Class representing a task result"""
    
    def __init__(self, task_id: str, status: str = TaskStatus.PENDING, 
                 result: Any = None, error: Optional[str] = None):
        """
        Initialize a task result
        
        Args:
            task_id: Unique task identifier
            status: Task status
            result: Task result data
            error: Error message (if any)
        """
        self.task_id = task_id
        self.status = status
        self.result = result
        self.error = error
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
    
    def update(self, status: str, result: Any = None, error: Optional[str] = None):
        """
        Update the task result
        
        Args:
            status: New task status
            result: New result data
            error: New error message
        """
        self.status = status
        if result is not None:
            self.result = result
        if error is not None:
            self.error = error
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary
        
        Returns:
            dict: Dictionary representation
        """
        return {
            "task_id": self.task_id,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TaskResult':
        """
        Create from dictionary
        
        Args:
            data: Dictionary data
            
        Returns:
            TaskResult: New instance
        """
        result = cls(
            task_id=data["task_id"],
            status=data["status"],
            result=data["result"],
            error=data["error"]
        )
        result.created_at = datetime.fromisoformat(data["created_at"])
        result.updated_at = datetime.fromisoformat(data["updated_at"])
        return result


class ThreadingTaskManager:
    """Task manager using Python threading"""
    
    def __init__(self, max_workers: int = 5):
        """
        Initialize the task manager
        
        Args:
            max_workers: Maximum number of worker threads
        """
        self.max_workers = max_workers
        self.tasks = {}
        self.task_queue = queue.Queue()
        self.workers = []
        self.running = False
        self.lock = threading.Lock()
    
    def start(self):
        """Start the task manager"""
        if self.running:
            return
        
        self.running = True
        
        # Start worker threads
        for _ in range(self.max_workers):
            worker = threading.Thread(target=self._worker_loop)
            worker.daemon = True
            worker.start()
            self.workers.append(worker)
        
        logger.info(f"Started ThreadingTaskManager with {self.max_workers} workers")
    
    def stop(self):
        """Stop the task manager"""
        if not self.running:
            return
        
        self.running = False
        
        # Add termination signals to the queue
        for _ in range(self.max_workers):
            self.task_queue.put(None)
        
        # Wait for workers to terminate
        for worker in self.workers:
            worker.join(timeout=1.0)
        
        self.workers = []
        logger.info("Stopped ThreadingTaskManager")
    
    def _worker_loop(self):
        """Worker thread loop"""
        while self.running:
            try:
                # Get a task from the queue
                task = self.task_queue.get(timeout=1.0)
                
                # Check for termination signal
                if task is None:
                    break
                
                task_id, func, args, kwargs = task
                
                # Update task status
                with self.lock:
                    if task_id in self.tasks:
                        self.tasks[task_id].update(TaskStatus.RUNNING)
                
                try:
                    # Execute the task
                    result = func(*args, **kwargs)
                    
                    # Update task result
                    with self.lock:
                        if task_id in self.tasks:
                            self.tasks[task_id].update(TaskStatus.COMPLETED, result=result)
                
                except Exception as e:
                    logger.error(f"Error executing task {task_id}: {str(e)}")
                    
                    # Update task error
                    with self.lock:
                        if task_id in self.tasks:
                            self.tasks[task_id].update(TaskStatus.FAILED, error=str(e))
                
                finally:
                    # Mark task as done
                    self.task_queue.task_done()
            
            except queue.Empty:
                # Queue timeout, continue
                pass
            
            except Exception as e:
                logger.error(f"Error in worker loop: {str(e)}")
    
    def submit_task(self, func: Callable, *args, **kwargs) -> str:
        """
        Submit a task for execution
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            str: Task ID
        """
        # Generate a unique task ID
        task_id = str(uuid.uuid4())
        
        # Create task result
        task_result = TaskResult(task_id)
        
        # Store task result
        with self.lock:
            self.tasks[task_id] = task_result
        
        # Add task to queue
        self.task_queue.put((task_id, func, args, kwargs))
        
        logger.info(f"Submitted task {task_id}")
        return task_id
    
    def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """
        Get task result
        
        Args:
            task_id: Task ID
            
        Returns:
            TaskResult: Task result or None if not found
        """
        with self.lock:
            return self.tasks.get(task_id)
    
    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a task
        
        Args:
            task_id: Task ID
            
        Returns:
            bool: True if canceled, False otherwise
        """
        with self.lock:
            if task_id in self.tasks:
                task_result = self.tasks[task_id]
                if task_result.status == TaskStatus.PENDING:
                    task_result.update(TaskStatus.CANCELED)
                    return True
        return False
    
    def clean_old_tasks(self, max_age: timedelta = timedelta(days=1)):
        """
        Clean up old tasks
        
        Args:
            max_age: Maximum age of tasks to keep
        """
        now = datetime.now()
        with self.lock:
            task_ids = list(self.tasks.keys())
            for task_id in task_ids:
                task_result = self.tasks[task_id]
                if now - task_result.updated_at > max_age:
                    del self.tasks[task_id]


class CeleryTaskManager:
    """Task manager using Celery"""
    
    def __init__(self, app_name: str = 'stopsale', broker_url: str = 'redis://localhost:6379/0'):
        """
        Initialize the task manager
        
        Args:
            app_name: Celery application name
            broker_url: Celery broker URL
        """
        if not CELERY_AVAILABLE:
            raise ImportError("Celery is not installed")
        
        self.app = Celery(app_name, broker=broker_url)
        self.app.conf.update(
            task_serializer='json',
            accept_content=['json'],
            result_serializer='json',
            enable_utc=True,
            task_track_started=True,
            result_backend=broker_url
        )
        
        logger.info(f"Initialized CeleryTaskManager with broker {broker_url}")
    
    def submit_task(self, func: Callable, *args, **kwargs) -> str:
        """
        Submit a task for execution
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            str: Task ID
        """
        # Create a Celery task
        task = self.app.task(func)
        
        # Submit the task
        result = task.delay(*args, **kwargs)
        
        logger.info(f"Submitted Celery task {result.id}")
        return result.id
    
    def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """
        Get task result
        
        Args:
            task_id: Task ID
            
        Returns:
            TaskResult: Task result or None if not found
        """
        try:
            # Get the Celery result
            async_result = self.app.AsyncResult(task_id)
            
            # Map Celery status to our status
            status_map = {
                'PENDING': TaskStatus.PENDING,
                'STARTED': TaskStatus.RUNNING,
                'SUCCESS': TaskStatus.COMPLETED,
                'FAILURE': TaskStatus.FAILED,
                'REVOKED': TaskStatus.CANCELED
            }
            
            status = status_map.get(async_result.status, TaskStatus.PENDING)
            
            # Create task result
            result = None
            error = None
            
            if status == TaskStatus.COMPLETED:
                result = async_result.result
            elif status == TaskStatus.FAILED:
                error = str(async_result.result)
            
            return TaskResult(task_id, status, result, error)
        
        except Exception as e:
            logger.error(f"Error getting Celery task result {task_id}: {str(e)}")
            return None
    
    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a task
        
        Args:
            task_id: Task ID
            
        Returns:
            bool: True if canceled, False otherwise
        """
        try:
            self.app.control.revoke(task_id, terminate=True)
            return True
        except Exception as e:
            logger.error(f"Error canceling Celery task {task_id}: {str(e)}")
            return False


class AsyncProcessor:
    """Main asynchronous processing class"""
    
    def __init__(self, use_celery: bool = True, max_workers: int = 5, 
                 broker_url: str = 'redis://localhost:6379/0'):
        """
        Initialize the async processor
        
        Args:
            use_celery: Whether to use Celery (if available)
            max_workers: Maximum number of worker threads (for threading backend)
            broker_url: Celery broker URL (for Celery backend)
        """
        # Initialize task manager
        if use_celery and CELERY_AVAILABLE:
            try:
                self.task_manager = CeleryTaskManager(broker_url=broker_url)
                self.backend = 'celery'
                logger.info("Using Celery for asynchronous processing")
            except Exception as e:
                logger.error(f"Failed to initialize Celery: {str(e)}")
                self.task_manager = ThreadingTaskManager(max_workers=max_workers)
                self.task_manager.start()
                self.backend = 'threading'
                logger.info("Falling back to threading for asynchronous processing")
        else:
            self.task_manager = ThreadingTaskManager(max_workers=max_workers)
            self.task_manager.start()
            self.backend = 'threading'
            logger.info("Using threading for asynchronous processing")
    
    def process_async(self, func: Callable, *args, **kwargs) -> str:
        """
        Process a function asynchronously
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            str: Task ID
        """
        return self.task_manager.submit_task(func, *args, **kwargs)
    
    def get_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get task result
        
        Args:
            task_id: Task ID
            
        Returns:
            dict: Task result or None if not found
        """
        result = self.task_manager.get_task_result(task_id)
        if result:
            return result.to_dict()
        return None
    
    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a task
        
        Args:
            task_id: Task ID
            
        Returns:
            bool: True if canceled, False otherwise
        """
        return self.task_manager.cancel_task(task_id)
    
    def shutdown(self):
        """Shutdown the processor"""
        if self.backend == 'threading':
            self.task_manager.stop()


# Example async tasks

def process_email_async(processor, email_id):
    """
    Process an email asynchronously
    
    Args:
        processor: AsyncProcessor instance
        email_id: Email ID
        
    Returns:
        str: Task ID
    """
    def _process_email(email_id):
        # This would be the actual email processing logic
        logger.info(f"Processing email {email_id}")
        time.sleep(2)  # Simulate processing time
        return {"email_id": email_id, "processed": True}
    
    return processor.process_async(_process_email, email_id)


def analyze_hotel_data_async(processor, hotel_id, date_range):
    """
    Analyze hotel data asynchronously
    
    Args:
        processor: AsyncProcessor instance
        hotel_id: Hotel ID
        date_range: Date range
        
    Returns:
        str: Task ID
    """
    def _analyze_hotel_data(hotel_id, date_range):
        # This would be the actual analysis logic
        logger.info(f"Analyzing hotel {hotel_id} for date range {date_range}")
        time.sleep(5)  # Simulate processing time
        return {
            "hotel_id": hotel_id,
            "date_range": date_range,
            "occupancy_rate": 0.75,
            "revenue": 12500.0
        }
    
    return processor.process_async(_analyze_hotel_data, hotel_id, date_range)


def generate_report_async(processor, report_type, params):
    """
    Generate a report asynchronously
    
    Args:
        processor: AsyncProcessor instance
        report_type: Report type
        params: Report parameters
        
    Returns:
        str: Task ID
    """
    def _generate_report(report_type, params):
        # This would be the actual report generation logic
        logger.info(f"Generating {report_type} report with params {params}")
        time.sleep(10)  # Simulate processing time
        return {
            "report_type": report_type,
            "params": params,
            "generated_at": datetime.now().isoformat(),
            "url": f"/reports/{report_type}_{int(time.time())}.pdf"
        }
    
    return processor.process_async(_generate_report, report_type, params)


def install_dependencies():
    """Install required dependencies if not already installed"""
    try:
        import pip
        
        # Check and install dependencies
        if not CELERY_AVAILABLE:
            print("Installing Celery...")
            pip.main(['install', 'celery'])
        
        print("Dependencies installed successfully.")
        
    except Exception as e:
        print(f"Error installing dependencies: {str(e)}")


# Django integration
def setup_django_celery():
    """
    Set up Celery for Django
    
    Returns:
        str: Setup instructions
    """
    instructions = """
    # Create a celery.py file in your Django project directory:
    
    from __future__ import absolute_import, unicode_literals
    import os
    from celery import Celery
    
    # Set the default Django settings module
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stopsale.settings')
    
    app = Celery('stopsale')
    
    # Use a string here to avoid namespace issues
    app.config_from_object('django.conf:settings', namespace='CELERY')
    
    # Load task modules from all registered Django app configs
    app.autodiscover_tasks()
    
    
    # Add the following to your Django __init__.py:
    
    from __future__ import absolute_import, unicode_literals
    from .celery import app as celery_app
    
    __all__ = ('celery_app',)
    
    
    # Add the following to your Django settings.py:
    
    CELERY_BROKER_URL = 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_TIMEZONE = 'UTC'
    """
    return instructions


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    print("Asynchronous Processing Module")
    print("-----------------------------")
    print("This module provides asynchronous processing capabilities for the StopSale Automation System.")
    
    # Check if Celery is installed
    if not CELERY_AVAILABLE:
        print("\nCelery not installed.")
        install = input("Do you want to install it? (y/n): ")
        if install.lower() == 'y':
            install_dependencies()
    
    # Example usage
    print("\nExample usage:")
    processor = AsyncProcessor(use_celery=False)  # Use threading for example
    
    # Process an email
    email_task_id = process_email_async(processor, "email123")
    print(f"Started email processing task: {email_task_id}")
    
    # Wait a bit
    time.sleep(1)
    
    # Check result
    result = processor.get_result(email_task_id)
    print(f"Email task status: {result['status']}")
    
    # Wait for completion
    time.sleep(2)
    
    # Check result again
    result = processor.get_result(email_task_id)
    print(f"Email task result: {result}")
    
    # Shutdown
    processor.shutdown()
    
    # Django integration
    print("\nDjango integration:")
    print(setup_django_celery())
