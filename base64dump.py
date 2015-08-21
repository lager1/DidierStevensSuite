#!/usr/bin/env python

__description__ = 'Extract base64 strings from file'
__author__ = 'Didier Stevens'
__version__ = '0.0.2'
__date__ = '2015/07/28'

"""

Source code put in public domain by Didier Stevens, no Copyright
https://DidierStevens.com
Use at your own risk

History:
  2015/06/30: start
  2015/07/01: added header
  2015/07/14: 0.0.2: added option -n
  2015/07/28: fixed option -n

Todo:
"""

import optparse
import sys
import os
import zipfile
import cStringIO
import binascii
import textwrap
import re
import hashlib
import string
import math

dumplinelength = 16
MALWARE_PASSWORD = 'infected'

def PrintManual():
    manual = '''
Manual:

base64dump is a program that extracts and decodes base64 strings found inside the provided file. base64dump looks for sequences of base64 characters in the provided file and tries to decode them. The result is displayed in a table like this:

ID  Size    BASE64           Decoded          MD5 decoded
--  ----    ------           -------          -----------
 1:  400728 TVqQAAMAAAAEAAAA MZ.............. d611941e0d24cb6b59c7b6b2add4fd8f
 2:      36 U2NyaXB0aW5nLkZp Scripting.FileSy a1c46f599699a442a5ae0454467f6d63
 3:       4 exel             {..              f1b1127ffb842243f9a03e67036d4bb6

The first column (ID) is the number (ID) assigned to the datastream by base64dump. This ID is used when selecting a datastream for further analysis with option -s.
The second column (Size) is the length of the base64 string.
The third column (BASE64) is the start of the base64 string.
The fourth column (Decoded) is the ASCII dump of the start of the decoded base64 string.
The fifth column (MD5 decoded) is the MD5 hash of the decoded base64 string.

Select a datastream for further analysis with option -s followed by the ID number of the datastream (or a for all). For example -s 2:

Info:
 MD5: d611941e0d24cb6b59c7b6b2add4fd8f
 Filesize: 300544
 Entropy: 6.900531
 Magic HEX: 4d5a9000
 Magic ASCII: MZ..
 Null bytes: 41139
 Control bytes: 38024
 Whitespace bytes: 9369
 Printable bytes: 122967
 High bytes: 89045

This displays information for the datastream, like the entropy of the datastream.

The selected stream can be dumped (-d), hexdumped (-x) or ASCII dumped (-a). Use the dump option (-d) to extract the stream and save it to disk (with file redirection >) or to pipe it (|) into the next command.
Here is an example of an ascii dump (-s 2 -a):

00000000: 53 63 72 69 70 74 69 6E 67 2E 46 69 6C 65 53 79  Scripting.FileSy
00000010: 73 74 65 6D 4F 62 6A 65 63 74                    stemObject

You can also specify the minimum length of the decoded base64 datastream with option -n. 
'''
    for line in manual.split('\n'):
        print(textwrap.fill(line, 78))

#Convert 2 Bytes If Python 3
def C2BIP3(string):
    if sys.version_info[0] > 2:
        return bytes([ord(x) for x in string])
    else:
        return string

# CIC: Call If Callable
def CIC(expression):
    if callable(expression):
        return expression()
    else:
        return expression

# IFF: IF Function
def IFF(expression, valueTrue, valueFalse):
    if expression:
        return CIC(valueTrue)
    else:
        return CIC(valueFalse)

def File2String(filename):
    try:
        f = open(filename, 'rb')
    except:
        return None
    try:
        return f.read()
    except:
        return None
    finally:
        f.close()

class cDumpStream():
    def __init__(self):
        self.text = ''

    def Addline(self, line):
        if line != '':
            self.text += line + '\n'

    def Content(self):
        return self.text

def HexDump(data):
    oDumpStream = cDumpStream()
    hexDump = ''
    for i, b in enumerate(data):
        if i % dumplinelength == 0 and hexDump != '':
            oDumpStream.Addline(hexDump)
            hexDump = ''
        hexDump += IFF(hexDump == '', '', ' ') + '%02X' % ord(b)
    oDumpStream.Addline(hexDump)
    return oDumpStream.Content()

