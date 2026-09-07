"""scheduler package"""
from scheduler.fcfs       import fcfs
from scheduler.sjf        import sjf
from scheduler.round_robin import round_robin
from scheduler.priority   import priority_scheduling

__all__ = ["fcfs", "sjf", "round_robin", "priority_scheduling"]
