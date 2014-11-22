from os.path import join
import upload
import mock
from config import TEMP_DIRECTORY
try:
    import unittest2 as unittest
except ImportError:
    import unittest  # and hope for the best
from settings.test import FIXTURE_PATH

class TestUpload(unittest.TestCase):
    filename_to_upload = 'python-logo.png'
    file_url_to_upload = 'https://pypi.python.org/static/images/' + filename_to_upload #join(FIXTURE_PATH, 'chrome.png')
    downloaded_filename = join(TEMP_DIRECTORY, filename_to_upload)

    def create_directive(self, filename, **kwargs):
        self.state_machine = mock.Mock()
        self.up = upload.UploadDirective('upload', [filename], {}, None, 'lineno', 'content_offset', '.. upload::', 'state', self.state_machine)

    def test_upload(self):

        self.create_directive(self.file_url_to_upload)
        self.assertEqual(self.up.arguments, [self.file_url_to_upload])

        output = self.up.run()

        assert self.state_machine.document.settings.wordpress_instance.upload_file.called
        self.assertEqual(self.state_machine.document.settings.wordpress_instance.upload_file.call_args_list,
                         [((self.downloaded_filename,), {})])

    def test_no_upload(self):
        #file_url_to_upload = join(FIXTURE_PATH, 'install.rst')
        self.create_directive(self.file_url_to_upload)
        self.up.options['uploaded'] = 'http://example.com/already/exists'

        output = self.up.run()
        self.assertFalse(self.state_machine.document.settings.wordpress_instance.upload_file.called)