def CombineHexAscii(hexDump, asciiDump):
    if hexDump == '':
        return ''
    return hexDump + '  ' + (' ' * (3 * (dumplinelength - len(asciiDump)))) + asciiDump

def HexAsciiDump(data):
    oDumpStream = cDumpStream()
    hexDump = ''
    asciiDump = ''
    for i, b in enumerate(data):
        if i % dumplinelength == 0:
            if hexDump != '':
                oDumpStream.Addline(CombineHexAscii(hexDump, asciiDump))
            hexDump = '%08X:' % i
            asciiDump = ''
        hexDump+= ' %02X' % ord(b)
        asciiDump += IFF(ord(b) >= 32, b, '.')
    oDumpStream.Addline(CombineHexAscii(hexDump, asciiDump))
    return oDumpStream.Content()

#Fix for http://bugs.python.org/issue11395
def StdoutWriteChunked(data):
    while data != '':
        sys.stdout.write(data[0:10000])
        try:
            sys.stdout.flush()
        except IOError:
            return
        data = data[10000:]

def IfWIN32SetBinary(io):
    if sys.platform == 'win32':
        import msvcrt
        msvcrt.setmode(io.fileno(), os.O_BINARY)

def File2Strings(filename):
    try:
        f = open(filename, 'r')
    except:
        return None
    try:
        return map(lambda line:line.rstrip('\n'), f.readlines())
    except:
        return None
    finally:
        f.close()

def ProcessAt(argument):
    if argument.startswith('@'):
        strings = File2Strings(argument[1:])
        if strings == None:
            raise Exception('Error reading %s' % argument)
        else:
            return strings
    else:
        return [argument]

def ExpandFilenameArguments(filenames):
    return list(collections.OrderedDict.fromkeys(sum(map(glob.glob, sum(map(ProcessAt, filenames), [])), [])))

def AsciiDump(data):
    return ''.join([IFF(ord(b) >= 32, b, '.') for b in data])

def Magic(data):
    magicPrintable = ''
    magicHex = ''
    for iter in range(4):
        if len(data) >= iter + 1:
            if ord(data[iter]) >= 0x20 and ord(data[iter]) < 0x7F:
                magicPrintable += data[iter]
            else:
                magicPrintable += '.'
            magicHex += '%02x' % ord(data[iter])
    return magicPrintable, magicHex

def CalculateByteStatistics(dPrevalence):
    sumValues = sum(dPrevalence.values())
    countNullByte = dPrevalence[0]
    countControlBytes = 0
    countWhitespaceBytes = 0
    for iter in range(1, 0x21):
        if chr(iter) in string.whitespace:
            countWhitespaceBytes += dPrevalence[iter]
        else:
            countControlBytes += dPrevalence[iter]
    countControlBytes += dPrevalence[0x7F]
    countPrintableBytes = 0
    for iter in range(0x21, 0x7F):
        countPrintableBytes += dPrevalence[iter]
    countHighBytes = 0
    for iter in range(0x80, 0x100):
        countHighBytes += dPrevalence[iter]
    entropy = 0.0
    for iter in range(0x100):
        if dPrevalence[iter] > 0:
            prevalence = float(dPrevalence[iter]) / float(sumValues)
            entropy += - prevalence * math.log(prevalence, 2)
    return sumValues, entropy, countNullByte, countControlBytes, countWhitespaceBytes, countPrintableBytes, countHighBytes

def CalculateFileMetaData(data):
    dPrevalence = {}
    for iter in range(256):
        dPrevalence[iter] = 0
    for char in data:
        dPrevalence[ord(char)] += 1

    fileSize, entropy, countNullByte, countControlBytes, countWhitespaceBytes, countPrintableBytes, countHighBytes = CalculateByteStatistics(dPrevalence)
    magicPrintable, magicHex = Magic(data[0:4])
    return hashlib.md5(data).hexdigest(), magicPrintable, magicHex, fileSize, entropy, countNullByte, countControlBytes, countWhitespaceBytes, countPrintableBytes, countHighBytes

