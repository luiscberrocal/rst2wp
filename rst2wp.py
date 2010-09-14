#!/usr/bin/env python

'''Script to translate rst into HTML and post it to a Wordpress server.

See the README for more details.
'''
# FIXME: robust against missing configuration keys
# FIXME: prompt for a good filename/extension for unknown weird files
# FIXME: could use fields['date'] for publish date

import re
import argparse
from xdg import BaseDirectory
import ConfigParser
import sys
import os.path
import tempfile, subprocess, time
from docutils import core, io, nodes, utils
from docutils.readers import standalone
import docutils.writers.html4css1
import docutils.transforms
#import yaml
import utils

sys.path.insert(0, os.path.join(os.path.abspath(os.path.dirname(__file__)), "lib"))

import wordpresslib
import my_image # registers MyImageDirective
import upload   # registers UploadDirective
from config import IMAGES_LOCATION, POSTS_LOCATION, TEMP_FILES

class UsageError(Exception):
    @classmethod
    def usage_message(cls):
        return \
'''Usage: {name} filename
Converts an RST file into HTML and posts it to Wordpress.
See the source for more details.'''.format(name=os.path.basename(sys.argv[0]))

    def error_message(self):
        return "{error}\nSee '{path} --help'.".format(error=self.args[0],
                                                      path=self.args[1])


class MyTranslator(docutils.writers.html4css1.HTMLTranslator):
    def visit_image(self, node):
        docutils.writers.html4css1.HTMLTranslator.visit_image(self, node)
        image = self.body[-1]
        # Default title to alt text
        title = node.attributes.get('title', node.attributes.get('alt', None))

        if title:
            # Hackishly insert the image title into the image tag
            self.body[-1] = image.replace('/>', 'title="%s" />'%self.attval(title))


class BibliographicTransform(docutils.transforms.Transform):
    '''Parses the crap out of the bibliographic fields in the document
    and sticks them in document.settings.bibliographic_fields.'''
    default_priority = 98
    def __init__(self, *args, **kwargs):
        docutils.transforms.Transform.__init__(self, *args, **kwargs)

    def apply(self, **kwargs):
        header = self.document[0]
        if isinstance(header, nodes.field_list):
            fields = self.get_header_as_dict(header)
        else:
            fields = {}
        self.document.settings.bibliographic_fields = fields

    def get_header_as_dict(self, header):
        fields = {}
        for field in header.children:
            field_name, field_body = field.children

            # field_name is a node with a Text child
            assert len(field_name.children) == 1, "don't know how to handle"
            assert isinstance(field_name.children[0], nodes.Text)
            key = field_name.children[0].astext()

            # field_body is a node with either a bulleted_list child, or
            # a single Text child, or..?
            if len(field_body.children) == 0:
                fields[key] = None
                continue

            assert len(field_body.children) == 1, "don't know how to handle"
            data = field_body.children[0]
            if isinstance(data, nodes.bullet_list):
                value = [node.astext() for node in data.children]
            elif isinstance(data, nodes.Text):
                value = data.astext()
            elif isinstance(data, nodes.paragraph):
                value = data.children[0].astext()
            else:
                raise TypeError, "don't know how to handle a %s in the header %s"%(
                    data.__class__, key)
            fields[key] = value

        return fields

