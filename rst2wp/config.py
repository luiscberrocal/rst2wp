import os.path
from xdg import BaseDirectory

def posts_location():
    return os.path.join(BaseDirectory.save_config_path('rst2wp', 'published'),
                        'posts')

def images_location():
    return os.path.join(BaseDirectory.save_config_path('rst2wp', 'published'),
                        'images')

def temp_location():
    from settings.test import FIXTURE_PATH
    temp_folder = os.path.join(FIXTURE_PATH, 'tmp')
    if not os.path.exists(temp_folder):
        os.mkdir(temp_folder)
    return temp_folder

POSTS_LOCATION = posts_location
IMAGES_LOCATION = images_location

TEMP_DIRECTORY = temp_location()
TEMP_FILES = []
