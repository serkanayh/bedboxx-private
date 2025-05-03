"""
Code Style and Documentation Module for StopSale Automation System

This module provides tools for enforcing code style standards, generating documentation,
and improving overall code quality.
"""

import os
import sys
import re
import ast
import logging
import subprocess
import importlib
import inspect
from typing import Dict, List, Any, Optional, Union, Set, Tuple, Callable
from datetime import datetime

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class CodeStyleChecker:
    """Class for checking and enforcing code style standards"""
    
    def __init__(self, project_root: str, config_file: Optional[str] = None):
        """
        Initialize the code style checker
        
        Args:
            project_root: Root directory of the project
            config_file: Path to configuration file (relative to project_root)
        """
        self.project_root = os.path.abspath(project_root)
        
        if config_file is None:
            self.config_file = os.path.join(self.project_root, "setup.cfg")
        else:
            self.config_file = os.path.join(self.project_root, config_file)
        
        # Default configuration
        self.config = {
            "max_line_length": 100,
            "indent_size": 4,
            "docstring_style": "google",
            "ignore_patterns": [
                "*/venv/*",
                "*/.git/*",
                "*/migrations/*",
                "*/__pycache__/*"
            ]
        }
        
        # Load configuration if exists
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from file"""
        if not os.path.exists(self.config_file):
            logger.warning(f"Configuration file not found: {self.config_file}")
            return
        
        try:
            import configparser
            
            config = configparser.ConfigParser()
            config.read(self.config_file)
            
            if "code_style" in config:
                section = config["code_style"]
                
                if "max_line_length" in section:
                    self.config["max_line_length"] = section.getint("max_line_length")
                
                if "indent_size" in section:
                    self.config["indent_size"] = section.getint("indent_size")
                
                if "docstring_style" in section:
                    self.config["docstring_style"] = section.get("docstring_style")
                
                if "ignore_patterns" in section:
                    patterns = section.get("ignore_patterns")
                    self.config["ignore_patterns"] = [p.strip() for p in patterns.split(",")]
        
        except Exception as e:
            logger.error(f"Error loading configuration: {str(e)}")
    
    def _should_ignore(self, file_path: str) -> bool:
        """
        Check if a file should be ignored
        
        Args:
            file_path: Path to the file
            
        Returns:
            bool: True if the file should be ignored, False otherwise
        """
        import fnmatch
        
        # Get relative path
        rel_path = os.path.relpath(file_path, self.project_root)
        
        # Check ignore patterns
        for pattern in self.config["ignore_patterns"]:
            if fnmatch.fnmatch(rel_path, pattern):
                return True
        
        return False
    
    def check_file(self, file_path: str) -> Dict[str, Any]:
        """
        Check a file for code style issues
        
        Args:
            file_path: Path to the file
            
        Returns:
            dict: Check results
        """
        if not os.path.exists(file_path):
            return {
                "file": file_path,
                "errors": [{"line": 0, "message": "File not found"}],
                "warnings": [],
                "info": []
            }
        
        if self._should_ignore(file_path):
            return {
                "file": file_path,
                "errors": [],
                "warnings": [],
                "info": [{"line": 0, "message": "File ignored"}]
            }
        
        # Check file extension
        _, ext = os.path.splitext(file_path)
        
        if ext.lower() != ".py":
            return {
                "file": file_path,
                "errors": [],
                "warnings": [],
                "info": [{"line": 0, "message": "Not a Python file"}]
            }
        
        # Initialize results
        results = {
            "file": file_path,
            "errors": [],
            "warnings": [],
            "info": []
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check line length
            self._check_line_length(content, results)
            
            # Check indentation
            self._check_indentation(content, results)
            
            # Check docstrings
            self._check_docstrings(content, results)
            
            # Check imports
            self._check_imports(content, results)
            
            # Check naming conventions
            self._check_naming_conventions(content, results)
            
            return results
        
        except Exception as e:
            logger.error(f"Error checking file {file_path}: {str(e)}")
            results["errors"].append({"line": 0, "message": f"Error checking file: {str(e)}"})
            return results
    
    def _check_line_length(self, content: str, results: Dict[str, Any]) -> None:
        """
        Check line length
        
        Args:
            content: File content
            results: Results dictionary to update
        """
        max_length = self.config["max_line_length"]
        
        for i, line in enumerate(content.split('\n'), 1):
            if len(line) > max_length:
                results["warnings"].append({
                    "line": i,
                    "message": f"Line too long ({len(line)} > {max_length})"
                })
    
    def _check_indentation(self, content: str, results: Dict[str, Any]) -> None:
        """
        Check indentation
        
        Args:
            content: File content
            results: Results dictionary to update
        """
        indent_size = self.config["indent_size"]
        
        for i, line in enumerate(content.split('\n'), 1):
            # Skip empty lines
            if not line.strip():
                continue
            
            # Check if indentation is a multiple of indent_size
            indent = len(line) - len(line.lstrip())
            if indent % indent_size != 0:
                results["errors"].append({
                    "line": i,
                    "message": f"Indentation is not a multiple of {indent_size}"
                })
    
    def _check_docstrings(self, content: str, results: Dict[str, Any]) -> None:
        """
        Check docstrings
        
        Args:
            content: File content
            results: Results dictionary to update
        """
        try:
            tree = ast.parse(content)
            
            # Check module docstring
            if (not tree.body or not isinstance(tree.body[0], ast.Expr) or
                    not isinstance(tree.body[0].value, ast.Str)):
                results["warnings"].append({
                    "line": 1,
                    "message": "Missing module docstring"
                })
            
            # Check class and function docstrings
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                    # Skip special methods
                    if isinstance(node, ast.FunctionDef) and node.name.startswith('__') and node.name.endswith('__'):
                        continue
                    
                    # Check if docstring exists
                    if (not node.body or not isinstance(node.body[0], ast.Expr) or
                            not isinstance(node.body[0].value, ast.Str)):
                        results["warnings"].append({
                            "line": node.lineno,
                            "message": f"Missing docstring in {node.__class__.__name__.lower()} {node.name}"
                        })
                    else:
                        # Check docstring style
                        docstring = ast.get_docstring(node)
                        if docstring:
                            self._check_docstring_style(docstring, node.lineno, results)
        
        except Exception as e:
            logger.error(f"Error checking docstrings: {str(e)}")
            results["errors"].append({"line": 0, "message": f"Error checking docstrings: {str(e)}"})
    
    def _check_docstring_style(self, docstring: str, line: int, results: Dict[str, Any]) -> None:
        """
        Check docstring style
        
        Args:
            docstring: Docstring to check
            line: Line number
            results: Results dictionary to update
        """
        style = self.config["docstring_style"].lower()
        
        if style == "google":
            # Check for Google style docstring
            if "Args:" not in docstring and "Returns:" not in docstring and "Raises:" not in docstring:
                results["warnings"].append({
                    "line": line,
                    "message": "Docstring does not follow Google style"
                })
        
        elif style == "numpy":
            # Check for NumPy style docstring
            if "Parameters" not in docstring and "Returns" not in docstring and "Raises" not in docstring:
                results["warnings"].append({
                    "line": line,
                    "message": "Docstring does not follow NumPy style"
                })
        
        elif style == "sphinx":
            # Check for Sphinx style docstring
            if ":param" not in docstring and ":return:" not in docstring and ":raises:" not in docstring:
                results["warnings"].append({
                    "line": line,
                    "message": "Docstring does not follow Sphinx style"
                })
    
    def _check_imports(self, content: str, results: Dict[str, Any]) -> None:
        """
        Check imports
        
        Args:
            content: File content
            results: Results dictionary to update
        """
        try:
            tree = ast.parse(content)
            
            # Check import order
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    imports.append((node.lineno, node))
            
            # Sort imports by type and name
            sorted_imports = sorted(imports, key=lambda x: (
                isinstance(x[1], ast.ImportFrom),  # Import before ImportFrom
                getattr(x[1], 'module', ''),       # Module name for ImportFrom
                [n.name for n in x[1].names][0]    # First imported name
            ))
            
            # Check if imports are in order
            for i in range(len(imports) - 1):
                if imports[i][0] > imports[i+1][0]:
                    results["warnings"].append({
                        "line": imports[i+1][0],
                        "message": "Imports are not in order"
                    })
                    break
            
            # Check for unused imports
            imported_names = set()
            for _, node in imports:
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported_names.add(alias.asname or alias.name)
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        imported_names.add(alias.asname or alias.name)
            
            # Find used names
            used_names = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                    used_names.add(node.id)
                elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
                    if isinstance(node.value, ast.Name):
                        used_names.add(node.value.id)
            
            # Check for unused imports
            for name in imported_names:
                if name not in used_names and name != '*':
                    results["warnings"].append({
                        "line": 0,
                        "message": f"Unused import: {name}"
                    })
        
        except Exception as e:
            logger.error(f"Error checking imports: {str(e)}")
            results["errors"].append({"line": 0, "message": f"Error checking imports: {str(e)}"})
    
    def _check_naming_conventions(self, content: str, results: Dict[str, Any]) -> None:
        """
        Check naming conventions
        
        Args:
            content: File content
            results: Results dictionary to update
        """
        try:
            tree = ast.parse(content)
            
            # Check class names (CamelCase)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    if not re.match(r'^[A-Z][a-zA-Z0-9]*$', node.name):
                        results["warnings"].append({
                            "line": node.lineno,
                            "message": f"Class name '{node.name}' does not follow CamelCase convention"
                        })
            
            # Check function and method names (snake_case)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Skip special methods
                    if node.name.startswith('__') and node.name.endswith('__'):
                        continue
                    
                    if not re.match(r'^[a-z][a-z0-9_]*$', node.name):
                        results["warnings"].append({
                            "line": node.lineno,
                            "message": f"Function/method name '{node.name}' does not follow snake_case convention"
                        })
            
            # Check variable names (snake_case)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            # Skip constants
                            if target.id.isupper():
                                continue
                            
                            if not re.match(r'^[a-z][a-z0-9_]*$', target.id):
                                results["warnings"].append({
                                    "line": node.lineno,
                                    "message": f"Variable name '{target.id}' does not follow snake_case convention"
                                })
        
        except Exception as e:
            logger.error(f"Error checking naming conventions: {str(e)}")
            results["errors"].append({"line": 0, "message": f"Error checking naming conventions: {str(e)}"})
    
    def check_project(self) -> Dict[str, Any]:
        """
        Check all Python files in the project
        
        Returns:
            dict: Check results
        """
        results = {
            "files": [],
            "summary": {
                "total_files": 0,
                "files_with_errors": 0,
                "files_with_warnings": 0,
                "total_errors": 0,
                "total_warnings": 0
            }
        }
        
        # Walk through project files
        for root, dirs, files in os.walk(self.project_root):
            # Skip ignored directories
            dirs[:] = [d for d in dirs if not self._should_ignore(os.path.join(root, d))]
            
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    
                    # Skip ignored files
                    if self._should_ignore(file_path):
                        continue
                    
                    # Check file
                    file_results = self.check_file(file_path)
                    results["files"].append(file_results)
                    
                    # Update summary
                    results["summary"]["total_files"] += 1
                    results["summary"]["total_errors"] += len(file_results["errors"])
                    results["summary"]["total_warnings"] += len(file_results["warnings"])
                    
                    if file_results["errors"]:
                        results["summary"]["files_with_errors"] += 1
                    
                    if file_results["warnings"]:
                        results["summary"]["files_with_warnings"] += 1
        
        return results
    
    def fix_file(self, file_path: str) -> Dict[str, Any]:
        """
        Fix code style issues in a file
        
        Args:
            file_path: Path to the file
            
        Returns:
            dict: Fix results
        """
        if not os.path.exists(file_path):
            return {
                "file": file_path,
                "success": False,
                "message": "File not found"
            }
        
        if self._should_ignore(file_path):
            return {
                "file": file_path,
                "success": True,
                "message": "File ignored"
            }
        
        # Check file extension
        _, ext = os.path.splitext(file_path)
        
        if ext.lower() != ".py":
            return {
                "file": file_path,
                "success": True,
                "message": "Not a Python file"
            }
        
        try:
            # Try to use autopep8 if available
            try:
                import autopep8
                has_autopep8 = True
            except ImportError:
                has_autopep8 = False
                logger.warning("autopep8 not installed, falling back to basic fixes")
            
            if has_autopep8:
                # Use autopep8 to fix the file
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                fixed_content = autopep8.fix_code(
                    content,
                    options={
                        'max_line_length': self.config["max_line_length"],
                        'indent_size': self.config["indent_size"]
                    }
                )
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(fixed_content)
                
                return {
                    "file": file_path,
                    "success": True,
                    "message": "Fixed with autopep8"
                }
            else:
                # Basic fixes
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                # Fix trailing whitespace
                fixed_lines = [line.rstrip() + '\n' for line in lines]
                
                # Ensure file ends with a newline
                if fixed_lines and not fixed_lines[-1].endswith('\n'):
                    fixed_lines[-1] += '\n'
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.writelines(fixed_lines)
                
                return {
                    "file": file_path,
                    "success": True,
                    "message": "Basic fixes applied"
                }
        
        except Exception as e:
            logger.error(f"Error fixing file {file_path}: {str(e)}")
            return {
                "file": file_path,
                "success": False,
                "message": f"Error: {str(e)}"
            }
    
    def fix_project(self) -> Dict[str, Any]:
        """
        Fix code style issues in all Python files in the project
        
        Returns:
            dict: Fix results
        """
        results = {
            "files": [],
            "summary": {
                "total_files": 0,
                "fixed_files": 0,
                "failed_files": 0
            }
        }
        
        # Walk through project files
        for root, dirs, files in os.walk(self.project_root):
            # Skip ignored directories
            dirs[:] = [d for d in dirs if not self._should_ignore(os.path.join(root, d))]
            
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    
                    # Skip ignored files
                    if self._should_ignore(file_path):
                        continue
                    
                    # Fix file
                    file_results = self.fix_file(file_path)
                    results["files"].append(file_results)
                    
                    # Update summary
                    results["summary"]["total_files"] += 1
                    
                    if file_results["success"]:
                        results["summary"]["fixed_files"] += 1
                    else:
                        results["summary"]["failed_files"] += 1
        
        return results
    
    def generate_config_file(self) -> bool:
        """
        Generate a configuration file
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            import configparser
            
            config = configparser.ConfigParser()
            
            # Add code style section
            config["code_style"] = {
                "max_line_length": str(self.config["max_line_length"]),
                "indent_size": str(self.config["indent_size"]),
                "docstring_style": self.config["docstring_style"],
                "ignore_patterns": ",".join(self.config["ignore_patterns"])
            }
            
            # Add flake8 section
            config["flake8"] = {
                "max-line-length": str(self.config["max_line_length"]),
                "exclude": ",".join(self.config["ignore_patterns"])
            }
            
            # Add isort section
            config["isort"] = {
                "line_length": str(self.config["max_line_length"]),
                "multi_line_output": "3",
                "include_trailing_comma": "True",
                "force_grid_wrap": "0",
                "use_parentheses": "True"
            }
            
            # Write to file
            with open(self.config_file, 'w') as f:
                config.write(f)
            
            logger.info(f"Configuration file generated: {self.config_file}")
            return True
        
        except Exception as e:
            logger.error(f"Error generating configuration file: {str(e)}")
            return False


