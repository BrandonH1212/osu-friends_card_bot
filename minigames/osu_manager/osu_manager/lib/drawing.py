"""
Drawing library
"""

from PIL import (
    Image,
)
from pathlib import Path
from .manager_types import ImageBuildData

LIB_PATH = Path(__file__).parent.absolute()
DUMP_PATH = f"{LIB_PATH}/../image_dump"
RESOURCES_PATH = f"{LIB_PATH}/../resources"
DEFAULT_IMAGE_PATH = f"{LIB_PATH}/../resources/menu/menu_base.png"


def get_dump_image(img_data: ImageBuildData) -> str:
    file_path = f"{DUMP_PATH}/{img_data.image}"
    base_file = Path(file_path)
    if base_file.is_file():
        return file_path
    else:
        generate_image(img_data)
        return file_path


def generate_image(img_data: ImageBuildData) -> None:
    img = None
    dump_path = f"{DUMP_PATH}/{img_data.image}"
    resource_path = f"{RESOURCES_PATH}/{img_data.image_path}"

    for img_settings in img_data.mapping:
        if img:
            img_path, size = img_settings
            img.paste(img_path, size)
        else:
            img = Image.open(resource_path)

    img.save(dump_path)
