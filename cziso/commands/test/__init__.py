import cziso.commands
import cziso.clonezilla
import cziso.image
import cziso.virtualmachine
from cziso.commands import CommonArgs, ImageArg


class Command(cziso.commands.Command):
	usage = CommonArgs(
		"""
		Start a VM with selected image
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
			cziso.abort("Input image %s does not exists" % in_image)
		cz = cziso.clonezilla.Clonezilla(config)
		cz.test_image(image)