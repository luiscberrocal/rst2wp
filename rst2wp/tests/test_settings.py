from unittest import TestCase
from os import path

__author__ = 'luiscberrocal'


class TestSettings(TestCase):

    def test_directories(self):
        from settings.test import RST2WP_ROOT, SITE_NAME, FIXTURE_PATH, SITE_ROOT
        print('RST2WP_ROOT  : %s' % RST2WP_ROOT)
        print('SITE_ROOT    : %s' % SITE_ROOT)
        print('SITE_NAME    : %s' % SITE_NAME)
        print('FIXTURE_PATH : %s' % FIXTURE_PATH)

        self.assertTrue(path.exists(FIXTURE_PATH))
