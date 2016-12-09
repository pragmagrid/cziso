import ConfigParser
import cookielib
import datetime
import logging
import os
import re
import shlex
import string
import sys
import subprocess
import urllib2


logger = None

__all__ = ["clonezilla", "gdrive", "image", "virtualmachine"]


def abort(error):
	"""
	Print out error message and cause program to exit with error code

	:param error: Text of error message

	:return: **Does not return**
	"""
	logger.error(error)
	sys.exit(1)


def abort_if_no_x():
	"""
	Check to see if X forwarding is enabled and fail if not
	"""
	# check for external display so we can launch vncviewer
	if "DISPLAY" not in os.environ:
		abort("""ERROR:
	Must have external display to launch vncviewer.  Please SSH
	in with -Y to forward X display""")


def config_logging(loglevel="INFO", logfile=None):
	"""
	Configure the logger for calling program.  If logfile is None, messages
	will be printed to stdout.

	:param loglevel: Level of messages to be printed [default: INFO]
	:param logfile: Redirect messages to file if exists [default: None]

	:return:  The configured logger object
	"""
	logformat = None
	if loglevel == "DEBUG":
		logformat = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
	logging.basicConfig(
		filename=logfile,
		format=logformat,
		level=getattr(logging, loglevel.upper()))
	global logger
	logger = logging.getLogger(sys.argv[0])
	return logging.getLogger(sys.argv[0])


def create_nfs_export(dir, ip):
	"""
	Export the specified directory to specified IP address.  Aborts if unable
	to export the directory.

	:param dir: A directory to export
	:param ip: The IP address of the machine that will mount the directory

	:return:
	"""
	out, rc = run_command(
		"exportfs -o 'rw,no_root_squash,async' %s:%s" % (ip, dir))
	if rc != 0:
		abort("Unable to export temp directory to Clonezilla VM")


def file_edit(file_path, substitutions):
	"""
	Edit specified file and make any substitutions in it if found.

	:param file_path: A string containing the path of the file to edit
	:param substitutions: A hash array where the key is the search string and
	the value is the replacement string

	:return: A new target_string with substitutions if matched
	"""
	old_f = open(file_path, "r")
	if old_f is None:
		abort("Unable to open file %s" % file_path)
	new_file = "%s.new" % file_path
	new_f = open(new_file, "w")
	if old_f is None:
		abort("Unable to open file %s for writing" % new_file)
	for line in old_f:
		for search_string, replace_string in substitutions.items():
			found_index = line.find(search_string)
			if found_index > 0:
				line = line.replace(search_string, replace_string)
		new_f.write(line)
	old_f.close()
	new_f.close()
	os.rename(new_file, file_path)


def fill_template(template_file, tmp_dir=None, **kwargs):
	""""
	Read the template file from disk and substitute in the args

	:param template_file The path to the template file
	:param tmp_dir Write output to tmp_dir if specified and return path to file;
	else return substituted template as a string.
	:param kwargs Arbitrary number of substitute values to the the template file

	:return A string containing the filled in template file or path to template
	file if tmp_dir is not None
	"""
	f = open(template_file, "r")
	if not f:
		abort("Unable to open %s" % template_file)
	template = string.Template(f.read())
	xml = template.substitute(kwargs)
	logger.debug("%s:\n%s" % (template_file, xml))
	logger.debug(xml)

	if tmp_dir is None:
		return xml

	template_basename = os.path.basename(template_file)
	expect_path = os.path.join(tmp_dir, template_basename)
	logger.info("Writing expect template to %s" % expect_path)
	f = open(expect_path, "w")
	f.write(xml)
	f.close()
	return expect_path


def gdrive_download(google_id, lpath):
	"""
	Download a file from Google drive using cookie trick from Phil

	:param google_id: A string containing the Google drive id for the file you
	want to download
	:param lpath:  A string containing the local path you want to download the
	file to
	:return: True if successful
	"""
	url = "https://docs.google.com/uc?id=%s&export=download" % google_id

	# get cookie and confirm code
	logger.debug("Getting cookie for file %s at %s" % (google_id, url))
	cookie_support = urllib2.HTTPCookieProcessor(cookielib.LWPCookieJar())
	opener = urllib2.build_opener(cookie_support, urllib2.HTTPHandler)
	urllib2.install_opener(opener)
	response = opener.open(url)
	response_str = response.read()
	matcher = re.search("confirm=(\w+)", response_str)
	if matcher is None:
		abort("Unable to find confirm code in %s" % response_str)
	confirm_code = matcher.group(1)

	# download to file
	download_url = "%s&confirm=%s" % (url, confirm_code)
	logger.debug("Download url is %s" % download_url)
	logger.info("Downloading file %s to %s" % (google_id, lpath))
	response = opener.open(download_url)
	with open(lpath, "wb") as f:
		f.write(response.read())
	return True


def generate_iso(genisoimage_command, source_dir, iso_file):
	"""
	Generate an ISO image from a source directory.

	:param genisoimage_command: A string containing the genisocommand and opts
	:param source_dir: A string containing the ISO source directory
	:param iso_file: A string containing the path of the generated ISO file
	:return:
	"""
	current_dir = os.getcwd()
	os.chdir(source_dir)
	logger.info("Generating ISO %s" % iso_file)
	out, rc = run_command("%s -o %s ." % (genisoimage_command, iso_file))
	if rc != 0:
		abort("Error generating ISO: %s" % ("\n".join(out)))
	if not os.path.exists(iso_file):
		abort("Can not find generated ISO file %s" % iso_file)
	os.chdir(current_dir)