class DocumentationGenerator:
    """Class for generating documentation"""
    
    def __init__(self, project_root: str, output_dir: Optional[str] = None):
        """
        Initialize the documentation generator
        
        Args:
            project_root: Root directory of the project
            output_dir: Directory to store generated documentation (if None, uses project_root/docs)
        """
        self.project_root = os.path.abspath(project_root)
        
        if output_dir is None:
            self.output_dir = os.path.join(self.project_root, "docs")
        else:
            self.output_dir = os.path.abspath(output_dir)
        
        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
    
    def generate_module_documentation(self, module_path: str) -> Dict[str, Any]:
        """
        Generate documentation for a module
        
        Args:
            module_path: Path to the module
            
        Returns:
            dict: Documentation data
        """
        if not os.path.exists(module_path):
            return {
                "module": module_path,
                "success": False,
                "message": "Module not found"
            }
        
        # Check if it's a Python file
        _, ext = os.path.splitext(module_path)
        
        if ext.lower() != ".py":
            return {
                "module": module_path,
                "success": False,
                "message": "Not a Python file"
            }
        
        try:
            # Get module name
            rel_path = os.path.relpath(module_path, self.project_root)
            module_name = os.path.splitext(rel_path)[0].replace(os.path.sep, '.')
            
            # Parse the module
            with open(module_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            # Get module docstring
            module_doc = ast.get_docstring(tree) or "No module documentation"
            
            # Get classes
            classes = []
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    class_doc = ast.get_docstring(node) or "No class documentation"
                    
                    # Get methods
                    methods = []
                    for method_node in node.body:
                        if isinstance(method_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            method_doc = ast.get_docstring(method_node) or "No method documentation"
                            
                            # Get parameters
                            params = []
                            for param in method_node.args.args:
                                if param.arg != 'self':
                                    params.append(param.arg)
                            
                            methods.append({
                                "name": method_node.name,
                                "docstring": method_doc,
                                "parameters": params,
                                "is_async": isinstance(method_node, ast.AsyncFunctionDef)
                            })
                    
                    classes.append({
                        "name": node.name,
                        "docstring": class_doc,
                        "methods": methods
                    })
            
            # Get functions
            functions = []
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    func_doc = ast.get_docstring(node) or "No function documentation"
                    
                    # Get parameters
                    params = []
                    for param in node.args.args:
                        params.append(param.arg)
                    
                    functions.append({
                        "name": node.name,
                        "docstring": func_doc,
                        "parameters": params,
                        "is_async": isinstance(node, ast.AsyncFunctionDef)
                    })
            
            return {
                "module": module_path,
                "name": module_name,
                "docstring": module_doc,
                "classes": classes,
                "functions": functions,
                "success": True
            }
        
        except Exception as e:
            logger.error(f"Error generating documentation for {module_path}: {str(e)}")
            return {
                "module": module_path,
                "success": False,
                "message": f"Error: {str(e)}"
            }
    
    def generate_markdown_documentation(self, module_data: Dict[str, Any], output_file: Optional[str] = None) -> str:
        """
        Generate Markdown documentation for a module
        
        Args:
            module_data: Module documentation data
            output_file: Path to output file (if None, generates based on module name)
            
        Returns:
            str: Path to generated file
        """
        if not module_data.get("success", False):
            logger.error(f"Cannot generate documentation for {module_data.get('module')}: {module_data.get('message')}")
            return ""
        
        # Determine output file
        if output_file is None:
            module_name = module_data["name"].split('.')[-1]
            output_file = os.path.join(self.output_dir, f"{module_name}.md")
        
        try:
            # Generate Markdown
            md = f"# {module_data['name']}\n\n"
            
            # Module docstring
            md += f"{module_data['docstring']}\n\n"
            
            # Classes
            if module_data["classes"]:
                md += "## Classes\n\n"
                
                for cls in module_data["classes"]:
                    md += f"### {cls['name']}\n\n"
                    md += f"{cls['docstring']}\n\n"
                    
                    # Methods
                    if cls["methods"]:
                        for method in cls["methods"]:
                            # Method signature
                            params_str = ", ".join(["self"] + method["parameters"])
                            
                            if method["is_async"]:
                                md += f"#### async {method['name']}({params_str})\n\n"
                            else:
                                md += f"#### {method['name']}({params_str})\n\n"
                            
                            md += f"{method['docstring']}\n\n"
            
            # Functions
            if module_data["functions"]:
                md += "## Functions\n\n"
                
                for func in module_data["functions"]:
                    # Function signature
                    params_str = ", ".join(func["parameters"])
                    
                    if func["is_async"]:
                        md += f"### async {func['name']}({params_str})\n\n"
                    else:
                        md += f"### {func['name']}({params_str})\n\n"
                    
                    md += f"{func['docstring']}\n\n"
            
            # Write to file
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(md)
            
            logger.info(f"Markdown documentation generated: {output_file}")
            return output_file
        
        except Exception as e:
            logger.error(f"Error generating Markdown documentation: {str(e)}")
            return ""
    
    def generate_html_documentation(self, module_data: Dict[str, Any], output_file: Optional[str] = None) -> str:
        """
        Generate HTML documentation for a module
        
        Args:
            module_data: Module documentation data
            output_file: Path to output file (if None, generates based on module name)
            
        Returns:
            str: Path to generated file
        """
        if not module_data.get("success", False):
            logger.error(f"Cannot generate documentation for {module_data.get('module')}: {module_data.get('message')}")
            return ""
        
        # Determine output file
        if output_file is None:
            module_name = module_data["name"].split('.')[-1]
            output_file = os.path.join(self.output_dir, f"{module_name}.html")
        
        try:
            # Generate HTML
            html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{module_data['name']} - Documentation</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            color: #333;
        }}
        h1, h2, h3, h4 {{
            color: #2c3e50;
        }}
        pre {{
            background-color: #f8f9fa;
            padding: 10px;
            border-radius: 5px;
            overflow-x: auto;
        }}
        .method {{
            margin-left: 20px;
            margin-bottom: 20px;
        }}
        .function {{
            margin-bottom: 20px;
        }}
        .docstring {{
            white-space: pre-wrap;
        }}
    </style>
