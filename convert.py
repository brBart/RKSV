#!/usr/bin/env python2.7

###########################################################################
# Copyright 2017 ZT Prentner IT GmbH
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
###########################################################################

from builtins import int
from builtins import range

import gettext
_ = gettext.translation('rktool', './lang', fallback=True).gettext

import sys

import depexport
import depparser
import receipt
import utils

def usage():
    print("Usage: ./convert.py json2csv")
    print("       ./convert.py csv2json")
    sys.exit(0)

if __name__ == "__main__":
    import gettext
    gettext.install('rktool', './lang', True)

    if len(sys.argv) != 2:
        usage()

    recs = list()
    if sys.argv[1] == 'json2csv':
        exporter = depexport.CSVExporter()
        parser = depparser.CertlessStreamDEPParser(sys.stdin)
        for chunk in parser.parse(depparser.depParserChunkSize()):
            for recs, cert, cert_list in chunk:
                exporter.addGroup([ receipt.Receipt.fromJWSString(
                    depparser.expandDEPReceipt(r)) for r in recs ], cert, cert_list)
    elif sys.argv[1] == 'csv2json':
        next(sys.stdin)
        for row in sys.stdin:
            recs.append(receipt.Receipt.fromCSV(row.strip()))
        exporter = depexport.JSONExporter()
        exporter.addGroup(recs)
    else:
        usage()

    print(exporter.export())
