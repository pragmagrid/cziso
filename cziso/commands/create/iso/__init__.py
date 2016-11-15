import cziso.commands
import cziso.clonezilla
from cziso.commands import CommonArgs, Arg, Opt


class Command(cziso.commands.Command):
	usage = CommonArgs(
		"""
		Create a format independent Clonezilla ISO based on the supplied VM
		image file.  This leverages a specialized version of Clonezilla Live VM
		with some built-in assumptions so that the conversion process is mostly
		automated.
		""",
		[
			Arg("image", "Name of image to use as source for iso")
		],
		[
			Opt("ip",
			    "Temporary IP address to assign Clonezilla Live VM.\n" +
			    "  If blank uses 'rocks report nextip command", None)
		]
	)

	def __init__(self):
		cziso.commands.Command.__init__(self)
		self.file = __file__

	def run(self, config, args):
		arg_vals = self.parse_args(args)

		cz = cziso.clonezilla.Clonezilla(config)
		cz.convert_to_clonezilla_iso(arg_vals["image"], ip=arg_vals["ip"])