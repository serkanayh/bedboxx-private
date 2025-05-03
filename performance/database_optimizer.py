"""
Database Optimization Module for StopSale Automation System

This module provides database indexing and query optimization for improving
the performance of database operations in the StopSale Automation System.
"""

import logging
from typing import List, Dict, Any, Tuple, Optional
import time

# Set up logging
logger = logging.getLogger(__name__)

class DatabaseOptimizer:
    """Class for optimizing database operations"""
    
    def __init__(self, connection=None):
        """
        Initialize the database optimizer
        
        Args:
            connection: Database connection object (optional)
        """
        self.connection = connection
        self.slow_queries = []
        self.index_recommendations = []
        self.optimization_history = []
    
    def set_connection(self, connection):
        """
        Set the database connection
        
        Args:
            connection: Database connection object
        """
        self.connection = connection
    
    def analyze_query_performance(self, query: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Analyze the performance of a SQL query
        
        Args:
            query: SQL query to analyze
            params: Query parameters (optional)
            
        Returns:
            dict: Performance metrics
        """
        if not self.connection:
            logger.error("No database connection provided")
            return {"error": "No database connection"}
        
        try:
            # Add EXPLAIN to the query
            if query.strip().lower().startswith("select"):
                explain_query = f"EXPLAIN ANALYZE {query}"
            else:
                logger.warning(f"Cannot explain non-SELECT query: {query[:50]}...")
                return {"error": "Can only explain SELECT queries"}
            
            # Execute the query with timing
            start_time = time.time()
            
            cursor = self.connection.cursor()
            if params:
                cursor.execute(explain_query, params)
            else:
                cursor.execute(explain_query)
                
            explain_results = cursor.fetchall()
            execution_time = time.time() - start_time
            
            # Parse the explain results
            analysis = self._parse_explain_results(explain_results)
            analysis["execution_time"] = execution_time
            analysis["query"] = query
            
            # Check if this is a slow query
            if execution_time > 0.5:  # Threshold for slow queries (500ms)
                self.slow_queries.append({
                    "query": query,
                    "execution_time": execution_time,
                    "timestamp": time.time()
                })
                
                # Generate index recommendations
                recommendations = self._generate_index_recommendations(query, analysis)
                if recommendations:
                    self.index_recommendations.extend(recommendations)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing query: {str(e)}")
            return {"error": str(e)}
    
    def _parse_explain_results(self, explain_results: List[Tuple]) -> Dict[str, Any]:
        """
        Parse the results of an EXPLAIN ANALYZE query
        
        Args:
            explain_results: Results from EXPLAIN ANALYZE
            
        Returns:
            dict: Parsed analysis
        """
        analysis = {
            "operations": [],
            "table_scans": 0,
            "index_scans": 0,
            "estimated_rows": 0,
            "actual_rows": 0
        }
        
        for row in explain_results:
            row_str = str(row[0])
            
            # Extract operation type
            operation = {}
            
            if "Seq Scan" in row_str:
                operation["type"] = "Sequential Scan"
                analysis["table_scans"] += 1
            elif "Index Scan" in row_str:
                operation["type"] = "Index Scan"
                analysis["index_scans"] += 1
            elif "Index Only Scan" in row_str:
                operation["type"] = "Index Only Scan"
                analysis["index_scans"] += 1
            else:
                operation["type"] = "Other"
            
            # Extract table name
            import re
            table_match = re.search(r"on ([a-zA-Z_]+)", row_str)
            if table_match:
                operation["table"] = table_match.group(1)
            
            # Extract row estimates
            rows_match = re.search(r"rows=(\d+)", row_str)
            if rows_match:
                operation["estimated_rows"] = int(rows_match.group(1))
                analysis["estimated_rows"] += int(rows_match.group(1))
            
            # Extract actual rows
            actual_rows_match = re.search(r"actual rows=(\d+)", row_str)
            if actual_rows_match:
                operation["actual_rows"] = int(actual_rows_match.group(1))
                analysis["actual_rows"] += int(actual_rows_match.group(1))
            
            # Extract cost
            cost_match = re.search(r"cost=([0-9.]+)\.\.([0-9.]+)", row_str)
            if cost_match:
                operation["start_cost"] = float(cost_match.group(1))
                operation["total_cost"] = float(cost_match.group(2))
            
            analysis["operations"].append(operation)
        
        return analysis
    
    def _generate_index_recommendations(self, query: str, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate index recommendations based on query analysis
        
        Args:
            query: The SQL query
            analysis: Query analysis results
            
        Returns:
            list: Index recommendations
        """
        recommendations = []
        
        # Check for table scans
        if analysis["table_scans"] > 0:
            # Extract WHERE clause columns
            import re
            where_columns = re.findall(r"WHERE\s+([a-zA-Z_]+)\.([a-zA-Z_]+)\s*=", query, re.IGNORECASE)
            where_columns.extend(re.findall(r"WHERE\s+([a-zA-Z_]+)\s*=", query, re.IGNORECASE))
            
            # Extract JOIN columns
            join_columns = re.findall(r"JOIN\s+([a-zA-Z_]+)\s+ON\s+([a-zA-Z_]+)\.([a-zA-Z_]+)\s*=", query, re.IGNORECASE)
            
            # Extract ORDER BY columns
            order_columns = re.findall(r"ORDER\s+BY\s+([a-zA-Z_]+)\.([a-zA-Z_]+)", query, re.IGNORECASE)
            order_columns.extend(re.findall(r"ORDER\s+BY\s+([a-zA-Z_]+)", query, re.IGNORECASE))
            
            # Generate recommendations for WHERE columns
            for col in where_columns:
                if isinstance(col, tuple) and len(col) == 2:
                    table, column = col
                    recommendations.append({
                        "table": table,
                        "column": column,
                        "reason": "Used in WHERE clause",
                        "priority": "high"
                    })
                elif isinstance(col, str):
                    column = col
                    # Try to find the table from operations
                    table = None
                    for op in analysis["operations"]:
                        if "table" in op:
                            table = op["table"]
                            break
                    
                    if table:
                        recommendations.append({
                            "table": table,
                            "column": column,
                            "reason": "Used in WHERE clause",
                            "priority": "high"
                        })
            
            # Generate recommendations for JOIN columns
            for join in join_columns:
                if len(join) == 3:
                    table, _, column = join
                    recommendations.append({
                        "table": table,
                        "column": column,
                        "reason": "Used in JOIN condition",
                        "priority": "high"
                    })
            
            # Generate recommendations for ORDER BY columns
            for col in order_columns:
                if isinstance(col, tuple) and len(col) == 2:
                    table, column = col
                    recommendations.append({
                        "table": table,
                        "column": column,
                        "reason": "Used in ORDER BY clause",
                        "priority": "medium"
                    })
                elif isinstance(col, str):
                    column = col
                    # Try to find the table from operations
                    table = None
                    for op in analysis["operations"]:
                        if "table" in op:
                            table = op["table"]
                            break
                    
                    if table:
                        recommendations.append({
                            "table": table,
                            "column": column,
                            "reason": "Used in ORDER BY clause",
                            "priority": "medium"
                        })
        
        return recommendations
    
    def get_slow_queries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get the list of slow queries
        
        Args:
            limit: Maximum number of queries to return
            
        Returns:
            list: Slow queries with performance metrics
        """
        # Sort by execution time (slowest first)
        sorted_queries = sorted(self.slow_queries, key=lambda q: q["execution_time"], reverse=True)
        return sorted_queries[:limit]
    
    def get_index_recommendations(self) -> List[Dict[str, Any]]:
        """
        Get index recommendations
        
        Returns:
            list: Index recommendations
        """
        # Remove duplicates
        unique_recommendations = []
        seen = set()
        
        for rec in self.index_recommendations:
            key = f"{rec['table']}.{rec['column']}"
            if key not in seen:
                seen.add(key)
                unique_recommendations.append(rec)
        
        # Sort by priority
        priority_map = {"high": 3, "medium": 2, "low": 1}
        sorted_recommendations = sorted(
            unique_recommendations, 
            key=lambda r: priority_map.get(r["priority"], 0),
            reverse=True
        )
        
        return sorted_recommendations
    
    def generate_index_creation_sql(self) -> List[str]:
        """
        Generate SQL statements for creating recommended indexes
        
        Returns:
            list: SQL statements for index creation
        """
        sql_statements = []
        recommendations = self.get_index_recommendations()
        
        for i, rec in enumerate(recommendations):
            table = rec["table"]
            column = rec["column"]
            index_name = f"idx_{table}_{column}"
            
            sql = f"CREATE INDEX {index_name} ON {table} ({column});"
            sql_statements.append(sql)
        
        return sql_statements
    
    def apply_index_recommendations(self, confirm: bool = True) -> List[Dict[str, Any]]:
        """
        Apply index recommendations to the database
        
        Args:
            confirm: Whether to confirm each index creation
            
        Returns:
            list: Results of index creation
        """
        if not self.connection:
            logger.error("No database connection provided")
            return [{"error": "No database connection"}]
        
        results = []
        recommendations = self.get_index_recommendations()
        
        for rec in recommendations:
            table = rec["table"]
            column = rec["column"]
            index_name = f"idx_{table}_{column}"
            
            if confirm:
                logger.info(f"Creating index {index_name} on {table}.{column}...")
            
            try:
                cursor = self.connection.cursor()
                sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({column});"
                
                start_time = time.time()
                cursor.execute(sql)
                execution_time = time.time() - start_time
                
                self.connection.commit()
                
                result = {
                    "status": "success",
                    "index_name": index_name,
                    "table": table,
                    "column": column,
                    "execution_time": execution_time
                }
                
                # Record in optimization history
                self.optimization_history.append({
                    "type": "index_creation",
                    "index_name": index_name,
                    "table": table,
                    "column": column,
                    "timestamp": time.time(),
                    "execution_time": execution_time
                })
                
                logger.info(f"Successfully created index {index_name}")
                
            except Exception as e:
                result = {
                    "status": "error",
                    "index_name": index_name,
                    "table": table,
                    "column": column,
                    "error": str(e)
                }
                logger.error(f"Error creating index {index_name}: {str(e)}")
            
            results.append(result)
        
        return results
    
    def optimize_query(self, query: str) -> Dict[str, Any]:
        """
        Optimize a SQL query
        
        Args:
            query: SQL query to optimize
            
        Returns:
            dict: Optimization results
        """
        original_query = query
        optimized_query = query
        
        # Optimization 1: Replace SELECT * with specific columns
        import re
        if re.search(r"SELECT\s+\*\s+FROM", optimized_query, re.IGNORECASE):
            # This is a simplified example - in a real implementation,
            # we would analyze the query and determine which columns are actually needed
            logger.warning("Query uses SELECT * - consider specifying only required columns")
        
        # Optimization 2: Add LIMIT if not present
        if not re.search(r"LIMIT\s+\d+", optimized_query, re.IGNORECASE):
            # Only add LIMIT to SELECT queries without aggregation
            if (re.search(r"SELECT", optimized_query, re.IGNORECASE) and
                not re.search(r"GROUP\s+BY", optimized_query, re.IGNORECASE) and
                not re.search(r"COUNT\(", optimized_query, re.IGNORECASE) and
                not re.search(r"SUM\(", optimized_query, re.IGNORECASE) and
                not re.search(r"AVG\(", optimized_query, re.IGNORECASE)):
                optimized_query += " LIMIT 1000"
                logger.info("Added LIMIT clause to query")
        
        # Optimization 3: Check for missing JOIN conditions
        join_count = len(re.findall(r"JOIN", optimized_query, re.IGNORECASE))
        on_count = len(re.findall(r"ON", optimized_query, re.IGNORECASE))
        
        if join_count > on_count:
            logger.warning("Query may have missing JOIN conditions")
        
        # Record optimization in history
        if original_query != optimized_query:
            self.optimization_history.append({
                "type": "query_optimization",
                "original_query": original_query,
                "optimized_query": optimized_query,
                "timestamp": time.time()
            })
        
        return {
            "original_query": original_query,
            "optimized_query": optimized_query,
            "changes": original_query != optimized_query
        }
    
    def get_optimization_history(self) -> List[Dict[str, Any]]:
        """
        Get the optimization history
        
        Returns:
            list: Optimization history
        """
        return self.optimization_history


# Example usage with Django
def optimize_django_queries():
    """
    Optimize Django queries by adding appropriate indexes
    
    Returns:
        dict: Optimization results
    """
    try:
        # Import Django modules
        from django.db import connection
        from django.db.models import Q
        
        # Initialize the optimizer
        optimizer = DatabaseOptimizer(connection)
        
        # Analyze common queries
        results = {
            "analyzed_queries": 0,
            "slow_queries": 0,
            "index_recommendations": [],
            "applied_indexes": []
        }
        
        # Example: Analyze a query for Email model
        query = """
        SELECT e.id, e.subject, e.sender, e.received_date, e.status
        FROM emails_email e
        WHERE e.status = 'pending'
        ORDER BY e.received_date DESC
        """
        
        analysis = optimizer.analyze_query_performance(query)
        results["analyzed_queries"] += 1
        
        if "error" not in analysis:
            if analysis.get("execution_time", 0) > 0.5:
                results["slow_queries"] += 1
        
        # Example: Analyze a query for EmailRow model
        query = """
        SELECT er.id, er.hotel_name, er.room_type, er.start_date, er.end_date, er.sale_type, er.status
        FROM emails_emailrow er
        JOIN emails_email e ON er.email_id = e.id
        WHERE er.status = 'pending' AND e.received_date > '2025-01-01'
        ORDER BY er.hotel_name, er.room_type
        """
        
        analysis = optimizer.analyze_query_performance(query)
        results["analyzed_queries"] += 1
        
        if "error" not in analysis:
            if analysis.get("execution_time", 0) > 0.5:
                results["slow_queries"] += 1
        
        # Get index recommendations
        recommendations = optimizer.get_index_recommendations()
        results["index_recommendations"] = recommendations
        
        # Generate SQL for index creation
        sql_statements = optimizer.generate_index_creation_sql()
        
        # Apply recommendations if confirmed
        apply_indexes = input("Apply recommended indexes? (y/n): ")
        if apply_indexes.lower() == 'y':
            applied_indexes = optimizer.apply_index_recommendations()
            results["applied_indexes"] = applied_indexes
        
        return results
        
    except ImportError:
        logger.error("Django modules not available")
        return {"error": "Django modules not available"}


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    print("Database Optimizer Module")
    print("------------------------")
    print("This module provides database indexing and query optimization.")
    
    # Check if running in Django environment
    try:
        import django
        print("\nDjango environment detected.")
        print("You can run optimize_django_queries() to analyze and optimize Django queries.")
    except ImportError:
        print("\nDjango environment not detected.")
        print("This module can still be used with other database connections.")
