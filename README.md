# The effect of Virtual Environments on cooperation in Iterated Prisoner's Dilemma games

**Please ignore this page if you are a subject candidate for this experiment, as it reveals crucial parts of the experiment, and can skew the results by spoiling the test environment's inner workings.** 

# Step by step guide to conducting experiments
The environment consists of a Python server, an HTML frontend for logging users into the environment and the game module (both HTML for testing purposes and a Unity based VR game). 
* On a Windows PC go to *game/* and start the server with *run.bat* which will create the Python virtual environment and initiate the server with logging turned on. You can define your own address via *--ip* and *--port* arguments as well as the logging folder and file prefixes. Leave the command line open!
* Once the server is listening, open *login.html* with a browser that allows websocket access for local webpages (like Chrome or Firefox)! You can define the server's address by setting the following GET parameters: "login.html?ip=...&port=..." to match the values printed on the command line. If the connection was successfull, an input area will appear on the webpage asking for an ID, while the server's command line will show an incomming connection.
* Each subject must have their own unique ID assigned. These IDs must not collide and can never be the same for two people. After the ID of a subject is set, the subjects are asked to provide additional information, which includes setting up their avatars. Once all information is set, the webpage will inform the subject to start playing (put on a headset). 
* The subject can now put on a VR headset and play mutliple, short matches. When the game is over, the subject will be informed to remove the headset and give additional information on the webpage that was previously used to provide data.
* Once the remaining information is given, the goals of the experiment are revealed and the test is over. The subject may leave and the login page will once again ask for another subject's ID.
* The process can be repeated multiple times with the same settings. If the server's command line is closed, the experiment will be shut down and both the login webpage and the game will disconnect and show a notification. The experiment can be continued by repeating all these steps again.
* Throughout the process, user's information and in-game actions are logged (if not set otherwise) as *.csv* files with time stamp affixes. 

TODO: what to do when a subject pauses or interrupts the experiment.

# Server API Documentation

