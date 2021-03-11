"""
Osu manager minigame
"""
from lib.drawing import get_dump_image
from config.config import img_config


def main() -> None:
    get_dump_image(img_config.MENU_MAPPING)


def init() -> None:
    pass


if __name__ == '__main__':
    main()
