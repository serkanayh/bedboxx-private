"""
Django Management Commands for Code Quality

This module provides Django management commands for code quality tools.
"""

import os
import logging
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

class CheckCodeStyleCommand(BaseCommand):
    """
    Django management command to check code style
    """
    
    help = 'Check code style of the project'
    
    def add_arguments(self, parser):
        """
        Add command arguments
        
        Args:
            parser: The argument parser
        """
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Fix code style issues',
        )
        parser.add_argument(
            '--report',
            action='store_true',
            help='Generate report',
        )
        parser.add_argument(
            '--output',
            help='Output file for report',
        )
    
    def handle(self, *args, **options):
        """
        Command handler
        
        Args:
            *args: Command arguments
            **options: Command options
        """
        from code_quality.code_style_and_documentation import CodeStyleChecker
        
        # Get project root
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Create code style checker
        checker = CodeStyleChecker(project_root)
        
        if options['fix']:
            # Fix code style issues
            results = checker.fix_project()
            
            self.stdout.write(self.style.SUCCESS(
                f"Fixed {results['summary']['fixed_files']} of {results['summary']['total_files']} files"
            ))
        else:
            # Check code style
            results = checker.check_project()
            
            self.stdout.write(self.style.SUCCESS(
                f"Found {results['summary']['total_errors']} errors and {results['summary']['total_warnings']} warnings "
                f"in {results['summary']['total_files']} files"
            ))
        
        # Generate report if requested
        if options['report']:
            import json
            
            output_file = options['output'] or 'code_style_report.json'
            
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2)
            
            self.stdout.write(self.style.SUCCESS(
                f"Report generated: {output_file}"
            ))


class GenerateDocsCommand(BaseCommand):
    """
    Django management command to generate documentation
    """
    
    help = 'Generate documentation for the project'
    
    def add_arguments(self, parser):
        """
        Add command arguments
        
        Args:
            parser: The argument parser
        """
        parser.add_argument(
            '--format',
            choices=['markdown', 'html'],
            default='html',
            help='Documentation format',
        )
        parser.add_argument(
            '--output',
            help='Output directory',
        )
    
    def handle(self, *args, **options):
        """
        Command handler
        
        Args:
            *args: Command arguments
            **options: Command options
        """
        from code_quality.code_style_and_documentation import DocumentationGenerator
        
        # Get project root
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Get output directory
        output_dir = options['output'] or os.path.join(project_root, 'docs')
        
        # Create documentation generator
        generator = DocumentationGenerator(project_root, output_dir)
        
        # Generate documentation
        results = generator.generate_project_documentation(format=options['format'])
        
        self.stdout.write(self.style.SUCCESS(
            f"Generated documentation for {results['summary']['successful_modules']} of {results['summary']['total_modules']} modules"
        ))
        self.stdout.write(self.style.SUCCESS(
            f"Index file: {results['index_file']}"
        ))


class CheckDependenciesCommand(BaseCommand):
    """
    Django management command to check dependencies
    """
    
    help = 'Check project dependencies'
    
    def add_arguments(self, parser):
        """
        Add command arguments
        
        Args:
            parser: The argument parser
        """
        parser.add_argument(
            '--update',
            action='store_true',
            help='Update outdated dependencies',
        )
        parser.add_argument(
            '--check-security',
            action='store_true',
            help='Check for security vulnerabilities',
        )
        parser.add_argument(
            '--report',
            action='store_true',
            help='Generate report',
        )
        parser.add_argument(
            '--output',
            help='Output file for report',
        )
    
    def handle(self, *args, **options):
        """
        Command handler
        
        Args:
            *args: Command arguments
            **options: Command options
        """
        from code_quality.dependency_manager import DependencyManager
        
        # Get project root
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Create dependency manager
        manager = DependencyManager(project_root)
        
        if options['update']:
            # Update dependencies
            results = manager.update_dependencies()
            
            self.stdout.write(self.style.SUCCESS(
                f"Updated {results['summary']['updated']} of {results['summary']['total']} dependencies"
            ))
        else:
            # Check dependencies
            results = manager.check_dependencies(check_security=options['check_security'])
            
            self.stdout.write(self.style.SUCCESS(
                f"Found {results['summary']['outdated']} outdated and {results['summary']['vulnerable']} vulnerable dependencies "
                f"out of {results['summary']['total']} dependencies"
            ))
        
        # Generate report if requested
        if options['report']:
            import json
            
            output_file = options['output'] or 'dependency_report.json'
            
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2)
            
            self.stdout.write(self.style.SUCCESS(
                f"Report generated: {output_file}"
            ))


class RunTestsCommand(BaseCommand):
    """
    Django management command to run tests
    """
    
    help = 'Run tests for the project'
    
    def add_arguments(self, parser):
        """
        Add command arguments
        
        Args:
            parser: The argument parser
        """
        parser.add_argument(
            '--module',
            help='Module to test',
        )
        parser.add_argument(
            '--report',
            action='store_true',
            help='Generate report',
        )
        parser.add_argument(
            '--format',
            choices=['text', 'html', 'json'],
            default='html',
            help='Report format',
        )
        parser.add_argument(
            '--output',
            help='Output file for report',
        )
    
    def handle(self, *args, **options):
        """
        Command handler
        
        Args:
            *args: Command arguments
            **options: Command options
        """
        from code_quality.unit_testing import TestRunner
        
        # Get project root
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Create test runner
        runner = TestRunner(project_root=project_root)
        
        # Discover tests
        discovery_results = runner.discover_tests()
        
        if discovery_results['status'] != 'success':
            self.stdout.write(self.style.ERROR(
                f"Error discovering tests: {discovery_results.get('message', 'Unknown error')}"
            ))
            return
        
        self.stdout.write(self.style.SUCCESS(
            f"Discovered {discovery_results['total_tests']} tests in {len(discovery_results['test_suites'])} test suites"
        ))
        
        # Run tests
        if options['module']:
            results = runner.run_tests(options['module'])
        else:
            results = runner.run_all_tests()
        
        if results['status'] != 'success':
            self.stdout.write(self.style.ERROR(
                f"Error running tests: {results.get('message', 'Unknown error')}"
            ))
            return
        
        self.stdout.write(self.style.SUCCESS(
            f"Test results: {results['summary']['passed']} passed, {results['summary']['failed']} failed, "
            f"{results['summary']['total'] - results['summary']['passed'] - results['summary']['failed']} skipped"
        ))
        
        # Generate report if requested
        if options['report']:
            report_file = runner.generate_test_report(results, format=options['format'])
            
            if report_file:
                self.stdout.write(self.style.SUCCESS(
                    f"Report generated: {report_file}"
                ))
            else:
                self.stdout.write(self.style.ERROR(
                    "Error generating report"
                ))
