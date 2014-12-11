#!/usr/bin/env python
import csv
import itertools
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

class RST(Processor):
    CORNER = '+'
    DELIM = '|'
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
            " %-*s  " % (length, cell.replace('|', '\\|'))
            for length, cell in zip(self.lengths, row)
            ) + self.DELIM

    def post(self):
        yield self.border

class Markdown(Processor):
    DELIM = '|'

    def process_header_row(self, row):
        for result in self.process_regular_row(row):
            yield result
        yield self.DELIM + self.DELIM.join(
            " %s " % ('-' * (length+1))
            for length in self.lengths
            ) + self.DELIM

    def process_regular_row(self, row):
        yield self.DELIM + self.DELIM.join(
            " %-*s  " % (length, cell.replace('|', '\\|'))
            for length, cell in zip(self.lengths, row)
            ) + self.DELIM

def build_parser():
    parser = OptionParser(
        usage="%prog [options] file1.csv [file2.csv ...]",
        description="Convert one or more .csv files to reST tables",
        )
    parser.add_option("-l", "--local",
        help="Write them to the local directory "
            "rather than in the same location as the source. "
            "WARNING: May produce filename conflicts and bail early",
        dest="local",
        action="store_true",
        default=False,
        )
    parser.add_option("-d", "--delimiter",
        help="The delimiter to use.",
        dest="delimiter",
        action="store",
        default=',',
        )
    return parser

def main(args):
    parser = build_parser()
    options, args = parser.parse_args(args)
    if not args:
        sys.stderr.write("No file-names specified\n")
        parser.print_help()
        return ERROR
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
                processor = RST(r)
                for row in processor:
                    print repr(row)
            finally:
                f.close()

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
