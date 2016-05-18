from PIL import Image, ImageFile
import string

class FujiImageFile(ImageFile.ImageFile):
    format = "FUJI"
    format_description = "Fuji Frontier SP3000 RAW"

    def _open(self):
        # check header
        header = self.fp.read(32)

        if header[:2] != "DR":
            raise SyntaxError, "not a FUJI file"

	# read image size from header (16 bit info endianness-transformed)
	headerbytes = [ord(c) for c in header]    
	headerwords = [headerbytes[d + 1] * 256 + headerbytes[d] for d in range(0, len(headerbytes) - 1, 2)]
	self.size = headerwords[4], headerwords[5]

	# mode is always RGB, right?
	self.mode = "RGB"

        self.tile = [
            ("raw", (0, 0) + self.size, 32, (self.mode, 0, 1))
        ]

Image.register_open("FUJI", FujiImageFile)
Image.register_extension("FUJI", ".fuji")
