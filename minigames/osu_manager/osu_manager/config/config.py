"""
config file
"""

from dataclasses import dataclass


@dataclass
class BaseConfig:
    pass


@dataclass
class ManagerConfig(BaseConfig):
    pass


config = ManagerConfig()
