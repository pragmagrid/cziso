import ConfigParser
import cookielib
import logging
import re
import shlex
import string
import sys
import subprocess
import urllib2


logger = None

__all__ = ["clonezilla"]


def abort(error):
	"""
	Print out error message and cause program to exit with error code

	:param error: Text of error message

	:return: **Does not return**
	"""
	logger.error(error)
	sys.exit(1)


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


def create_loop_device(image):
	"""
	Mount an image file as a block device.

	:param image: A path to an image file

	:return: The loop device id
	"""
	out, rc = run_command("losetup -f %s" % image)
	if rc != 0:
		abort("Unable to mount %s as a control loop device")
	out, rc = run_command("losetup -a")
	loop_device = None
	for line in out:
		if line.find(image) >= 0:
			matcher = re.search("(/dev/loop\d+)", line)
			if matcher:
				loop_device = matcher.group(1)
				return loop_device
	if not loop_device:
		abort("Unable to find loop device for %s" % image)


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


def fill_template(template_file, **kwargs):
	""""
	Read the template file from disk and substitute in the args

	:param template_file The path to the template file
	:param kwargs Arbitrary number of substitute values to the the template file

	:return A string containing the filled in template file
	"""
	f = open(template_file, "r")
	if not f:
		abort("Unable to open %s" % template_file)
	template = string.Template(f.read())
	xml = template.substitute(kwargs)
	logger.debug("%s:\n%s" % (template_file, xml))
	return xml


def gdrive_download(google_id, lpath):
	url = "https://docs.google.com/uc?id=%s&export=download" % google_id

	# get cookie and confirm code
	logger.debug("Getting cookie for file %s at %s" % (google_id, url))
	cookie_support = urllib2.HTTPCookieProcessor(cookielib.LWPCookieJar())
	opener = urllib2.build_opener(cookie_support, urllib2.HTTPHandler)
	urllib2.install_opener(opener)
	response = opener.open(url)
	response_str = response.read()
	matcher = re.search("confirm=(\w+)", response_str)
	confirm_code = matcher.group(1)

	# download to file
	download_url = "%s&confirm=%s" % (url, confirm_code)
	logger.debug("Download url is %s" % download_url)
	logger.info("Downloading file %s to %s" % (google_id, lpath))
	response = opener.open(download_url)
	with open(lpath, "wb") as f:
		f.write(response.read())
	return True


def get_free_ip(iface):
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


def remove_loop_device(loop_device):
	"""
	Unmount image from loop device.  Returns if successful; otherwise aborts.

	:param loop_device: The loop device id (/dev/loopX)

	:return:
	"""
	out, rc = run_command("losetup -d %s" % loop_device)
	if rc != 0:
		abort("Unable to remove loop device %s" % loop_device)


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
	p = subprocess.Popen(cmdline, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
							stderr=subprocess.STDOUT)
	grep_stdout = p.communicate(input=input_string)[0]
	p.wait()
	return grep_stdout.split('\n'), p.returncode


class CzisoConfig(ConfigParser.RawConfigParser):
	"""
	Convenience class for getting info from config file
	"""
	def __init__(self, **kwargs):
		"""
		Create CzisoConfig object

		:param kwargs: Same as arguments for ConfigParser.RawConfigParser

		:return: new CzisoConfig object
		"""
		ConfigParser.RawConfigParser.__init__(self, kwargs)
		self.logger = logging.getLogger(self.__module__)

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