def BASE64Dump(filename, options):
    if filename == '':
        IfWIN32SetBinary(sys.stdin)
        oStringIO = cStringIO.StringIO(sys.stdin.read())
    elif filename.lower().endswith('.zip'):
        oZipfile = zipfile.ZipFile(filename, 'r')
        oZipContent = oZipfile.open(oZipfile.infolist()[0], 'r', C2BIP3(MALWARE_PASSWORD))
        oStringIO = cStringIO.StringIO(oZipContent.read())
        oZipContent.close()
        oZipfile.close()
    else:
        oStringIO = cStringIO.StringIO(open(filename, 'rb').read())

    if options.dump:
        DumpFunction = lambda x:x
        IfWIN32SetBinary(sys.stdout)
    elif options.hexdump:
        DumpFunction = HexDump
    elif options.asciidump:
        DumpFunction = HexAsciiDump
    else:
        DumpFunction = None

    if options.select == '':
        formatString = '%-2s  %-7s %-16s %-16s %-32s'
        columnNames = ('ID', 'Size', 'BASE64', 'Decoded', 'MD5 decoded')
        print(formatString % columnNames)
        print(formatString % tuple(['-' * len(s) for s in columnNames]))

    counter = 1
    data = oStringIO.read()
    for base64string in re.findall('[ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/]+={0,2}', data):
        if len(base64string) % 4 == 0:
            try:
                base64data = binascii.a2b_base64(base64string)
            except:
                continue
            if options.number and len(base64data) < options.number:
                continue
            if options.select == '':
                print('%2d: %7d %-16s %-16s %s' % (counter, len(base64string), base64string[0:16], AsciiDump(base64data[0:16]), hashlib.md5(base64data).hexdigest()))
            elif ('%s' % counter) == options.select or options.select == 'a':
                if DumpFunction == None:
                    filehash, magicPrintable, magicHex, fileSize, entropy, countNullByte, countControlBytes, countWhitespaceBytes, countPrintableBytes, countHighBytes = CalculateFileMetaData(base64data)
                    print('Info:')
                    print(' %s: %s' % ('MD5', filehash))
                    print(' %s: %d' % ('Filesize', fileSize))
                    print(' %s: %f' % ('Entropy', entropy))
                    print(' %s: %s' % ('Magic HEX', magicHex))
                    print(' %s: %s' % ('Magic ASCII', magicPrintable))
                    print(' %s: %s' % ('Null bytes', countNullByte))
                    print(' %s: %s' % ('Control bytes', countControlBytes))
                    print(' %s: %s' % ('Whitespace bytes', countWhitespaceBytes))
                    print(' %s: %s' % ('Printable bytes', countPrintableBytes))
                    print(' %s: %s' % ('High bytes', countHighBytes))
                else:
                    StdoutWriteChunked(DumpFunction(base64data))
            counter += 1

    return 0

def Main():
    oParser = optparse.OptionParser(usage='usage: %prog [options] [file]\n' + __description__, version='%prog ' + __version__)
    oParser.add_option('-m', '--man', action='store_true', default=False, help='Print manual')
    oParser.add_option('-s', '--select', default='', help='select item nr for dumping (a for all)')
    oParser.add_option('-d', '--dump', action='store_true', default=False, help='perform dump')
    oParser.add_option('-x', '--hexdump', action='store_true', default=False, help='perform hex dump')
    oParser.add_option('-a', '--asciidump', action='store_true', default=False, help='perform ascii dump')
    oParser.add_option('-n', '--number', type=int, default=None, help='minimum number of bytes in decoded base64 data')
    (options, args) = oParser.parse_args()

    if options.man:
        oParser.print_help()
        PrintManual()
        return 0

    if len(args) > 1:
        oParser.print_help()
        print('')
        print('  Source code put in the public domain by Didier Stevens, no Copyright')
        print('  Use at your own risk')
        print('  https://DidierStevens.com')
        return 0
    elif len(args) == 0:
        return BASE64Dump('', options)
    else:
        return BASE64Dump(args[0], options)

if __name__ == '__main__':
    sys.exit(Main())
