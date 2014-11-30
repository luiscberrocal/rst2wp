import os
from docutils import core
import docutils
import docutils.writers.html4css1
from rst2wp import WordPressReader

__author__ = 'luiscberrocal'


class RestructuredTextParser(object):

    def __init__(self):
        self.bibliographic_fields = {}

    def parse_text(self, text):
        writer = docutils.writers.html4css1.Writer()
        writer.translator_class = RestructuredTranslator
        preview = False
        reader =  None #WordPressReader(preview)
        categories = {}
        self.bibliographic_fields['categories'] = categories
        overrides = {
            'bibliographic_fields': self.bibliographic_fields
        }

        filename = None #os.path.abspath(filename)
        # overrides = {
        #     'wordpress_instance': wp,
        #     'application': self,
        #     'bibliographic_fields': {
        #         'categories': categories
        #     },
        #     'directive_uris': directive_uris,
        #     'used_images': used_images,
        #     # FIXME: probably a nicer way to do this
        #     'filename': self.filename,
        #     'tab_width': self.config.getint('config', 'tab_width'),
        #     'initial_header_level': self.config.getint('config', 'initial_header_level'),
        # }
        output = core.publish_parts(source=text, writer=writer,
                                    source_path= filename,
                                    reader = reader,
                                    settings_overrides = overrides)
        # print yaml.dump(output, default_flow_style=False)
        body = output['body']
        return body


class RestructuredTranslator(docutils.writers.html4css1.HTMLTranslator):
    def visit_image(self, node):
        docutils.writers.html4css1.HTMLTranslator.visit_image(self, node)
        image = self.body[-1]
        # Default title to alt text
        title = node.attributes.get('title', node.attributes.get('alt', None))

        if title:
            # Hackishly insert the image title into the image tag
            self.body[-1] = image.replace('/>', 'title="%s" />'%self.attval(title))

    def visit_literal_block(self, node):
        docutils.writers.html4css1.HTMLTranslator.visit_literal_block(self, node)
        pre_tag = self.body[-1]
        if 'code' in node.attributes.get('classes'):
            self.body[-1] = ''

    def depart_literal_block(self, node):
        docutils.writers.html4css1.HTMLTranslator.depart_literal_block(self, node)
        pre_tag = self.body[-1]
        #print(node.attributes.get('classes'))
        #print(pre_tag)
        if 'code' in node.attributes.get('classes'):
            self.body[-1] = ''