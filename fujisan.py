# fujisan.py
# ----------
# FDIA clone by isak.asia
#
# dependencies: pymssql, pillow, tendo

import os
import time
import pymssql
from tendo import singleton
from PIL import Image # Pillow library
import fujirawimage # custom Pillow decoder

# configuration
w2khost = "10.0.1.15" # mssql / smb share host
w2kuser = "svartlab"
w2kpass = "1234"
inspool = "/tmp/fuji/inspool" # inspool mount path
outspool = "/tmp/fuji/outspool" # outspool mount path
outdir = "/Users/Svartlab/Documents/Frontier/Ready" # output path
datestr = time.strftime("%Y%m%d") # today's date

# make sure this is the only instance
me = singleton.SingleInstance()

# connect to MS SQL database
with pymssql.connect(w2khost, w2kuser, w2kpass, "FDIA_DB") as conn:
	# reset list of orders waiting to be converted
	waiting_orders = []
	with conn.cursor(as_dict = True) as c:
		# retrieve all orders
		c.execute("SELECT * FROM dbo.OrderTable")
		# loop through rows
		for row in c:
			# read order status 
			# (0 = Error, 2 = Waiting to convert)
			# (4 = Waiting to write, 5 = Completed)
			if row["Status"] == 2:
				# append to order list
				waiting_orders.append({
					"dir":str(row["FDIAManageID"]), 
					"status":row["Status"], 
					"name":row["OrderID"]
				})

		# mount inspool if not mounted	
		if not os.path.ismount(inspool):
			if not os.path.isdir(inspool):
				os.makedirs(inspool)
			os.system("mount_smbfs //FRONTIER:FRONTIER@" + win2000 + "/InSpool " + inspool);

		# mount outspool if not mounted
		if not os.path.ismount(outspool):
			if not os.path.isdir(outspool):
				os.makedirs(outspool)
			os.system("mount_smbfs //FRONTIER:FRONTIER@" + win2000 + "/OutSpool " + outspool);

		# create output directory if not existing
		if not os.path.isdir(outdir):
			os.makedirs(outdir)

		# loop through orders to be converted
		for order in waiting_orders:
			orderdir = inspool + "/0000" + order["dir"]
			newdir = outdir + "/" + datestr + "-" + order["name"]
			if not os.path.isdir(newdir):
				os.makedirs(newdir)

			for file in os.listdir(orderdir):
				im = Image.open(orderdir + "/" + file)
				filename = newdir + "/" + datestr + "-" + order["name"] + "-" + file.replace(".RAW", "").replace("0000", "")
				out = im.rotate(270, expand = True)
				out.save(filename + ".tif")
				print "saving " + filename

			# remove images associated with order in DB
			# c.execute("SELECT * FROM dbo.ImageTable WHERE FDIAManageID = '" + order["dir"] + "'")

			# change status of order to completed in DB
			c.execute("UPDATE dbo.OrderTable SET Status = 5 WHERE FDIAManageID = '" + order["dir"] + "'")
			conn.commit()
