"""
Module to define types
"""

from dataclasses import dataclass


@dataclass
class ImageBuildData:
    image: str
    image_path: str
    mapping: dict
