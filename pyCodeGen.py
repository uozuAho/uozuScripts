script_description = """
===========================================================
Inline code generator, similar to cog & pump. Takes an input
file and runs any code generation sections, which are written
in python.

Example input file text:
-----------------------
Anything any text blah blah

#PYGEN_BEGIN
print "any python code can go here"
gen.write("Generate output with 'gen.write()'\n")
gen.writeln("Generate output with 'gen.writeln()'")
#PYGEN_END
#PYGEN_OUTPUT

Anything...
Text can be substituted using any python that generates
a string, like ${"this"} or ${'t'+'h'+'i'+'s'}

And so forth...
-----------------------


Input file rules
================
 - Characters preceding "#PYGEN_BEGIN" must be consistent
   per line until "#PYGEN_END".
 - Every block that generates code needs a #PYGEN_OUTPUT to
   tell the generator where to put the output code


Simple explanation of operation
===============================

Step 1: pyCodeGen.py extracts python code from input file,
        writes code to a generator file.

Step 2: Generator file is called by pyCodeGen, creating the
        output file.

Step 3: Generator file and pyCodeGen.pyc are deleted


TODO
====
 - Put arg parsing in single function. Use it to set CONFIG
   members.
 - Allow user-configurable code generation block delimiters
   (configure in this file, eg. genBlock_start = "PYGEN_BEGIN")
 - Add option to keep generator script file (default delete)
 - Support input file line-endings (may already "just work"?)


References
==========
cog:  http://nedbatchelder.com/code/cog/
pump: https://code.google.com/p/googletest/wiki/PumpManual

Written by Warwick Stone (uozu.aho@gmail.com)
===========================================================
"""

import argparse, logging, subprocess, shutil, os, re

class CONFIG:
	log_level                 = logging.WARNING
	keep_generator_code       = False # leave generator code in output file
	keep_generator_file       = False # copy generator file to output dir


def main():
	args = getArgParser().parse_args()
	input_file_dir, input_filename = os.path.split(args.input)
	if args.verbose:
		CONFIG.log_level = logging.DEBUG
	logging.basicConfig(level=CONFIG.log_level)
	if args.output == None:
		output_file_path = os.path.join(input_file_dir, getOutputFilename(args.input))
	else:
		output_file_path = args.output
	if args.keep_gencode:
		CONFIG.keep_generator_code = True

	pyCodeGen_script_dir = os.path.dirname(os.path.realpath(__file__))
	generator_file_path = os.path.join(pyCodeGen_script_dir, input_filename + ".gen.py~")

	logging.debug("running in:          " + pyCodeGen_script_dir)
	logging.debug("input_file_dir:      " + input_file_dir)
	logging.debug("input_filename:      " + input_filename)
	logging.debug("generator_file_path: " + generator_file_path)
	logging.debug("output_file_path:    " + output_file_path)

	createGeneratorFile(args.input, generator_file_path, output_file_path)
	subprocess.call(["python", generator_file_path])
	if not CONFIG.keep_generator_code:
		removeCodeGenBlocksFromFile(output_file_path)
	os.remove(generator_file_path)
	os.remove(os.path.join(pyCodeGen_script_dir, "pyCodeGen.pyc"))


def getArgParser():
	parser = argparse.ArgumentParser(description=script_description,
																	 formatter_class=argparse.RawDescriptionHelpFormatter)

	parser.add_argument('input',          help="input file")

	parser.add_argument('-o', '--output',
											help="Output file location. If omitted, the generated file will "
											"be placed in the same directory as the input file, with the same "
											"filename suffixed with '_gen'.")

	parser.add_argument('-v', '--verbose', action='store_true', help="Verbose output")

	parser.add_argument('-k', '--keep_gencode', action='store_true',
											help="Generator code is left in the output file.")
	return parser


def getOutputFilename(input_path):
	""" Return the input filename with '_gen' appended before
			the extension. For example:

			"/some/file.txt" --> "file_gen.txt"
	"""
	filename = os.path.basename(input_path)
	name, ext = os.path.splitext(filename)
	return name + "_gen" + ext


