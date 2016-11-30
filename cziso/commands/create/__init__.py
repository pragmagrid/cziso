import cziso.commands
import cziso.clonezilla
import cziso.image
from cziso.commands import CommonArgs, Arg, ImageArg, Opt


class Command(cziso.commands.Command):
	usage = CommonArgs(
		"""
		Create a format independent Clonezilla ISO based on the supplied VM
		image file.  This leverages a specialized version of Clonezilla Live VM
		with some built-in assumptions so that the conversion process is mostly
		automated.  Currently only RAW and ZFS volumes are supported.
		""",
		[
			ImageArg("image")
		],
		[
			Opt(
				"out",
				"""Path to directory where to write generated ISO file to.
		(default is to write it to configured temp directory)""",
				None),
			Opt(
				"net",
			    """Temporary IP address and netmask to assign Clonezilla Live
		VM.  Format is <ip>:<netmask>.  If blank attempts to use
		'rocks report nextip command'.  """,
				None)
		]
	)

	def __init__(self):
		cziso.commands.Command.__init__(self)
		self.file = __file__

	def run(self, config, args):
		arg_vals = self.parse_args(args)

		in_image = cziso.image.Image.factory(arg_vals["image"])
		cz = cziso.clonezilla.Clonezilla(config)
		cz.convert_to_clonezilla_iso(in_image, arg_vals["out"], arg_vals["net"])