class ValidityCheckerTransform(docutils.transforms.Transform):
    default_priority = 99
    def apply(self):
        fields = self.document.settings.bibliographic_fields
        app = self.document.settings.application

        def _no_field(msg, msg2=''):
            if msg2: msg = msg+msg2
            raise TypeError, msg

        if 'title' not in fields:
            _no_field("title missing", """
- Make sure you have a bibliographic field list at the top of your file.
- Make sure that a title field is included.""")

        if fields['title'] == '':
            _no_field("title empty", """
- Please set a title, because otherwise rst2wp breaks horribly.""")

        if 'category' in fields:
            fields['categories'] = fields.pop('category')

        if not fields.get('categories') and \
                not app.config.has_option('config', 'default_category'):
            _no_field("No categories supplied", """
WordPress requires at least one category.

If you don't want to categorize this post, use the "Uncategorized" category.

Set config.default_category to do this automatically.

:categories: Uncategorized
""")

        print "Checking validity of categories/tags"
        categories = fields.get('categories') or fields.get('category')
        if categories == None:
            fields['categories'] = categories = [app.config.get('config', 'default_category')]

        wp = self.document.settings.wordpress_instance
        if not self.document.settings.application.dont_check_tags:
            for cat in categories:
                self.check_existing_category(wp, cat)

        if 'tag' in fields:
            fields['tags'] = fields.pop('tag')

        if 'tags' in fields:
            if not self.document.settings.application.dont_check_tags:
                for tag in fields['tags']:
                    self.check_existing_tag(wp, tag)
        print "Tags/categories: OK"

    def check_existing_tag(self, wp, tag):
        if ',' in tag:
            raise ValueError, """Cannot use tags with ',' in the name.

WordPress will break tags at commas. If you really want a tag with a comma, add it via the web interface."""
        if not wp.has_tag(tag):
            tag = self.read_tag(tag)

    def check_existing_category(self, wp, cat):
        if not wp.has_category(cat):
            cat = self.read_category(cat)

    def read_base(self, name):
        fmt = {'name': repr(str(name))}
        slug = raw_input("Slug for {name} [auto-generate]: ".format(**fmt))
        description = raw_input("Description for {name} [none]: ".format(**fmt))
        return {'slug': slug, 'description': description, 'name': name}

    def read_tag(self, tag):
        fmt = {'tag': repr(str(tag))}
        if ',' in tag:
            raise ValueError, """Cannot create tag with ',' in the name.

If you really want a tag with a comma in the name, create it via the web interface first."""

        print "Post has non-existent tag {tag}. Ctrl-C to cancel.".format(**fmt)
        print "rst2wp can create the tag automatically, but can't set description or slug via XML-RPC API. If you want to edit these things, log in to the blog!"
        raw_input("Confirm creation? [yes] ")

    def read_category(self, cat):
        fmt = {'category': repr(str(cat))}
        print "Post has non-existent category {category}. Ctrl-C to cancel.".format(**fmt)
        raw_input("Confirm? [yes]")

        data = self.read_base(cat)
        parent_id = raw_input("Parent id for {category} [none]: ".format(**fmt))

        c = wordpresslib.WordPressCategory(parent_id=parent_id, **data)
        wp.new_category(c)


class WordPressReader(standalone.Reader):
    def __init__(self, preview=False):
        standalone.Reader.__init__(self)
        self.preview = preview

    def get_transforms(self):
        transforms = standalone.Reader.get_transforms(self)
        if self.preview: return transforms

        transforms.insert(0, BibliographicTransform)
        transforms.insert(1, ValidityCheckerTransform)
        return transforms


class Application(object):
    '''Container for all dotrc-config-related stuff'''
    config_name = 'rst2wp'
    def __init__(self):
        super(Application, self).__init__()
        self._config = None

    @property
    def config(self):
        if self._config: return self._config
        return self._load_config()

    def _read_configs_into(self, config, filepath='wordpressrc', config_name='config'):
        '''Used to read application config (blog name, etc.)'''
        for dir in BaseDirectory.load_config_paths(self.config_name):
            filename = os.path.join(dir, filepath)
            if not os.path.exists(filename): continue
            print "loading {0} from".format(config_name), filename
            with file(filename) as f:
                config.readfp(f)
            print 'config loaded'

    def _load_config(self):
        config = ConfigParser.SafeConfigParser()
        self.VERBOSE = False

        self._read_configs_into(config)

        DEFAULT_WORDPRESS_URL = 'http://wordpress.example.com/wordpress/xmlrpc.php'

        if not config.has_section('account'):
            config.add_section('account')
            # Fill in some default values
            config.set('account', 'url', DEFAULT_WORDPRESS_URL)
            config.set('account', 'username', 'joe_user')
            config.set('account', 'password', 'trustNo1')

            config.add_section('config')
            config.set('config', 'data_storage', 'file')
            config.set('config', 'publish_default', 'yes')
            config.set('config', 'save_uploads', 'no')
            config.set('config', 'scale_images', 'no')

            path = os.path.join(BaseDirectory.save_config_path('rst2wp'), 'wordpressrc')
            print 'Need configuration! Edit %s'%(path,)
            with file(path, 'wb') as fp:
                config.write(fp)
            sys.exit()

        if config.get('account', 'url') == DEFAULT_WORDPRESS_URL:
            # Don't wipe out what they might have configured
            print 'Still needs configuration! Edit %s'%(path,)
            sys.exit()

        self._config = config
        return config

    def search_configs(self, configfile, section, key, default=None):
        '''Looks through all configs named configfile for (section, key)'''
        for dir in BaseDirectory.load_config_paths(self.config_name):
            filename = os.path.join(dir, configfile)
            if not os.path.exists(filename): continue

            config = ConfigParser.SafeConfigParser()
            with file(filename) as f:
                config.readfp(f)
            if not config.has_section(section): continue

            if not config.has_option(section, key): continue

            return config.get(section, key)

        return default


