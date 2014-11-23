import re


def replace_newlines(txt):
    '''Eliminate newlines from txt.

    Wordpress's post API tries to format text, turns newlines into
    <br/>s, etc. Since we're giving it already-formatted HTML,
    there's no need for that behavior. Instead we turn newlines
    into spaces, which is safe because HTML mandates that multiple
    whitespaces are identical to one whitespace.

    The only time this doesn't work is when handling <pre>
    elements. Thus, we handle those specially.'''
    start = 0  # start eliminating from here
    pre = re.compile("<pre( [^>]*)?>")  # actual parsing? fuck that noise!
    end_pre = re.compile("</pre>")  # whew, no </pre class="...">

    # Loop invariant: start is the index at which text has already
    # been processed. This means it either ends a </pre> or 0.
    #
    # <pre>hi there</pre>abcde fgh ijklm<pre>foo bar baz</pre>nopqrstu
    # start -------------|
    # m.start() ------------------------|
    while True:
        m = pre.search(txt, start)
        if not m: break

        txt = (txt[:start] +  # already replaced
               txt[start:m.start()].replace('\n', ' ') +  # replace till next <pre>
               txt[m.start():])  # <pre> and afterwards

        # Indexes could change between start and m.start(), since
        # that's where we replace text. (They don't, but whatever.)
        # So to advance start, we search starting from start (instead
        # of m.start()).
        m = end_pre.search(txt, start)

        if not m: break  # couldn't keep the invariant
        start = m.end()

    # No <pre> blocks between start and end of string, but still
    # have to replace newlines there
    txt = txt[:start] + txt[start:].replace('\n', ' ')
    return txt


def list_wrap(obj):
    if isinstance(obj, list): return obj
    return [obj]

# Stolen from Dive Into Python: http://diveintopython3.org/your-first-python-program.html

SUFFIXES = {1000: ['KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'],
            1024: ['KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB']}


def approximate_size(size, a_kilobyte_is_1024_bytes=True):
    '''Convert a file size to human-readable form.

    Keyword arguments:
    size -- file size in bytes
    a_kilobyte_is_1024_bytes -- if True (default), use multiples of 1024
                                if False, use multiples of 1000

    Returns: string

    '''
    if size < 0:
        raise ValueError('number must be non-negative')

    multiple = 1024 if a_kilobyte_is_1024_bytes else 1000
    for suffix in SUFFIXES[multiple]:
        size /= multiple
        if size < multiple:
            return '{0:.1f} {1}'.format(size, suffix)

    raise ValueError('number too large')


PRINTING_COLORS = {'gray': 30,
                   'red': 31,
                   'green': 32,
                   'yellow': 33,
                   'blue': 34,
                   'magenta': 35,
                   'cyan': 36,
                   'white': 37,
                   'crimson': 38,
                   'high-red': 41,
                   'high-green': 42,
                   'high-brown': 43,
                   'high-blue': 44,
                   'high-magenta': 45,
                   'high-cyan': 46,
                   'high-gray': 47,
                   'high-crimson': 48,}


def color_print(text, color):
    template = '\033[1;%dm%s\033[1;m'

    print(template % (PRINTING_COLORS[color], text))

    # print '\033[1;30mGray like Ghost\033[1;m'
    # 2print '\033[1;31mRed like Radish\033[1;m'
    # 3print '\033[1;32mGreen like Grass\033[1;m'
    # 4print '\033[1;33mYellow like Yolk\033[1;m'
    # 5print '\033[1;34mBlue like Blood\033[1;m'
    # 6print '\033[1;35mMagenta like Mimosa\033[1;m'
    # 7print '\033[1;36mCyan like Caribbean\033[1;m'
    # 8print '\033[1;37mWhite like Whipped Cream\033[1;m'
    # 9print '\033[1;38mCrimson like Chianti\033[1;m'
    # 10print '\033[1;41mHighlighted Red like Radish\033[1;m'
    # 11print '\033[1;42mHighlighted Green like Grass\033[1;m'
    # 12print '\033[1;43mHighlighted Brown like Bear\033[1;m'
    # 13print '\033[1;44mHighlighted Blue like Blood\033[1;m'
    # 14print '\033[1;45mHighlighted Magenta like Mimosa\033[1;m'
    # 15print '\033[1;46mHighlighted Cyan like Caribbean\033[1;m'
    # 16print '\033[1;47mHighlighted Gray like Ghost\033[1;m'
    # 17print '\033[1;48mHighlighted Crimson like Chianti\033[1;m'