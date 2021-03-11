"""
config file
"""

from dataclasses import dataclass
from pathlib import Path
import json
from lib.manager_types import ImageBuildData

IMG_CONFIG_NAME = "img_config.json"


def load_image_config(config_path: str):
    config_file_path = Path(__file__).parent / config_path
    with config_file_path.open() as config_file:
        json_dict = json.load(config_file)

    kwargs = {}
    for key, value in json_dict.items():
        kwargs[key] = ImageBuildData(**value)
    return kwargs


@dataclass
class ImageConfig:
    MENU_MAPPING: ImageBuildData


img_config = ImageConfig(**load_image_config(IMG_CONFIG_NAME))
