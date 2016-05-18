# fujisan.py
# ----------
# FDIA clone by isak.asia, now a daemon!
#
# dependencies: pymssql, pillow

import os
import time
import shutil
import pymssql
from PIL import Image # Pillow library
import fujirawimage # custom Pillow decoder

# configuration
inspool = "/tmp/fuji/inspool" # inspool mount path
outspool = "/tmp/fuji/outspool" # outspool mount path
sleeptime = 5 # cycle time in seconds

outdir = "/Users/Svartlab/Documents/Frontier/Ready" # output path
w2khost = "10.0.1.15" # mssql / smb share host
w2kuser = "svartlab"
w2kpass = "1234"

datestr = time.strftime("%Y%m%d") # today's date

# connect to MS SQL database
with pymssql.connect(w2khost, w2kuser, w2kpass, "FDIA_DB") as conn:
		
	# run forever
	while True:

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

				for file in glob.glob(orderdir + "/*.RAW"):
					im = Image.open(file)
					filename = newdir + "/" + datestr + "-" + order["name"] + "-" + os.basename(file).replace(".RAW", "").replace("0000", "")
					out = im.rotate(270, expand = True)
					out.save(filename + ".tif")
					print "saving " + filename

				# remove image directory
				shutil.rmtree(orderdir)

				# remove images associated with order in DB
				c.execute("DELETE FROM dbo.ImageTable WHERE FDIAManageID = '" + order["dir"] + "'")
				c.execute("DELETE FROM dbo.OutputImageTable WHERE FDIAManageID = '" + order["dir"] + "'")
				# TODO: insert more tables here

				# change status of order to completed in DB
				#c.execute("UPDATE dbo.OrderTable SET Status = 5 WHERE FDIAManageID = '" + order["dir"] + "'")

				# or nah, remove it
				c.execute("DELETE FROM dbo.OrderTable WHERE FDIAManageID = '" + order["dir"] + "'")

				# commit SQL changes to database
				conn.commit()

		# time to sleep, soon time to wake up
		time.sleep(sleeptime)