</head>
<body>
    <h1>{module_data['name']}</h1>
    
    <div class="docstring">{module_data['docstring']}</div>
"""
            
            # Classes
            if module_data["classes"]:
                html += """
    <h2>Classes</h2>
"""
                
                for cls in module_data["classes"]:
                    html += f"""
    <h3>{cls['name']}</h3>
    
    <div class="docstring">{cls['docstring']}</div>
"""
                    
                    # Methods
                    if cls["methods"]:
                        for method in cls["methods"]:
                            # Method signature
                            params_str = ", ".join(["self"] + method["parameters"])
                            
                            if method["is_async"]:
                                html += f"""
    <div class="method">
        <h4>async {method['name']}({params_str})</h4>
        
        <div class="docstring">{method['docstring']}</div>
    </div>
"""
                            else:
                                html += f"""
    <div class="method">
        <h4>{method['name']}({params_str})</h4>
        
        <div class="docstring">{method['docstring']}</div>
    </div>
"""
            
            # Functions
            if module_data["functions"]:
                html += """
    <h2>Functions</h2>
"""
                
                for func in module_data["functions"]:
                    # Function signature
                    params_str = ", ".join(func["parameters"])
                    
                    if func["is_async"]:
                        html += f"""
    <div class="function">
        <h3>async {func['name']}({params_str})</h3>
        
        <div class="docstring">{func['docstring']}</div>
    </div>