class Rst2Wp(Application):
    def _known_link_stanza(self):
        known_links = ConfigParser.SafeConfigParser()
        self._read_configs_into(known_links, 'known_links', 'known links')

        links = []
        for sectname in known_links.sections():
            links.append('.. _`{name}`: {link}'.format(link=sectname,
                                                       name=known_links.get(sectname, 'link')))

        return '\n\n'+'\n'.join(links)

    def __init__(self):
        super(Rst2Wp, self).__init__()
        self.preview = False
        self.list_tags = False
        self.list_categories = False
        self.publish = None

    @property
    def data_storage(self):
        return self.config.get('config', 'data_storage')

    def parse_args(self, args):
        parser = argparse.ArgumentParser(description=
                                         'Convert ReStructuredText to HTML and upload to a Wordpress instance.')
        parser.add_argument('-n', '--preview', action='store_true',
                            help="don't upload; render to HTML and display in $BROWSER")
        parser.add_argument('-c', '--config', dest='alt_config', nargs='?', type=str,
                            help='use alternate config (see README for details)')
        parser.add_argument('--dont-check-tags', action='store_true',
                            help="don't check categories/tags for existance")
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('filename', type=str, nargs='?',
                            help='the ReStructuredText source file (optional if querying tags/categories)')
        group.add_argument('--list-tags', action='store_true',
                            help="list available tags for this Wordpress instance")
        group.add_argument('--list-categories', action='store_true',
                            help="list available categories for this Wordpress instance")

        group = parser.add_mutually_exclusive_group()
        group.add_argument('--publish', action='store_const', const=True,
                           help="mark this post as published")
        group.add_argument('--no-publish', dest='publish', action='store_const', const=False,
                           help="do not mark this post as published")

        options = parser.parse_args(args, self)
        if isinstance(self.alt_config, str): self.config_name = self.alt_config

    def prompt(self, msg):
        return raw_input(msg)

    def save_info(self, document, section, key, value, location=None,
                  # FIXME: fugly hack
                  image=None, type='image'):
        "Usage: app.save_info(document, 'post ' + filename, 'id', '365')"
        # N.B. The get_info, has_info, and save_info rely on the
        # convention that if you're looking for some info on an image, you pass
        # section = 'image http://www.example.com/image.jpg', key = 'saved_as',
        # and (for save_info) image = 'http://www.example.com/image.jpg'.
        # save_info uses the extra argument to locate the image in the source file.
        # It also relies on the fact that document.settings.image_uris is a dict
        # of 'image http://www.example.com/image.jpg.form-200x200' => uploaded URL.
        location = location or POSTS_LOCATION
        data_storage = self.data_storage
        if data_storage in ['both', 'dotrc']:
            config = ConfigParser.SafeConfigParser()
            filename = location()
            if os.path.exists(filename):
                with file(filename) as f:
                    config.readfp(f)

            if not config.has_section(section):
                config.add_section(section)

            config.set(section, key, value)
            with file(filename, 'wb') as fp:
                config.write(fp)

        if data_storage in ['both', 'file']:
            if location == POSTS_LOCATION:
                self.replace_field(document, key, value)
            elif location == IMAGES_LOCATION:
                if image:
                    self.replace_directive(document, image, key, value, type=type)
                    # Also update document.settings with the new info.
                    document.settings.image_uris[section+'.'+key] = value
            else:
                raise ValueError, "couldn't save data in {location}".format(location=location)

        # Save immediately, so as to not forget the location of an uploaded image
        if self.should_save_file():
            print "Saving file with new data"
            file(self.filename, 'w').write(self.text)

    def get_info(self, document, section, key, location=None):
        location = location or POSTS_LOCATION
        if self.data_storage in ['both', 'file']:
            if location == POSTS_LOCATION:
                #print("Looking up {key} and finding {value}".format(key=key, value=document.settings.bibliographic_fields[key]))
                return document.settings.bibliographic_fields[key]
            elif location == IMAGES_LOCATION:
                try:
                    return document.settings.image_uris[section+'.'+key]
                except KeyError:
                    pass
                if self.data_storage == 'file':
                    raise ValueError, "uh oh.. don't know what the image URI should be for {uri}".format(uri=section)

        return self.search_configs(location(), section, key)

    def has_info(self, document, section, key, location=None):
        location = location or POSTS_LOCATION
        if self.data_storage in ['both', 'file']:
            if location == POSTS_LOCATION:
                return (key in document.settings.bibliographic_fields)
            elif location == IMAGES_LOCATION:
                try:
                    return document.settings.image_uris[section+'.'+key]
                except KeyError:
                    pass

        class NO_DEFAULT:
            pass

        return self.search_configs(location(), section, key, NO_DEFAULT) is not NO_DEFAULT


    def replace_field(self, document, key, value):
        '''Inserts a bibliographic field into the header of an RST document.

        Replaces an existing field of the same name.'''
        keystring = ':{key}:'.format(key=key)
        new_line = '{keystring} {value}'.format(keystring=keystring, value=value.encode('utf8'))

        lines = self.text.split('\n')
        for i in range(len(lines)):
            if lines[i].strip() == '':
                # Didn't have that field
                lines.insert(i, new_line)
                break
            if lines[i].startswith(keystring):
                lines[i] = new_line
                break

        self.text = '\n'.join(lines)

    def get_indent(self, s):
        r = re.compile('^\s*')
        m = r.search(s)
        return m.end()

    def replace_directive(self, document, uri, key, value, type='image'):
        '''Add a field to a URL-based directive.'''
        r = re.compile('{name}::\s+({uri})'.format(name=type, uri = re.escape(uri)))
        lines = self.text.split('\n')

        for i in range(len(lines)):
            if r.search(lines[i]):
                n = self.get_indent(lines[i])
                # FIXME: check if it's already there
                lines.insert(i+1, ((n+3)*' ')+':{key}: {value}'.format(key=key, value=value))

        self.text = '\n'.join(lines)

    def should_save_file(self):
        data_storage = self.config.get('config', 'data_storage')
        save_to_file = data_storage in ['both', 'file']
        return self.text != file(self.filename).read() and save_to_file

    def create_client(self, url, username, password):
        wp = wordpresslib.WordPressClient(url, username, password)
        config = self.config

        if not config.has_option('account', 'blog_id') or config.get('account', 'blog_id') == '':
            blogs = list(wp.get_users_blogs())
            blog = blogs[0]
            print "Arbitrarily picking first blog: %s at %s"%(blog.name, blog.url)
            wp.selectBlog(blog.id)
        else:
            blog_id = config.get_int('account', 'blog_id')
            print "Using blog id %s from config" % (blog_id,)
            wp.selectBlog(blog_id)

        return wp

    def run(self, *args, **kwargs):
        if not args: args = sys.argv[1:]
        self.parse_args(args)
        config = self.config

        url = config.get('account', 'url')
        username = config.get('account', 'username')
        password = config.get('account', 'password')
        if config.has_option('account', 'verbose'):
            self.VERBOSE = config.get('account', 'verbose')

        print "Connecting to WP server at", url
        wp = None
        if not self.preview:
            self.wp = wp = self.create_client(url, username, password)

        if self.VERBOSE:
            options = wp.get_options()
            print "Talking to %s version %s"%(options['software_name'], options['software_version'])

        if not self.preview:
            if self.list_tags:
                return self.run_list_tags()
            elif self.list_categories:
                return self.run_list_categories()

        with file(self.filename) as f:
            self.text = text = f.read()

        # self.text is the version we eventually save;
        # text is the version we render
        text = text+self._known_link_stanza()
        reader = WordPressReader(self.preview)

        used_images = {}
        writer = docutils.writers.html4css1.Writer()
        writer.translator_class = MyTranslator

        image_uris = {}

        output = core.publish_parts(source=text, writer=writer,
                                    reader=reader,
                                    settings_overrides={
                'wordpress_instance' : wp,
                'application': self,
                'image_uris': image_uris,
                'used_images': used_images,
                # FIXME: probably a nicer way to do this
                'filename': self.filename,
                })
        #print yaml.dump(output, default_flow_style=False)
        body = output['body']

        if self.preview:
            return self.run_preview(output)


        fields = reader.document.settings.bibliographic_fields

        categories = [wordpresslib.WordPressCategory(name=cat) for cat in fields['categories']]
        tags = []
        for tag in fields.get('tags', []):
            if wp.has_tag(tag):
                tags.append(wp.get_tag(tag))
            else:
                tags.append(wordpresslib.WordPressTag(name=tag))
        # WP will replace \n with <br/>, which isn't what RST is
        # designed for. We short-circuit this by replacing all newlines
        # with spaces, which ought to be safe.
        body = utils.replace_newlines(body)

        new_post_data = {
            'title' : unicode(fields['title']),
            'categories': categories,
            'tags': tags,
            'description': body,
            }

        # Publish priority:
        # 1. --publish/--no-publish
        # 2. :publish: yes
        # 3. config publish_default
        # 4. default to false
        publish = None
        if publish == None: publish = self.publish
        if publish == None:
            publish = fields.get('publish', None)
            if publish == 'yes': publish = True
        if publish == None and config.has_option('config', 'publish_default'):
            publish = config.getboolean('config', 'publish_default')
        if publish == None: publish = False

        if self.has_info(reader.document, "post " + self.filename, 'id'):
            post_id = self.get_info(reader.document, "post " + self.filename, 'id')
            post_id = unicode(post_id)
            post = wp.get_post(post_id)

            post.__dict__.update(new_post_data)

            if fields.get('type') == 'page':
                wp.edit_page(post_id, post, publish)
            else:
                wp.edit_post(post_id, post, publish)

        else:
            # FIXME: fields['date']
            user = wp.get_user_info()
            new_post_data['user'] = user.id
            post = wordpresslib.WordPressPost(**new_post_data)

            if fields.get('type') == 'page':
                post_id = wp.new_page(post, publish)
            else:
                post_id = wp.new_post(post, publish)
            self.save_info(reader.document, "post " + self.filename,
                           'id', str(post_id))

        self.save_info(reader.document, "post " + self.filename,
                       'title', fields['title'])

        for image_uri in used_images:
            self.save_info(reader.document, "image " + image_uri,
                           'used in ' + str(post_id), fields['title'], location=IMAGES_LOCATION)

    def run_preview(self, output):
        body = output['body']
        fp = tempfile.NamedTemporaryFile(suffix='-rst2wp-preview.html',
                                         delete=False)
        fp.write(body.encode('utf8'))
        fp.close()
        browser = os.getenv('BROWSER') or 'sensible-browser'
        subprocess.call([browser, fp.name])
        # FIXME: better way to know when it gets loaded?
        time.sleep(5)

        os.unlink(fp.name)

    def run_list_tags(self):
        tags = self.wp.get_tags()
        for tag in tags:
            print '{name} (id {id}): {count} posts'.format(**tag.__dict__)

    def run_list_categories(self):
        categories = self.wp.get_categories()
        for category in tags:
            print '{name} (id {id})'.format(**tag.__dict__)

if __name__ == '__main__':
    try:
        Rst2Wp().run()
    except UsageError, u:
        print u.error_message()
        sys.exit(1)
    finally:
        for filename in TEMP_FILES:
            os.unlink(filename)
