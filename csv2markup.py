#!/usr/bin/env python
import cgi
import csv
import itertools
import os
import sys
from optparse import OptionParser

SUCCESS, ERROR = range(2)

class Processor(object):
    def __init__(self, stream, **options):
        self.data = [row for row in stream if row]
        self.options = options
        self.lengths = [
            max(len(val) for val in col)
            for col
            in itertools.izip(*self.data)
            ]
    def __iter__(self):
        i = iter(self.data)
        for result in self.process_header_row(next(i)):
            yield result
        for row in i:
            for result in self.process_regular_row(row):
                yield result
        for result in self.post():
            yield result
    def process_header_row(self, row): return []
    def process_regular_row(self, row): return []
    def post(self): return []
    def clean(self, s):
        # do any requisite cleaning/escaping of strings
        # TODO non-HTML processors need to have better
        # escaping. They're mostly untested with
        # strange data
        return s

class RST(Processor):
    extension = ".rst"
    CORNER = '+'
    DELIM = '|'

    def clean(self, s):
        return s.replace("\\", "\\\\").replace("|", "\\|")

    def __init__(self, *args, **kwargs):
        super(RST, self).__init__(*args, **kwargs)
        for field, char in (
                ("border", "-"),
                ("separator", "="),
                ):
            value= self.CORNER + self.CORNER.join(
                "%s" % (char * (length+3))
                for length in self.lengths
                ) + self.CORNER
            setattr(self, field, value)

    def process_header_row(self, row):
         yield self.border
         for item in self.process_regular_row(row):
            yield item
         yield self.separator

    def process_regular_row(self, row):
        yield self.DELIM + self.DELIM.join(
            " %-*s  " % (length, self.clean(cell))
            for length, cell in zip(self.lengths, row)
            ) + self.DELIM

    def post(self):
        yield self.border

class Markdown(Processor):
    extension = ".md"
    DELIM = '|'

    def clean(self, s):
        return s.replace("\\", "\\\\").replace("|", "\\|")

    def process_header_row(self, row):
        for result in self.process_regular_row(row):
            yield result
        yield self.DELIM + self.DELIM.join(
            " %s " % ('-' * (length+1))
            for length in self.lengths
            ) + self.DELIM

    def process_regular_row(self, row):
        yield self.DELIM + self.DELIM.join(
            " %-*s  " % (length, self.clean(cell))
            for length, cell in zip(self.lengths, row)
            ) + self.DELIM

class Dokuwiki(Processor):
    extension = ".doku"
    DELIM = '|'
    HEADER_DELIM = '^'
    def process_header_row(self, row):
        yield self.HEADER_DELIM + self.HEADER_DELIM.join(
            " %-*s  " % (length, self.clean(cell))
            for length, cell in zip(self.lengths, row)
            ) + self.HEADER_DELIM

    def process_regular_row(self, row):
        yield self.DELIM + self.DELIM.join(
            " %-*s  " % (length, self.clean(cell))
            for length, cell in zip(self.lengths, row)
            ) + self.DELIM

class HTML(Processor):
    extension = ".html"
    def clean(self, s):
        return cgi.escape(s)

    def process_header_row(self, row):
        yield "<table>"
        yield "<thead>"
        yield "<tr>" + "".join(
            "<th>%s</th>" % self.clean(cell)
            for cell in row
            ) + "</tr>"
        yield "</thead>"
        yield "<tbody>"

    def process_regular_row(self, row):
        yield "<tr>" + "".join(
            "<td>%s</td>" % self.clean(cell)
            for cell in row
            ) + "</tr>"

    def post(self):
        yield "</tbody>"
        yield "</table>"

FORMATS = {
    # Name -> (class, [aliases])
    "dokuwiki": (Dokuwiki, ["dok", "doku", "dw"]),
    "markdown": (Markdown, ["md"]),
    "rst": (RST, ["rest", "restructured text", "restructuredtext"]),
    "html": (HTML, []),
    }
# process the aliases
tmp = {}
for format, details in FORMATS.iteritems():
    (cls, aliases) = details
    for alias in aliases:
        tmp[alias] = details
FORMATS.update(tmp)
del tmp

def build_parser():
    parser = OptionParser(
        usage="%prog [options] file1.csv [file2.csv ...]",
        description="Convert one or more .csv files "
            "to the table syntax of various markup languages",
        )
    parser.add_option("-f", "--format", "--fmt",
        help="The output format. One of %s" % (
            ', '.join(sorted(FORMATS.keys()))
            ),
        dest="format",
        action="store",
        choices=FORMATS.keys(),
        default=False,
        )
    parser.add_option("-o", "--stdout",
        help="Write to stdout rather than files",
        dest="stdout",
        action="store_true",
        default=False,
        )
    parser.add_option("-l", "--local",
        help="Write them to the local directory "
            "rather than in the same location as the source. "
            "WARNING: May produce filename conflicts and bail early",
        dest="local",
        action="store_true",
        default=False,
        )
    parser.add_option("--force",
        help="Force overwriting of existing output files",
        dest="force",
        action="store_true",
        default=False,
        )
    parser.add_option("-d", "--delimiter",
        help="The delimiter to use.",
        dest="delimiter",
        action="store",
        default=',',
        )
    parser.set_defaults(
        format=None,
        )
    return parser

def main(args):
    parser = build_parser()
    options, args = parser.parse_args(args)
    issue = None

    if not args: issue = "No filename specified"
    if not options.format: issue = "No format specified"

    if issue:
        sys.stderr.write("%s\n" % issue)
        parser.print_help()
        return ERROR

    processor, _aliases = FORMATS[options.format]
    for fname in args:
        try:
            f = file(fname, "rb")
        except IOError:
            sys.stderr.write("Could not open %s\n" % fname)
        else:
            params = dict(
                delimiter=options.delimiter,
                )
            r = csv.reader(f, **params)
            try:
                if options.stdout:
                    output_file = sys.stdout
                else:
                    output_name, _ = os.path.splitext(fname)
                    output_name = (
                        os.path.basename(output_name) +
                        processor.extension
                        )
                    if not options.local:
                        output_name = os.path.join(
                            os.path.dirname(fname),
                            output_name,
                            )
                    if os.path.exists(output_name):
                        if not options.force:
                            sys.stderr.write("%s already exists. Skipping.\n" % output_name)
                            continue
                        if not os.path.isfile(output_name):
                            sys.stderr.write(
                                "%s already exists and isn't a file. Skipping.\n"
                                % output_name)
                            continue
                    output_file = file(output_name, "wb")
                try:
                    for row in processor(r):
                        output_file.write(row)
                        output_file.write("\n")
                finally:
                    if not options.stdout:
                        output_file.close()
            finally:
                f.close()

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