"""
                    else:
                        html += f"""
    <div class="function">
        <h3>{func['name']}({params_str})</h3>
        
        <div class="docstring">{func['docstring']}</div>
    </div>
"""
            
            html += """
</body>
</html>
"""
            
            # Write to file
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html)
            
            logger.info(f"HTML documentation generated: {output_file}")
            return output_file
        
        except Exception as e:
            logger.error(f"Error generating HTML documentation: {str(e)}")
            return ""
    
    def generate_project_documentation(self, format: str = "markdown") -> Dict[str, Any]:
        """
        Generate documentation for all Python files in the project
        
        Args:
            format: Documentation format ('markdown' or 'html')
            
        Returns:
            dict: Documentation results
        """
        results = {
            "modules": [],
            "index_file": "",
            "summary": {
                "total_modules": 0,
                "successful_modules": 0,
                "failed_modules": 0
            }
        }
        
        # Find all Python files
        python_files = []
        for root, dirs, files in os.walk(self.project_root):
            # Skip common directories to ignore
            if any(ignore_dir in root for ignore_dir in ['/venv/', '/.git/', '/__pycache__/']):
                continue
            
            for file in files:
                if file.endswith('.py'):
                    python_files.append(os.path.join(root, file))
        
        # Generate documentation for each module
        for file_path in python_files:
            module_data = self.generate_module_documentation(file_path)
            
            if module_data["success"]:
                # Generate documentation file
                if format.lower() == "html":
                    output_file = self.generate_html_documentation(module_data)
                else:
                    output_file = self.generate_markdown_documentation(module_data)
                
                module_data["output_file"] = output_file
                results["modules"].append(module_data)
                
                results["summary"]["total_modules"] += 1
                results["summary"]["successful_modules"] += 1
            else:
                results["modules"].append(module_data)
                
                results["summary"]["total_modules"] += 1
                results["summary"]["failed_modules"] += 1
        
        # Generate index file
        if format.lower() == "html":
            index_file = self._generate_html_index(results["modules"])
        else:
            index_file = self._generate_markdown_index(results["modules"])
        
        results["index_file"] = index_file
        
        return results
    
    def _generate_markdown_index(self, modules: List[Dict[str, Any]]) -> str:
        """
        Generate Markdown index file
        
        Args:
            modules: List of module documentation data
            
        Returns:
            str: Path to generated file
        """
        output_file = os.path.join(self.output_dir, "index.md")
        
        try:
            # Generate Markdown
            md = "# Project Documentation\n\n"
            
            # Add generation timestamp
            md += f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            # Add module list
            md += "## Modules\n\n"
            
            # Group modules by package
            packages = {}
            for module in modules:
                if not module.get("success", False):
                    continue
                
                # Get package name
                module_name = module["name"]
                parts = module_name.split('.')
                
                if len(parts) > 1:
                    package = '.'.join(parts[:-1])
                    module_short_name = parts[-1]
                else:
                    package = "root"
                    module_short_name = module_name
                
                if package not in packages:
                    packages[package] = []
                
                # Get relative path to module documentation
                output_file_rel = os.path.relpath(
                    module.get("output_file", ""),
                    self.output_dir
                )
                
                packages[package].append({
                    "name": module_short_name,
                    "full_name": module_name,
                    "link": output_file_rel
                })
            
            # Add packages and modules
            for package_name in sorted(packages.keys()):
                if package_name == "root":
                    md += "### Root Modules\n\n"
                else:
                    md += f"### {package_name}\n\n"
                
                for module in sorted(packages[package_name], key=lambda m: m["name"]):
                    md += f"- [{module['name']}]({module['link']}) - {module['full_name']}\n"
                
                md += "\n"
            
            # Write to file
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(md)
            
            logger.info(f"Markdown index generated: {output_file}")
            return output_file
        
        except Exception as e:
            logger.error(f"Error generating Markdown index: {str(e)}")
            return ""
    
    def _generate_html_index(self, modules: List[Dict[str, Any]]) -> str:
        """
        Generate HTML index file
        
        Args:
            modules: List of module documentation data
            
        Returns:
            str: Path to generated file
        """
        output_file = os.path.join(self.output_dir, "index.html")
        
        try:
            # Generate HTML
            html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Project Documentation</title>
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
        ul {
            list-style-type: none;
            padding-left: 20px;
        }
        li {
            margin-bottom: 5px;
        }
        a {
            color: #3498db;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
        .package {
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <h1>Project Documentation</h1>
    
    <p>Generated on """
            
            # Add generation timestamp
            html += f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>"
            
            # Add module list
            html += """
    <h2>Modules</h2>
"""
            
            # Group modules by package
            packages = {}
            for module in modules:
                if not module.get("success", False):
                    continue
                
                # Get package name
                module_name = module["name"]
                parts = module_name.split('.')
                
                if len(parts) > 1:
                    package = '.'.join(parts[:-1])
                    module_short_name = parts[-1]
                else:
                    package = "root"
                    module_short_name = module_name
                
                if package not in packages:
                    packages[package] = []
                
                # Get relative path to module documentation
                output_file_rel = os.path.relpath(
                    module.get("output_file", ""),
                    self.output_dir
                )
                
                packages[package].append({
                    "name": module_short_name,
                    "full_name": module_name,
                    "link": output_file_rel
                })
            
            # Add packages and modules
            for package_name in sorted(packages.keys()):
                if package_name == "root":
                    html += """
    <div class="package">
        <h3>Root Modules</h3>
        <ul>
"""
                else:
                    html += f"""
    <div class="package">
        <h3>{package_name}</h3>
        <ul>
"""
                
                for module in sorted(packages[package_name], key=lambda m: m["name"]):
                    html += f"""
            <li><a href="{module['link']}">{module['name']}</a> - {module['full_name']}</li>
"""
                
                html += """
        </ul>
    </div>
"""
            
            html += """
</body>
</html>
"""
            
            # Write to file
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html)
            
            logger.info(f"HTML index generated: {output_file}")
            return output_file
        
        except Exception as e:
            logger.error(f"Error generating HTML index: {str(e)}")
            return ""


