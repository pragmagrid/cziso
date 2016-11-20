import cziso.commands
import cziso.clonezilla
import cziso.image
from cziso.commands import CommonArgs, Arg, ImageArg, Opt


class Command(cziso.commands.Command):
	usage = CommonArgs(
		"""
		Restore a Clonezilla VM ISO to image
		""",
		[
			Arg("iso", "Path to Clonezilla VM ISO"),
			ImageArg("image")

		],
		[
			Opt("size", "Size of destination image (GB)", "")
		]
	)

	def __init__(self):
		cziso.commands.Command.__init__(self)
		self.file = __file__

	def run(self, config, args):
		arg_vals = self.parse_args(args)

		out_image = cziso.image.Image.factory(arg_vals["image"])
		if not out_image.exists():
			if arg_vals["size"] == "":
				cziso.abort("Image %s does not exist, please specify option 'size' to create image")
			out_image.create(arg_vals["size"])
		cz = cziso.clonezilla.Clonezilla(config)
		cz.restore_clonezilla_iso(arg_vals["iso"], out_image)