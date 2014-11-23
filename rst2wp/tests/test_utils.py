from unittest import TestCase
from utils import color_print, PRINTING_COLORS

__author__ = 'luiscberrocal'


class TestUtils(TestCase):

    def test_print_colors(self):
        for name, value in PRINTING_COLORS.items():
            color_print('Coloring with %-15s code %d'% (name, value), name)