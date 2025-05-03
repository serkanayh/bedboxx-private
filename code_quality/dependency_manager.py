"""
Dependency Management Module for StopSale Automation System

This module provides tools for managing project dependencies, ensuring consistent
environments, and tracking dependency versions.
"""

import os
import sys
import json
import logging
import subprocess
import pkg_resources
from typing import Dict, List, Any, Optional, Union, Set, Tuple
from datetime import datetime

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class DependencyManager:
    """Class for managing project dependencies"""
    
    def __init__(self, project_root: str, requirements_file: Optional[str] = None):
        """
        Initialize the dependency manager
        
        Args:
            project_root: Root directory of the project
            requirements_file: Path to requirements.txt file (relative to project_root)
        """
        self.project_root = os.path.abspath(project_root)
        
        if requirements_file is None:
            self.requirements_file = os.path.join(self.project_root, "requirements.txt")
        else:
            self.requirements_file = os.path.join(self.project_root, requirements_file)
        
        # Initialize dependency tracking
        self.installed_packages = self._get_installed_packages()
        self.required_packages = self._parse_requirements_file()
    
    def _get_installed_packages(self) -> Dict[str, str]:
        """
        Get installed packages and versions
        
        Returns:
            dict: Dictionary of package names and versions
        """
        installed = {}
        
        try:
            for package in pkg_resources.working_set:
                installed[package.key] = package.version
        except Exception as e:
            logger.error(f"Error getting installed packages: {str(e)}")
        
        return installed
    
    def _parse_requirements_file(self) -> Dict[str, str]:
        """
        Parse requirements.txt file
        
        Returns:
            dict: Dictionary of package names and version constraints
        """
        required = {}
        
        if not os.path.exists(self.requirements_file):
            logger.warning(f"Requirements file not found: {self.requirements_file}")
            return required
        
        try:
            with open(self.requirements_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                    
                    # Handle options like --index-url
                    if line.startswith('-'):
                        continue
                    
                    # Handle requirements with version specifiers
                    if '==' in line:
                        name, version = line.split('==', 1)
                        required[name.strip()] = f"=={version.strip()}"
                    elif '>=' in line:
                        name, version = line.split('>=', 1)
                        required[name.strip()] = f">={version.strip()}"
                    elif '<=' in line:
                        name, version = line.split('<=', 1)
                        required[name.strip()] = f"<={version.strip()}"
                    elif '~=' in line:
                        name, version = line.split('~=', 1)
                        required[name.strip()] = f"~={version.strip()}"
                    else:
                        # No version specified
                        required[line.strip()] = ""
        
        except Exception as e:
            logger.error(f"Error parsing requirements file: {str(e)}")
        
        return required
    
    def check_dependencies(self) -> Dict[str, Any]:
        """
        Check if installed packages match requirements
        
        Returns:
            dict: Dependency check results
        """
        results = {
            "missing": [],
            "outdated": [],
            "compatible": [],
            "unknown": []
        }
        
        for package, constraint in self.required_packages.items():
            if package not in self.installed_packages:
                results["missing"].append({
                    "name": package,
                    "constraint": constraint,
                    "installed": None
                })
                continue
            
            installed_version = self.installed_packages[package]
            
            if not constraint:
                # No version constraint, any version is fine
                results["compatible"].append({
                    "name": package,
                    "constraint": "any",
                    "installed": installed_version
                })
                continue
            
            # Check version constraints
            if constraint.startswith("=="):
                required_version = constraint[2:].strip()
                if installed_version == required_version:
                    results["compatible"].append({
                        "name": package,
                        "constraint": constraint,
                        "installed": installed_version
                    })
                else:
                    results["outdated"].append({
                        "name": package,
                        "constraint": constraint,
                        "installed": installed_version
                    })
            
            elif constraint.startswith(">="):
                required_version = constraint[2:].strip()
                try:
                    if pkg_resources.parse_version(installed_version) >= pkg_resources.parse_version(required_version):
                        results["compatible"].append({
                            "name": package,
                            "constraint": constraint,
                            "installed": installed_version
                        })
                    else:
                        results["outdated"].append({
                            "name": package,
                            "constraint": constraint,
                            "installed": installed_version
                        })
                except:
                    results["unknown"].append({
                        "name": package,
                        "constraint": constraint,
                        "installed": installed_version
                    })
            
            elif constraint.startswith("<="):
                required_version = constraint[2:].strip()
                try:
                    if pkg_resources.parse_version(installed_version) <= pkg_resources.parse_version(required_version):
                        results["compatible"].append({
                            "name": package,
                            "constraint": constraint,
                            "installed": installed_version
                        })
                    else:
                        results["outdated"].append({
                            "name": package,
                            "constraint": constraint,
                            "installed": installed_version
                        })
                except:
                    results["unknown"].append({
                        "name": package,
                        "constraint": constraint,
                        "installed": installed_version
                    })
            
            elif constraint.startswith("~="):
                required_version = constraint[2:].strip()
                try:
                    if pkg_resources.parse_version(installed_version) >= pkg_resources.parse_version(required_version):
                        # Check if major version matches
                        installed_parts = installed_version.split('.')
                        required_parts = required_version.split('.')
                        
                        if installed_parts[0] == required_parts[0]:
                            results["compatible"].append({
                                "name": package,
                                "constraint": constraint,
                                "installed": installed_version
                            })
                        else:
                            results["outdated"].append({
                                "name": package,
                                "constraint": constraint,
                                "installed": installed_version
                            })
                    else:
                        results["outdated"].append({
                            "name": package,
                            "constraint": constraint,
                            "installed": installed_version
                        })
                except:
                    results["unknown"].append({
                        "name": package,
                        "constraint": constraint,
                        "installed": installed_version
                    })
            
            else:
                # Unknown constraint format
                results["unknown"].append({
                    "name": package,
                    "constraint": constraint,
                    "installed": installed_version
                })
        
        return results
    
    def install_missing_dependencies(self, upgrade: bool = False) -> Dict[str, Any]:
        """
        Install missing dependencies
        
        Args:
            upgrade: Whether to upgrade existing packages
            
        Returns:
            dict: Installation results
        """
        results = {
            "installed": [],
            "upgraded": [],
            "failed": []
        }
        
        # Check dependencies
        check_results = self.check_dependencies()
        
        # Install missing packages
        for package_info in check_results["missing"]:
            package = package_info["name"]
            constraint = package_info["constraint"]
            
            package_spec = package + constraint if constraint else package
            
            try:
                logger.info(f"Installing {package_spec}")
                subprocess.check_call([sys.executable, "-m", "pip", "install", package_spec])
                results["installed"].append({
                    "name": package,
                    "spec": package_spec
                })
            except Exception as e:
                logger.error(f"Error installing {package_spec}: {str(e)}")
                results["failed"].append({
                    "name": package,
                    "spec": package_spec,
                    "error": str(e)
                })
        
        # Upgrade outdated packages if requested
        if upgrade:
            for package_info in check_results["outdated"]:
                package = package_info["name"]
                constraint = package_info["constraint"]
                
                package_spec = package + constraint if constraint else package
                
                try:
                    logger.info(f"Upgrading {package_spec}")
                    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", package_spec])
                    results["upgraded"].append({
                        "name": package,
                        "spec": package_spec
                    })
                except Exception as e:
                    logger.error(f"Error upgrading {package_spec}: {str(e)}")
                    results["failed"].append({
                        "name": package,
                        "spec": package_spec,
                        "error": str(e)
                    })
        
        # Update installed packages
        self.installed_packages = self._get_installed_packages()
        
        return results
    
    def generate_requirements_file(self, output_file: Optional[str] = None, 
                                  include_versions: bool = True,
                                  include_comments: bool = True) -> str:
        """
        Generate requirements.txt file from installed packages
        
        Args:
            output_file: Path to output file (if None, uses self.requirements_file)
            include_versions: Whether to include version constraints
            include_comments: Whether to include comments
            
        Returns:
            str: Path to generated file
        """
        if output_file is None:
            output_file = self.requirements_file
        
        try:
            with open(output_file, 'w') as f:
                if include_comments:
                    f.write(f"# Generated by DependencyManager on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("# StopSale Automation System dependencies\n\n")
                
                # Get sorted list of packages
                packages = sorted(self.installed_packages.keys())
                
                for package in packages:
                    if include_versions:
                        f.write(f"{package}=={self.installed_packages[package]}\n")
                    else:
                        f.write(f"{package}\n")
            
            logger.info(f"Generated requirements file: {output_file}")
            return output_file
        
        except Exception as e:
            logger.error(f"Error generating requirements file: {str(e)}")
            return ""
    
    def find_unused_dependencies(self) -> List[str]:
        """
        Find potentially unused dependencies
        
        Returns:
            list: List of potentially unused package names
        """
        # This is a simple implementation that checks for imports in Python files
        # A more sophisticated implementation would use tools like pipreqs or importchecker
        
        unused = set(self.installed_packages.keys())
        
        # Packages that are always needed
        essential_packages = {
            "pip", "setuptools", "wheel", "django", "psycopg2", "psycopg2-binary",
            "anthropic", "requests", "celery", "redis", "cryptography"
        }
        
        # Remove essential packages from the set
        unused -= essential_packages
        
        # Walk through Python files and check imports
        for root, dirs, files in os.walk(self.project_root):
            # Skip virtual environments and hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'venv' and d != 'env']
            
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    
                    try:
                        with open(file_path, 'r') as f:
                            content = f.read()
                            
                            # Check for imports
                            for package in list(unused):
                                # Check different import patterns
                                patterns = [
                                    f"import {package}",
                                    f"from {package}",
                                    f"import {package.replace('-', '_')}",
                                    f"from {package.replace('-', '_')}"
                                ]
                                
                                for pattern in patterns:
                                    if pattern in content:
                                        unused.discard(package)
                                        break
                    
                    except Exception as e:
                        logger.error(f"Error checking imports in {file_path}: {str(e)}")
        
        return sorted(list(unused))
    
    def create_virtual_environment(self, venv_dir: Optional[str] = None) -> bool:
        """
        Create a virtual environment
        
        Args:
            venv_dir: Directory for the virtual environment (if None, uses 'venv' in project_root)
            
        Returns:
            bool: True if successful, False otherwise
        """
        if venv_dir is None:
            venv_dir = os.path.join(self.project_root, "venv")
        
        try:
            # Check if venv module is available
            try:
                import venv
                has_venv = True
            except ImportError:
                has_venv = False
            
            if has_venv:
                # Use venv module
                logger.info(f"Creating virtual environment using venv module: {venv_dir}")
                venv.create(venv_dir, with_pip=True)
            else:
                # Use virtualenv command
                logger.info(f"Creating virtual environment using virtualenv command: {venv_dir}")
                subprocess.check_call([sys.executable, "-m", "pip", "install", "virtualenv"])
                subprocess.check_call([sys.executable, "-m", "virtualenv", venv_dir])
            
            logger.info(f"Virtual environment created: {venv_dir}")
            return True
        
        except Exception as e:
            logger.error(f"Error creating virtual environment: {str(e)}")
            return False
    
    def export_dependency_graph(self, output_file: str) -> bool:
        """
        Export dependency graph as JSON
        
        Args:
            output_file: Path to output file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get dependency graph using pip show
            graph = {}
            
            for package in self.installed_packages:
                try:
                    # Run pip show to get package info
                    result = subprocess.run(
                        [sys.executable, "-m", "pip", "show", package],
                        capture_output=True,
                        text=True
                    )
                    
                    if result.returncode == 0:
                        # Parse output
                        info = {}
                        requires = []
                        
                        for line in result.stdout.split('\n'):
                            if ':' in line:
                                key, value = line.split(':', 1)
                                key = key.strip().lower()
                                value = value.strip()
                                
                                if key == 'requires':
                                    # Split requirements
                                    if value:
                                        requires = [r.strip() for r in value.split(',')]
                                else:
                                    info[key] = value
                        
                        # Add to graph
                        graph[package] = {
                            "info": info,
                            "requires": requires
                        }
                
                except Exception as e:
                    logger.error(f"Error getting info for {package}: {str(e)}")
            
            # Write to file
            with open(output_file, 'w') as f:
                json.dump(graph, f, indent=2)
            
            logger.info(f"Dependency graph exported to: {output_file}")
            return True
        
        except Exception as e:
            logger.error(f"Error exporting dependency graph: {str(e)}")
            return False
    
    def check_security_vulnerabilities(self) -> Dict[str, Any]:
        """
        Check for security vulnerabilities in dependencies
        
        Returns:
            dict: Vulnerability check results
        """
        results = {
            "vulnerable": [],
            "safe": [],
            "unknown": []
        }
        
        try:
            # Install safety if not already installed
            try:
                import safety
                has_safety = True
            except ImportError:
                has_safety = False
                
                try:
                    logger.info("Installing safety package")
                    subprocess.check_call([sys.executable, "-m", "pip", "install", "safety"])
                    has_safety = True
                except Exception as e:
                    logger.error(f"Error installing safety: {str(e)}")
            
            if has_safety:
                # Run safety check
                logger.info("Running safety check")
                
                # Create temporary requirements file
                temp_req_file = os.path.join(self.project_root, "temp_requirements.txt")
                self.generate_requirements_file(temp_req_file, include_comments=False)
                
                # Run safety check
                result = subprocess.run(
                    [sys.executable, "-m", "safety", "check", "-r", temp_req_file, "--json"],
                    capture_output=True,
                    text=True
                )
                
                # Remove temporary file
                try:
                    os.remove(temp_req_file)
                except:
                    pass
                
                if result.returncode == 0:
                    # No vulnerabilities found
                    for package in self.installed_packages:
                        results["safe"].append({
                            "name": package,
                            "version": self.installed_packages[package]
                        })
                else:
                    # Parse JSON output
                    try:
                        data = json.loads(result.stdout)
                        
                        # Process vulnerabilities
                        vulnerable_packages = set()
                        
                        for vuln in data.get("vulnerabilities", []):
                            package_name = vuln.get("package_name")
                            affected_version = vuln.get("installed_version")
                            vulnerability_id = vuln.get("vulnerability_id")
                            description = vuln.get("advisory")
                            
                            vulnerable_packages.add(package_name)
                            
                            results["vulnerable"].append({
                                "name": package_name,
                                "version": affected_version,
                                "vulnerability_id": vulnerability_id,
                                "description": description
                            })
                        
                        # Add safe packages
                        for package in self.installed_packages:
                            if package not in vulnerable_packages:
                                results["safe"].append({
                                    "name": package,
                                    "version": self.installed_packages[package]
                                })
                    
                    except json.JSONDecodeError:
                        logger.error("Error parsing safety check output")
                        
                        # Add all packages as unknown
                        for package in self.installed_packages:
                            results["unknown"].append({
                                "name": package,
                                "version": self.installed_packages[package]
                            })
            else:
                # Safety not available, mark all as unknown
                for package in self.installed_packages:
                    results["unknown"].append({
                        "name": package,
                        "version": self.installed_packages[package]
                    })
        
        except Exception as e:
            logger.error(f"Error checking security vulnerabilities: {str(e)}")
            
            # Mark all as unknown
            for package in self.installed_packages:
                results["unknown"].append({
                    "name": package,
                    "version": self.installed_packages[package]
                })
        
        return results


class DependencyReport:
    """Class for generating dependency reports"""
    
    def __init__(self, dependency_manager: DependencyManager):
        """
        Initialize the dependency report
        
        Args:
            dependency_manager: DependencyManager instance
        """
        self.dependency_manager = dependency_manager
    
    def generate_html_report(self, output_file: str) -> bool:
        """
        Generate HTML dependency report
        
        Args:
            output_file: Path to output file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Check dependencies
            check_results = self.dependency_manager.check_dependencies()
            
            # Check for unused dependencies
            unused = self.dependency_manager.find_unused_dependencies()
            
            # Check for security vulnerabilities
            security_results = self.dependency_manager.check_security_vulnerabilities()
            
            # Generate HTML
            html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dependency Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            color: #333;
        }}
        h1, h2, h3 {{
            color: #2c3e50;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin-bottom: 20px;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        th {{
            background-color: #f2f2f2;
        }}
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        .success {{
            color: #27ae60;
        }}
        .warning {{
            color: #f39c12;
        }}
        .error {{
            color: #e74c3c;
        }}
        .summary {{
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
    </style>
</head>
<body>
    <h1>Dependency Report</h1>
    <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    
    <div class="summary">
        <h2>Summary</h2>
        <p><strong>Total packages:</strong> {len(self.dependency_manager.installed_packages)}</p>
        <p><strong>Compatible packages:</strong> <span class="success">{len(check_results["compatible"])}</span></p>
        <p><strong>Missing packages:</strong> <span class="error">{len(check_results["missing"])}</span></p>
        <p><strong>Outdated packages:</strong> <span class="warning">{len(check_results["outdated"])}</span></p>
        <p><strong>Potentially unused packages:</strong> <span class="warning">{len(unused)}</span></p>
        <p><strong>Vulnerable packages:</strong> <span class="error">{len(security_results["vulnerable"])}</span></p>
    </div>
    
    <h2>Installed Packages</h2>
    <table>
        <tr>
            <th>Package</th>
            <th>Installed Version</th>
            <th>Required Version</th>
            <th>Status</th>
        </tr>
"""
            
            # Add compatible packages
            for package in check_results["compatible"]:
                html += f"""
        <tr>
            <td>{package["name"]}</td>
            <td>{package["installed"]}</td>
            <td>{package["constraint"]}</td>
            <td class="success">Compatible</td>
        </tr>"""
            
            # Add outdated packages
            for package in check_results["outdated"]:
                html += f"""
        <tr>
            <td>{package["name"]}</td>
            <td>{package["installed"]}</td>
            <td>{package["constraint"]}</td>
            <td class="warning">Outdated</td>
        </tr>"""
            
            # Add missing packages
            for package in check_results["missing"]:
                html += f"""
        <tr>
            <td>{package["name"]}</td>
            <td>Not installed</td>
            <td>{package["constraint"]}</td>
            <td class="error">Missing</td>
        </tr>"""
            
            # Add unknown packages
            for package in check_results["unknown"]:
                html += f"""
        <tr>
            <td>{package["name"]}</td>
            <td>{package["installed"]}</td>
            <td>{package["constraint"]}</td>
            <td class="warning">Unknown</td>
        </tr>"""
            
            html += """
    </table>
    
    <h2>Potentially Unused Packages</h2>
"""
            
            if unused:
                html += """
    <table>
        <tr>
            <th>Package</th>
            <th>Installed Version</th>
        </tr>
"""
                
                for package in unused:
                    html += f"""
        <tr>
            <td>{package}</td>
            <td>{self.dependency_manager.installed_packages.get(package, "Unknown")}</td>
        </tr>"""
                
                html += """
    </table>
"""
            else:
                html += """
    <p class="success">No potentially unused packages found.</p>
"""
            
            html += """
    <h2>Security Vulnerabilities</h2>
"""
            
            if security_results["vulnerable"]:
                html += """
    <table>
        <tr>
            <th>Package</th>
            <th>Version</th>
            <th>Vulnerability ID</th>
            <th>Description</th>
        </tr>
"""
                
                for vuln in security_results["vulnerable"]:
                    html += f"""
        <tr>
            <td>{vuln["name"]}</td>
            <td>{vuln["version"]}</td>
            <td>{vuln.get("vulnerability_id", "Unknown")}</td>
            <td>{vuln.get("description", "No description available")}</td>
        </tr>"""
                
                html += """
    </table>
"""
            else:
                html += """
    <p class="success">No security vulnerabilities found.</p>
"""
            
            html += """
</body>
</html>
"""
            
            # Write to file
            with open(output_file, 'w') as f:
                f.write(html)
            
            logger.info(f"HTML report generated: {output_file}")
            return True
        
        except Exception as e:
            logger.error(f"Error generating HTML report: {str(e)}")
            return False
    
    def generate_markdown_report(self, output_file: str) -> bool:
        """
        Generate Markdown dependency report
        
        Args:
            output_file: Path to output file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Check dependencies
            check_results = self.dependency_manager.check_dependencies()
            
            # Check for unused dependencies
            unused = self.dependency_manager.find_unused_dependencies()
            
            # Check for security vulnerabilities
            security_results = self.dependency_manager.check_security_vulnerabilities()
            
            # Generate Markdown
            md = f"""# Dependency Report

Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary

- **Total packages:** {len(self.dependency_manager.installed_packages)}
- **Compatible packages:** {len(check_results["compatible"])}
- **Missing packages:** {len(check_results["missing"])}
- **Outdated packages:** {len(check_results["outdated"])}
- **Potentially unused packages:** {len(unused)}
- **Vulnerable packages:** {len(security_results["vulnerable"])}

## Installed Packages

| Package | Installed Version | Required Version | Status |
|---------|------------------|-----------------|--------|
"""
            
            # Add compatible packages
            for package in check_results["compatible"]:
                md += f"| {package['name']} | {package['installed']} | {package['constraint']} | ✅ Compatible |\n"
            
            # Add outdated packages
            for package in check_results["outdated"]:
                md += f"| {package['name']} | {package['installed']} | {package['constraint']} | ⚠️ Outdated |\n"
            
            # Add missing packages
            for package in check_results["missing"]:
                md += f"| {package['name']} | Not installed | {package['constraint']} | ❌ Missing |\n"
            
            # Add unknown packages
            for package in check_results["unknown"]:
                md += f"| {package['name']} | {package['installed']} | {package['constraint']} | ⚠️ Unknown |\n"
            
            md += """
## Potentially Unused Packages

"""
            
            if unused:
                md += """| Package | Installed Version |
|---------|------------------|
"""
                
                for package in unused:
                    md += f"| {package} | {self.dependency_manager.installed_packages.get(package, 'Unknown')} |\n"
            else:
                md += "No potentially unused packages found.\n"
            
            md += """
## Security Vulnerabilities

"""
            
            if security_results["vulnerable"]:
                md += """| Package | Version | Vulnerability ID | Description |
|---------|---------|-----------------|-------------|
"""
                
                for vuln in security_results["vulnerable"]:
                    md += f"| {vuln['name']} | {vuln['version']} | {vuln.get('vulnerability_id', 'Unknown')} | {vuln.get('description', 'No description available')} |\n"
            else:
                md += "No security vulnerabilities found.\n"
            
            # Write to file
            with open(output_file, 'w') as f:
                f.write(md)
            
            logger.info(f"Markdown report generated: {output_file}")
            return True
        
        except Exception as e:
            logger.error(f"Error generating Markdown report: {str(e)}")
            return False


def setup_django_dependency_management():
    """
    Set up Django dependency management
    
    Returns:
        str: Setup instructions
    """
    instructions = """
    # Add the following to your Django settings.py:
    
    import os
    from dependency_manager import DependencyManager
    
    # Initialize dependency manager
    DEPENDENCY_MANAGER = DependencyManager(
        project_root=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        requirements_file="requirements.txt"
    )
    
    # Check dependencies on startup
    if not DEBUG:
        # Only check in production
        check_results = DEPENDENCY_MANAGER.check_dependencies()
        if check_results["missing"] or check_results["outdated"]:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Dependency issues found: {len(check_results['missing'])} missing, "
                f"{len(check_results['outdated'])} outdated"
            )
    
    
    # Create a management command for dependency management:
    # management/commands/check_dependencies.py
    
    from django.core.management.base import BaseCommand
    from django.conf import settings
    
    class Command(BaseCommand):
        help = 'Check and manage dependencies'
        
        def add_arguments(self, parser):
            parser.add_argument(
                '--install',
                action='store_true',
                help='Install missing dependencies',
            )
            parser.add_argument(
                '--upgrade',
                action='store_true',
                help='Upgrade outdated dependencies',
            )
            parser.add_argument(
                '--report',
                action='store_true',
                help='Generate dependency report',
            )
            parser.add_argument(
                '--format',
                choices=['html', 'markdown'],
                default='html',
                help='Report format',
            )
            parser.add_argument(
                '--output',
                help='Output file for report',
            )
        
        def handle(self, *args, **options):
            from dependency_manager import DependencyReport
            
            # Get dependency manager
            dependency_manager = settings.DEPENDENCY_MANAGER
            
            # Check dependencies
            check_results = dependency_manager.check_dependencies()
            
            self.stdout.write(self.style.SUCCESS(
                f"Dependency check: {len(check_results['compatible'])} compatible, "
                f"{len(check_results['missing'])} missing, "
                f"{len(check_results['outdated'])} outdated"
            ))
            
            # Install missing dependencies if requested
            if options['install']:
                install_results = dependency_manager.install_missing_dependencies(
                    upgrade=options['upgrade']
                )
                
                self.stdout.write(self.style.SUCCESS(
                    f"Installation: {len(install_results['installed'])} installed, "
                    f"{len(install_results['upgraded'])} upgraded, "
                    f"{len(install_results['failed'])} failed"
                ))
            
            # Generate report if requested
            if options['report']:
                report = DependencyReport(dependency_manager)
                
                output_file = options['output']
                if not output_file:
                    if options['format'] == 'html':
                        output_file = 'dependency_report.html'
                    else:
                        output_file = 'dependency_report.md'
                
                if options['format'] == 'html':
                    success = report.generate_html_report(output_file)
                else:
                    success = report.generate_markdown_report(output_file)
                
                if success:
                    self.stdout.write(self.style.SUCCESS(
                        f"Report generated: {output_file}"
                    ))
                else:
                    self.stdout.write(self.style.ERROR(
                        f"Error generating report"
                    ))
    """
    return instructions


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    print("Dependency Management Module")
    print("--------------------------")
    print("This module provides tools for managing project dependencies.")
    
    # Get project root
    project_root = input("Enter project root directory (default: current directory): ")
    if not project_root:
        project_root = os.getcwd()
    
    # Create dependency manager
    dependency_manager = DependencyManager(project_root)
    
    # Check dependencies
    print("\nChecking dependencies...")
    check_results = dependency_manager.check_dependencies()
    
    print(f"Compatible packages: {len(check_results['compatible'])}")
    print(f"Missing packages: {len(check_results['missing'])}")
    print(f"Outdated packages: {len(check_results['outdated'])}")
    
    # Ask to install missing dependencies
    if check_results["missing"]:
        install = input("\nInstall missing dependencies? (y/n): ")
        if install.lower() == 'y':
            upgrade = input("Upgrade outdated dependencies? (y/n): ")
            install_results = dependency_manager.install_missing_dependencies(
                upgrade=upgrade.lower() == 'y'
            )
            
            print(f"Installed: {len(install_results['installed'])}")
            print(f"Upgraded: {len(install_results['upgraded'])}")
            print(f"Failed: {len(install_results['failed'])}")
    
    # Generate report
    report = input("\nGenerate dependency report? (y/n): ")
    if report.lower() == 'y':
        report_format = input("Report format (html/markdown): ")
        
        if report_format.lower() in ('html', 'h'):
            output_file = os.path.join(project_root, "dependency_report.html")
            DependencyReport(dependency_manager).generate_html_report(output_file)
        else:
            output_file = os.path.join(project_root, "dependency_report.md")
            DependencyReport(dependency_manager).generate_markdown_report(output_file)
        
        print(f"Report generated: {output_file}")
    
    # Django integration
    print("\nDjango integration:")
    print(setup_django_dependency_management())