def get_current_time_string():
	"""
	Get the current time formatted nicely as a string in UTC

	:return:  A string representing the current date/time.
	"""
	class UTC(datetime.tzinfo):
		def utcoffset(self, dt):
			return datetime.timedelta(0)

		def tzname(self, dt):
			return "UTC"

		def dst(self, dt):
			return datetime.timedelta(0)

	utc = UTC()
	now = datetime.datetime.now(utc)
	return str(now)


def get_free_ip(iface):
	"""
	Find a free unused IP address using Rocks commands.

	:param iface: The interface to find the IP address for

	:return: A tuple containing the free ip and netmask.
	"""
	free_ip = None
	out, rc = run_command("rocks report nextip private")
	if rc != 0 and len(out) > 0:
		logger.error("Unable to get a free ip address from Rocks")
		return None, None
	free_ip = out[0]

	out, rc = run_command("rocks report host interface localhost iface=%s" % iface)
	if rc != 0 and len(out) > 0:
		logger.error(out)
		logger.error("Unable to get netmask from Rocks")
		return None, None
	matcher = re.search("NETMASK=(\S+)", " ".join(out))
	if matcher is None:
		logger.error("Unable to parse netmask from Rocks command")
		return None, None
	netmask = matcher.group(1)
	return free_ip, netmask


def get_command(args):
	"""
	Look for command in user's command-line arguments.

	:param args: A string array of user's command line arguments

	:return: A subclass object of cziso.command.Command or none if not found
	"""
	classname = "Command"
	for i in range(len(args), 0, -1):
		module_name = "cziso.commands.%s" % ".".join(args[:i])
		module_name = module_name.rstrip(".")
		try:
			module = __import__(module_name, fromlist=[classname])
			return getattr(module, classname)(), args[i:]
		except ImportError:
			continue
	return None, None


def increment_filename(filename):
	"""
	Given a filename check to see if it exists.  If so, append .1 so that we
	do not override the file.  If .1 file exists keep appending .1 until the
	file is not found.

	:param filename: A string containing a filename or path

	:return: An incremented filename that does not exist
	"""
	if not os.path.exists(filename):
		return filename
	i = 1
	while True:
		candidate_filename = "%s.%i" % (filename, i)
		if not os.path.exists(candidate_filename):
			return candidate_filename
		i += 1


def remove_nfs_export(dir, ip):
	"""
	Un-export NFS directory.  Returns if successful; otherwise aborts.

	:param dir:  The directory to un-export
	:param ip:  The IP address the directory was exported to.

	:return:
	"""
	out, rc = run_command("exportfs -u %s:%s" % (ip, dir))
	if rc != 0:
		abort("Unable to remove un-export temp directory")


def run_command(cmdline, input_string=None):
	"""
	Run popen pipe inputString and return a tuple of
	(the stdout as a list of string, return value of the command)

	:param cmdline A string containing the Bash command to run
	:param input_string A string containing input for command

	:return The stdout as a string array and exit code
	"""
	logger.debug("Executing command: '%s'" % cmdline)
	if isinstance(cmdline, unicode):
		cmdline = str(cmdline)
	if isinstance(cmdline, str):
		# needs to make a list
		cmdline = shlex.split(cmdline)
	p = subprocess.Popen(
		cmdline, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
		stderr=subprocess.STDOUT)
	grep_stdout = p.communicate(input=input_string)[0]
	p.wait()
	return grep_stdout.split('\n'), p.returncode


class CzisoConfig(ConfigParser.RawConfigParser):
	"""
	Convenience class for getting info from config file
	"""
	def __init__(self, config_dir, config_file, **kwargs):
		"""
		Create CzisoConfig object

		:param kwargs: Same as arguments for ConfigParser.RawConfigParser

		:return: new CzisoConfig object
		"""
		ConfigParser.RawConfigParser.__init__(self, kwargs)
		self.config_dir = config_dir
		self.config_file = os.path.join(config_dir, config_file)
		self.logger = logging.getLogger(self.__module__)

	def get_path(self, section, var):
		"""
		Get a path from the config file.  If relative, it is assumed to be
		relative to the config dir etc

		:param section:  The section header to read variables from.
		:param var: A string containing the variable to read from section

		:return: A string containing the path to a file
		"""
		path = self.get(section, var)
		if not os.path.isabs(path):
			path = os.path.join(self.config_dir, path)
			self.logger.debug("Path for %s resolved to %s" % (var, path))
		return path

	def get_vars_by_regex(self, section, var_regex):
		"""
		Read variables matching the specified regex from the specified section
		of the config file.

		:param section:  The section header to read variables from.
		:param var_regex: A string containing a regex

		:return: A dictionary containing matching variable names and values.  If
		the regex contains a group, the value of the captured group is used as
		the variable name.
		"""
		variables = {}
		for (name, value) in self.items(section):
			match = re.search(var_regex, name)
			if match:
				if len(match.groups()) == 1:
					name = match.group(1)
				variables[name] = value
		return variables

	def load(self):
		"""
		Read in config file

		:return: Returns True if successful, otherwise False
		"""
		return ConfigParser.RawConfigParser.read(self, self.config_file)