class Generator:
	""" Generator class used by the generator file. Stores all
			strings generated within the generator file, then writes
			them to file once the end of the generator file is reached.
	"""
	def __init__(self, in_path, out_path):
		self.in_path = in_path
		self.out_path = out_path
		self._current_output_string = ""

		self.output_block_count = 0
		self.output_inline_count = 0

		self.generated_blocks = []
		self.generated_inlines = []

	def write(self, string):
		self._current_output_string += str(string)

	def writeln(self, string):
		self._current_output_string += str(string) + "\n"

	def appendGeneratedBlock(self):
		""" Add the currently generated string to the internal list
		of generated strings which will be inserted into the output
		file later. """
		self.generated_blocks.append(self._current_output_string)
		self._current_output_string = ""

	def	_getNextGeneratedBlock(self):
		ret = self.generated_blocks[self.output_block_count]
		self.output_block_count += 1
		return ret

	def appendInline(self, text):
		self.generated_inlines.append(str(text))

	def substituteInlineExprs(self, line):
		return re.sub("\$\{(.+?)\}", self._getNextInline, line)

	def _getNextInline(self, matchobj):
		ret = self.generated_inlines[self.output_inline_count]
		self.output_inline_count += 1
		return ret

	def end(self):
		logging.debug("All blocks and inlines generated.")
		logging.debug("Blocks:")
		for block in self.generated_blocks:
			logging.debug(block)
		logging.debug("")
		logging.debug("Inlines:")
		for inline in self.generated_inlines:
			logging.debug(inline)
		infile = open(self.in_path)
		outfile = open(self.out_path,'w')

		for line in infile:
			block_output = False
			if "#PYGEN_OUTPUT" in line:
				block_output = True

			output_line = self.substituteInlineExprs(line)

			outfile.write(output_line)

			if block_output:
				outfile.write(self._getNextGeneratedBlock())

		infile.close()
		outfile.close()


def createGeneratorFile(in_path, generator_file_path, out_path):
	""" Creates a python script containing the generator code
	found in the input path """
	infile = open(in_path)
	outfile = open(generator_file_path, "w")

	current_mode = "client_source"
	current_pygen_prefix = None

	outfile.write("import pyCodeGen\n")
	outfile.write("import os, sys, logging\n")
	outfile.write("\n")
	outfile.write("logging.basicConfig(level="+str(CONFIG.log_level)+")\n")
	outfile.write("gen = pyCodeGen.Generator(r'"+in_path+"', r'"+out_path+"')\n")

	outfile.write("logging.debug('genscript running in: ' + os.getcwd())\n")
	outfile.write("sys.path.append(r'"+os.path.dirname(in_path)+"')\n")

	line_num = 0
	for line in infile:
		line_num += 1

		if "#PYGEN_BEGIN" in line:
			if current_mode == "pygen_code":
				raise Exception("Error: line " +str(line_num)+ ": #PYGEN_BEGIN found when already in pygen mode")
			else:
				current_mode = "pygen_code"

			pygen_prefix = getPygenPrefix(line)
			logging.debug("pygen_prefix: " + pygen_prefix)

		if current_mode == "pygen_code":
			outfile.write(line[len(pygen_prefix):])
		else:
			inline = getInlinePygen(line)
			if inline != None:
				outfile.write(inline)

		if "#PYGEN_END" in line:
			if current_mode == "client_source":
				raise Exception("Error: line " +str(line_num)+ ": #PYGEN_END found when not in pygen mode")
			else:
				current_mode = "client_source"

		if "#PYGEN_OUTPUT" in line:
			outfile.write("gen.appendGeneratedBlock()\n")

	outfile.write("gen.end()\n")

	infile.close()
	outfile.close()


def getInlinePygen(line):
	matchobj = re.search("\$\{(.+?)\}", line)
	if matchobj != None:
		return "gen.appendInline("+matchobj.group(1)+")\n"
	else:
		return None


def getPygenPrefix(line):
	""" Get the characters #PYGEN_CODE """
	return line.split("#PYGEN_BEGIN")[0]


def removeCodeGenBlocksFromFile(path):
		temp_filename = path + ".tmp~"

		infile = open(path)
		outfile = open(temp_filename, 'w')
		in_genblock = False

		for line in infile:
			if "#PYGEN_BEGIN" in line:
				in_genblock = True
			if "#PYGEN_END" in line:
				in_genblock = False
				continue
			if "#PYGEN_OUTPUT" in line:
				continue
			if in_genblock == False:
				outfile.write(line)

		outfile.close()
		infile.close()
		os.remove(path)
		os.rename(temp_filename, path)


if __name__ == "__main__":
	main()