def setup_django_code_quality():
    """
    Set up Django code quality tools
    
    Returns:
        str: Setup instructions
    """
    instructions = """
    # Add the following to your Django project:
    
    # 1. Create a management command for code style checking:
    # management/commands/check_code_style.py
    
    from django.core.management.base import BaseCommand
    from django.conf import settings
    import os
    
    class Command(BaseCommand):
        help = 'Check code style'
        
        def add_arguments(self, parser):
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
            from code_style_and_documentation import CodeStyleChecker
            
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
    
    
    # 2. Create a management command for documentation generation:
    # management/commands/generate_docs.py
    
    from django.core.management.base import BaseCommand
    from django.conf import settings
    import os
    
    class Command(BaseCommand):
        help = 'Generate documentation'
        
        def add_arguments(self, parser):
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
            from code_style_and_documentation import DocumentationGenerator
            
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
    """
    return instructions


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    print("Code Style and Documentation Module")
    print("----------------------------------")
    print("This module provides tools for enforcing code style standards and generating documentation.")
    
    # Get project root
    project_root = input("Enter project root directory (default: current directory): ")
    if not project_root:
        project_root = os.getcwd()
    
    # Ask what to do
    print("\nWhat would you like to do?")
    print("1. Check code style")
    print("2. Fix code style issues")
    print("3. Generate documentation")
    print("4. Generate configuration file")
    
    choice = input("Enter your choice (1-4): ")
    
    if choice == "1":
        # Check code style
        checker = CodeStyleChecker(project_root)
        results = checker.check_project()
        
        print(f"\nFound {results['summary']['total_errors']} errors and {results['summary']['total_warnings']} warnings "
              f"in {results['summary']['total_files']} files")
        
        # Ask to show details
        show_details = input("\nShow details? (y/n): ")
        if show_details.lower() == 'y':
            for file_result in results["files"]:
                if file_result["errors"] or file_result["warnings"]:
                    print(f"\n{file_result['file']}:")
                    
                    for error in file_result["errors"]:
                        print(f"  Line {error['line']}: {error['message']}")
                    
                    for warning in file_result["warnings"]:
                        print(f"  Line {warning['line']}: {warning['message']}")
    
    elif choice == "2":
        # Fix code style issues
        checker = CodeStyleChecker(project_root)
        results = checker.fix_project()
        
        print(f"\nFixed {results['summary']['fixed_files']} of {results['summary']['total_files']} files")
    
    elif choice == "3":
        # Generate documentation
        generator = DocumentationGenerator(project_root)
        
        # Ask for format
        format_choice = input("\nDocumentation format (markdown/html): ")
        format = "html" if format_choice.lower() in ('html', 'h') else "markdown"
        
        results = generator.generate_project_documentation(format=format)
        
        print(f"\nGenerated documentation for {results['summary']['successful_modules']} of {results['summary']['total_modules']} modules")
        print(f"Index file: {results['index_file']}")
    
    elif choice == "4":
        # Generate configuration file
        checker = CodeStyleChecker(project_root)
        success = checker.generate_config_file()
        
        if success:
            print(f"\nConfiguration file generated: {checker.config_file}")
        else:
            print("\nFailed to generate configuration file")
    
    else:
        print("\nInvalid choice")
    
    # Django integration
    print("\nDjango integration:")
    print(setup_django_code_quality())
