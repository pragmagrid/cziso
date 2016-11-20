import cziso.commands
import cziso.clonezilla
import cziso.image
from cziso.commands import CommonArgs, Arg, ImageArg, Opt


class Command(cziso.commands.Command):
	usage = CommonArgs(
		"""
		Resize an image using regular Clonezilla Live VM
		""",
		[
			ImageArg("image")
		],
		[
		]
	)

	def __init__(self):
		cziso.commands.Command.__init__(self)
		self.file = __file__

	def run(self, config, args):
		arg_vals = self.parse_args(args)

		image = cziso.image.Image.factory(arg_vals["image"])
		if not image.exists():
			cziso.abort("Image %s does not exists" % image)
		cz = cziso.clonezilla.Clonezilla(config)
		cz.modify_image(image)