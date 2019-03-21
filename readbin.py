import glob

#OtherTable.FilePath = CDORDER.INF

f = file("cdorder.inf", "rU")
lines = f.read().split("\n")[1:-3]
for l in lines:
	print l.replace("[", "").replace("]", "").split(" ")[1::]


files = glob.glob("7775/*.INF")
for inffile in files:
	f = file(inffile, "rb")
	f.seek(0x3cc)
	framename = f.read(6)
	f.seek(0x400)
	rotation = f.read(8)

	print inffile + " frame " + framename + " rotation " + rotation.encode("hex")
