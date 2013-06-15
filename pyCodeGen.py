"""
Example (c code):

// #PYGEN_BEGIN
// import Thingo
// print "yo"
// #PYGEN_END
// #PYGEN_OUTPUT

void ${Thingo.string()}something() {
}


Rules:
 - Comment block characters preceding "#PYGEN_BEGIN" must be consistent for the whole block
   and all blocks in the file
 - Input file must have a newline at the end of the file otherwise you might miss some output
 - Every block that generates code needs a #PYGEN_OUTPUT to tell the generator where to
	 put the output code

TODO:
 - Make into proper console app
 - Allow user-configurable code generation block delimiters (configure in this
   file, eg. genBlock_start = "PYGEN_BEGIN"
 - Add option to keep generator script (default delete)
 - Support input file line-endings (may already "just work"?)

POTENTIAL IMPROVEMENTS:
 - Remove need for as many rules as possible (or at least make them optional)
"""

import argparse, logging, subprocess, shutil, os, re

class CONFIG:
	log_level                 = logging.WARNING
	keep_generator_code       = False # leave generator code in output file
	keep_generator_file       = False # copy generator file to output dir


def main():
	logging.basicConfig(level=CONFIG.log_level)
	args = getArgParser().parse_args()
	genscript_path = os.path.basename(args.input) + ".gen.py~"
	output = getOutputFilename(args.input)
	createGeneratorFile(args.input, genscript_path, output)
	subprocess.call(["python", genscript_path])
	if not CONFIG.keep_generator_code:
		removeCodeGenBlocksFromFile(output)
	cleanup()


def getArgParser():
	myParser_desc = """ To do: Description here... """
	parser = argparse.ArgumentParser(description=myParser_desc)
	parser.add_argument('input', help="input file")
	return parser


def cleanup():
	""" Remove temporary files generated during script """
	rm_list = [ f for f in os.listdir(".") if f.endswith("~") or f.endswith("pyc") ]
	for f in rm_list:
		os.remove(f)


def getOutputFilename(input_path):
	filename, ext = os.path.splitext(input_path)
	return filename + "_gen" + ext


class Generator:
	def __init__(self, in_path, out_path):
		self.in_path = in_path
		self.out_path = out_path
		self._current_output_string = ""
		self.inline_prefix = ""
		self.inline_suffix = ""

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

	def setInlinePrefixAndSuffix(self, prefix, suffix):
		""" Specify the prefix and suffix characters you will use for inline generator
		expressions. For example if you are generating C code, you may want to call
		pyCodeGen.setInlinePrefixAndSuffix("/*", "*/").
		The prefix and suffix will be removed in the generation of inline text.
		"""
		self.inline_prefix = prefix
		self.inline_suffix = suffix

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
	outfile.write("import logging\n")
	outfile.write("\n")
	outfile.write("logging.basicConfig(level="+str(CONFIG.log_level)+")\n")
	outfile.write("gen = pyCodeGen.Generator('"+in_path+"', '"+out_path+"')\n")

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
