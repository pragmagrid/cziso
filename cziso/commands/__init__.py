import cziso
import logging
import os
import re
import StringIO
import sys


class Arg:
	"""
	Convenience class for handling required command-line arguments
	"""
	def __init__(self, name, description):
		"""
		Constructor for required command-line argument

		:param name: A string containing the name of the command-line argument
		:param description: A string containing a short description of argument
		"""
		self.name = name
		self.description = description

	def get_name(self):
		"""
		Return the name of the command-line argument

		:return: A string containing the name of the command-line argument
		"""
		return self.name

	def usage_short(self):
		"""
		Get short usage string representing argument

		:return: A string containing the summary usage for this arg
		"""
		return " <%s>" % self.name

	def usage_long(self):
		"""
		Get long usage string representing argument

		:return: A string containing the long usage for this arg
		"""
		return """
		<%s>

		%s
		""" % (self.name, self.description)


class Opt(Arg):
	"""
	Convenience class for handling optional command-line arguments
	"""
	def __init__(self, name, description, default):
		"""
		Constructor for optional command-line argument

		:param name: A string containing the name of the command-line argument
		:param description: A string containing a short description of argument
		:param default: A string containing the default value of argument
		"""
		Arg.__init__(self, name, description)
		self.default = default

	def get_default(self):
		"""
		Return the default value of this option

		:return: A string containing the default value of the option
		"""
		return self.default

	def usage_short(self):
		"""
		Get short usage string representing argument

		:return: A string containing the summary usage for this arg
		"""
		return " [%s=%s]" % (self.name, self.default)

	def usage_long(self):
		"""
		Get long usage string representing argument

		:return: A string containing the long usage for this arg
		"""
		return """
		[%s=%s]

		%s
		""" % (self.name, self.default, self.description)


class Args:
	"""
	Convenience class for handling required and optional command-line args
	"""
	def __init__(self, description, args, opts):
		""""
		Constructor for managing command-lne args

		:param description A short description of the program
		:param args An array of Arg elements representing required
		command-line arguments
		:param opts An array of Opt elements representing optional command-line
		arguments
		"""
		self.description = description
		self.args = args
		self.opts = opts

	def get_arg(self, this_arg):
		"""
		Find the named argument or option for this program

		:param this_arg: A string containing the name of the argument or option

		:return: An element of type Arg (or Opt) or None if not found
		"""
		for arg in self.args:
			if arg.get_name() == this_arg:
				return arg
		for opt in self.opts:
			if opt.get_name() == this_arg:
				return opt
		return None

	def has_opt(self, this_opt):
		"""
		Return True if specified element is in program's options

		:param this_opt: A string containing the name of the option

		:return: True if exists otherwise False
		"""
		for opt in self.opts:
			if opt.get_name() == this_opt:
				return True
		return False

	def short_usage(self):
		"""
		Print the short usage of this program's command-line arguments as a
		single line

		:return:  A string containing the short usage summary
		"""
		usage = StringIO.StringIO()
		for arg in self.args:
			usage.write(arg.usage_short())
		for arg in self.opts:
			usage.write(arg.usage_short())
		return usage.getvalue()

	def long_usage(self):
		"""
		Print the long usage of this program including the program description
		and long description of required arguments and options

		:return:  A string containing the long usage details
		"""
		usage = StringIO.StringIO()
		usage.write("Description:\n")
		usage.write(self.description)
		if self.args:
			usage.write("\nArguments:\n")
		for arg in self.args:
			usage.write(arg.usage_long())
		if self.opts:
			usage.write("\nOptions:\n")
		for arg in self.opts:
			usage.write(arg.usage_long())
		return usage.getvalue()

	def verify(self, required, optionals):
		"""
		Validate the user's specified required arguments and options against
		the program's configuration

		:param required: An array of strings containing arguments supplied by
		user
		:param optionals: A hash array of optional arguments provided by user

		:return: A hash array where each key is a name of an argument or option
		and the value is the user provided value or default value
		"""
		arg_vals = {}
		if len(required) != len(self.args):
			sys.stderr.write(
				"Error, expected %d command arguments, received %d\n\n" % (
					len(self.args), len(required)))
			return None
		for i, arg in enumerate(self.args):
			arg_vals[arg.get_name()] = required[i]

		for opt in self.opts:
			if opt.get_name() in optionals:
				arg_vals[opt.get_name()] = optionals[opt.get_name()]
			else:
				arg_vals[opt.get_name()] = opt.get_default()
		return arg_vals


class CommonArgs(Args):
	"""
	Convenience class for common command-line arguments across all command
	"""
	def __init__(self, description, args, opts):
		opts.append(Opt(
			"loglevel",
			"Print out log messages from specified level",
			"ERROR"
		))
		Args.__init__(self, description, args, opts)


class Command:
	"""
	Convenience class for managing Cziso commands
	"""
	usage = Args("", [], [])

	def __init__(self):
		"""
		Base constructor that sets logger and name of module file
		"""
		self.logger = logging.getLogger(self.__module__)
		self.file = __file__

	def is_arg_true(self, arg):
		"""
		Returns true if specified value is interpreted as true

		:param arg: A string containing a user command-line argument

		:return: True if matches and False otherwise
		"""
		return re.match("true|yes|y|t", arg, re.IGNORECASE) is not None

	def parse_args(self, args):
		"""
		Parse the user's command-line arguments and return values

		:param args A string array of user's command-line args and opts

		:return: A hash array where each key is a name of an argument or option
		and the value is the user provided value or default value\
		"""
		if len(args) == 1 and args[0] == 'help':
			self.print_command_usage()
			sys.exit(0)

		required = []
		optionals = {}
		for arg in args:
			if re.search("\S+=\S+", arg):
				(name, val) = arg.split("=")
				optionals[name] = val
			else:
				required.append(arg)

		arg_vals = self.__class__.usage.verify(required, optionals)
		if not arg_vals:
			self.print_usage()
			sys.exit(-1)

		if "loglevel" in optionals:
			cziso.config_logging(optionals["loglevel"])
		elif self.__class__.usage.has_opt("loglevel"):
			loglevel = self.__class__.usage.get_arg("loglevel")
			cziso.config_logging(loglevel.get_default())
		else:
			cziso.config_logging("ERROR")

		return arg_vals

	def print_command_usage(self):
		"""
		Print out long usage for this command

		:return:
		"""
		print self.usage.long_usage()

	def print_usage(self):
		""""
		Print help summary for all subcommands
		"""
		print "cziso: Clonezilla VM image tools\n"
		print "Usage:"

		command_dir = os.path.dirname(os.path.realpath(self.file))
		command_dirs = []
		for root, dirs, files in os.walk(command_dir):
			if not dirs:
				command_dirs.append(root.replace(command_dir, "").strip("/"))
		parent_cmd_dir = os.path.dirname(__file__)
		parent_cmd = command_dir.replace(parent_cmd_dir, "")
		for command in sorted(command_dirs):
			module_name = "cziso.commands%s.%s" % (
				parent_cmd.replace("/", "."), command.replace("/", "."))
			module = __import__(module_name, fromlist=["Command"])
			cmd_obj = getattr(module, "Command")
			print "cziso%s %s %s" % (
				parent_cmd.replace("/", " "),
				command.replace("/", " "),
				cmd_obj.usage.short_usage())

	def run(self, config, args):
		"""
		Run the specified command

		:param args:  An CzisoConfig object containing all config info
		:param args:  An array of string arguments.  Required arguments are
		single values and optional arguments are of name=value format

		:return: True if successful and False otherwise
		"""
		self.print_usage()
		return True
