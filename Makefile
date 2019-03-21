LAUNCHDIR = ~/Library/LaunchAgents

NAME = py.fujisan.httpd
OBJ = $(NAME).plist

launch:
	cp -v $(OBJ) $(LAUNCHDIR)/ 

restart:
	launchctl unload $(LAUNCHDIR)/$(OBJ)
	launchctl start $(NAME)
