#!/usr/bin/python

SCRIPT_INFO = \
""" Script that makes the output of readelf more useful. Use options to determine how the symbol
table is ordered. It can either be in alphabetical order, or listed by type then size.

readelf is a program in binutils that spits out information about a program from the .elf file. 
This includes all functions, their location in memory, their size, data etc.

TODO: print to console by default
TODO: add options (check readelf options first):
    a: output everything
    --source_files: output source files used to build elf
    
TODO: finish parseSectionHeaders, replace ndx column with sections, add up section sizes properly
TODO: ARRRGGGHH!!! anything static seems to appear as 'NOTYPE' with no size. How is this useful?
        Where did the data go??? It's still there (check the map file) but has no label. Need some
        way to ensure that all bytes are accounted for.
TODO: Figure out how readelf displays discarded sections,functions and data. If it doesn't show
        them, it'd be useful to get this info, from the map file perhaps.
"""

import sys, subprocess, argparse

def main():
    args = getArgParser().parse_args()
    readelf_output = runReadlf(args.source)
    sym, start, end = parseReadelfOutput(readelf_output)
    
    if args.o == None:
        args.o = args.source + ".readelf_nice"

    printParsedInfoToFile(readelf_output, args.o, sym, start, end)
        
def getArgParser():
    parser = argparse.ArgumentParser(description=SCRIPT_INFO)
    parser.add_argument("source", help="input elf file")
    parser.add_argument("-o", help="output filename")
    parser.add_argument("-v", help="verbose console output")
    return parser
    
# Run binutils' readelf. Returns the output filename
def runReadlf(elf_filename):
    readelf_output_filename = elf_filename + ".readelf"

    ofile = open(readelf_output_filename, 'w')
    result = subprocess.call(['readelf', '-a', '-W', elf_filename],
                              stdout=ofile)
    ofile.close()
    
    if result == 0:
        return readelf_output_filename
    else:
        return None
        
def parseReadelfOutput(path):
    infile = open(path)
    sym, start, end = parseSymbolTable(infile)
    infile.close()
    return sym, start, end
    
# parse the symbol table of readelf's output, return all symbols
def parseSymbolTable(data):
    symbols = []
    symbol_table_started = False
    line_counter = 0
    symbol_table_start = 0  # first line of symbol table
    symbol_table_end = 0
    for line in data:
        line_counter += 1
        if symbol_table_started:
            if line_counter > symbol_table_start + 1:
                if len(line) < 4:
                    # this is the end of the symbol table
                    symbol_table_end = line_counter
                    break
                else:
                    symbols.append(parseSymbolInfo(line))
                    continue
        # symbol table starts with 'Symbol table...'
        elif line.startswith('Symbol table'):
            symbol_table_started = True
            symbol_table_start = line_counter
    return symbols, symbol_table_start, symbol_table_end
    
def printParsedInfoToFile(readelf_output_filename, output_filename, symbols,
                            symbols_start_line, symbols_end_line):
    infile = open(readelf_output_filename)
    outfile = open(output_filename, "w")
    
    line_counter = 0
    for line in infile:
        line_counter += 1
        if line_counter == symbols_start_line:
            outfile.write("Symbol table, sorted by type then size\n")
        if line_counter > symbols_start_line and line_counter < symbols_end_line:
            pass
        elif line_counter == symbols_end_line:
            outfile.write(getSymbolsCategorisedAndOrderedString(symbols))
        else:
            outfile.write(line)
            
    print line_counter, "lines written to", output_filename
            
    infile.close()
    outfile.close()
    
def goodSplit(string, delimiter):
    """ Similar to string.split(delimiter) but treats consecutive delimiters as one """
    output = []
    for item in string.split(delimiter):
        if item != '':
            if item[-1] == '\n':
                item = item[:-1]
            output.append(item)
    return output

def getSymbolHeadingsString():
    string = "Num:".rjust(6)
    string += "Value".rjust(11)
    string += "Size".rjust(7)
    string += "Type".rjust(8)
    string += "Bind".rjust(7)
    string += "Vis".rjust(8)
    string += "Ndx".rjust(6)
    string += "  Name"
    return string

# symbol info given in readelf's symbol table
class SymbolInfo():
    num = None        # symbol table number. Useless info...
    value = None       # symbol address (I think)
    size = None        # size in bytes (decimal) (I think)
    type = None     # File, function, section, object, notype...
    bind = None     # Scope?
    vis = None      # what?
    ndx = None      # section header. Given as a number TODO: read the section table and convert
                    # this to the section
    name = None

    def __str__(self):
        return  str(self.num).rjust(6) + \
                str(self.value).rjust(11) + \
                str(self.size).rjust(7) + \
                str(self.type).rjust(8) + \
                str(self.bind).rjust(7) + \
                str(self.vis).rjust(8) + \
                str(self.ndx).rjust(6) + \
                '  ' + str(self.name)

# give this the output of readelf, get a dictionary of section headings
def parseSectionHeaders(data):
    sections = {}
    section_headers_started = False
    for line in data:
        if section_headers_started:
            line_split = goodSplit(line, ' ')
            if len(line_split) < 9: break #this is the end...my only friend
            if '[Nr]' in line_split[0] : continue #column headings

        elif line.startswith('Section Headers'):
            section_headers_started = True
            continue


# give this a line from readelf's symbol table, get a SymbolInfo class back
# TODO: could do with some validity checks here
def parseSymbolInfo(line):
    info = SymbolInfo()
    line_split = goodSplit(line, ' ')

    info.num = line_split[0]
    info.value = line_split[1]
    info.size = int(line_split[2])
    info.type = line_split[3]
    info.bind = line_split[4]
    info.vis = line_split[5]
    info.ndx = line_split[6]
    if len(line_split) == 8:
        # 'section' type symbols don't have names
        # remove line endings
        name = line_split[7].replace('\r','')
        name = name.replace('\n','')
        info.name = name

    return info

def getSymbolsCategorisedAndOrderedString(symbols):
    string = ""
    symbols_dict = categoriseSymbols(symbols)
    for symbol_type in symbols_dict:
        string += getSymbolsOrderedBySizeString(symbols_dict[symbol_type], symbol_type)
    return string

# Get symbols, separated by type into a dictionary
# ie. dict[type] returns a list of symbols of that type
def categoriseSymbols(symbols):
    symboldict = {}
    for symbol in symbols:
        if symbol.type in symboldict:
            symboldict[symbol.type].append(symbol)
        else:
            symboldict[symbol.type] = [symbol]
    return symboldict

# Give a list of symbol objects, get a string of them
# ordered by size (descending). Input the symbol type 
# if you want it in the heading of this string
def getSymbolsOrderedBySizeString(symbols, symbol_type=None):
    string = ""
    
    totalsize = 0
    for symbol in symbols:
        totalsize += symbol.size
        
    string += "########################################################################\n"
    if symbol_type != None:
        string += "Symbols of type '" + str(symbol_type) + "':\n"
    string += "Total size: " + str(totalsize) + "bytes\n\n"
    string += getSymbolHeadingsString() + "\n"
    
    sorted_symbols = sorted(symbols, key = lambda symbol: symbol.size, reverse = True)
    for symbol in sorted_symbols:
        string += str(symbol) + "\n"
    
    return string

if __name__ == "__main__":
    main()
