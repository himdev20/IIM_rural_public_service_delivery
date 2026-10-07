"""Trucks, Time, and the Last Mile.

Capacity constraints and the cost of rural public-service delivery: a
reproducible re-analysis of the Nagpur liquid-nitrogen routing case.
"""

from .data import Instance, load_case_instance
from .model import Problem, Solution, TimeModel

__version__ = "0.1.0"
__all__ = ["Instance", "Problem", "Solution", "TimeModel", "load_case_instance"]
