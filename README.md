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
Both sent and received payloads have similar formats:
```javascript
{
    "type":"game",  # can be "info", "game" and "error" (received)
    "data": {...}   # dictionary with MULTIPLE key: value pairs
}
```
The "info" type is used by the login form to send data about the user. The "game" type is dedicated for the headset (or any other game frontend). Once user information is available the JSON objects for data exchange are the following:

**Server accepts:**
1. Connect (or reconnect to ongoing experiment) to the server as a "game" frontend:
```javascript
{"type":"game", "data":{"connect": true, "type":"game"}}
```
2. Search for a random opponent:
```javascript
{"type":"game", "data":{"search": true}}
```
3. Once an opponent was found, the choices within the game can be sent the following way:
```javascript
{"type":"game", "data":{"play": true}}  # cooperate
{"type":"game", "data":{"play": false}}  # defect
```
4. Disconnect (sned this when the experiment is over and ```{exit: true}``` was received also):
```javascript
{"type":"game", "data":{"disconnect": true}}
```

**Server sends**

NOTE: the data:{} object can have multiple key:value pairs!

1. On error (most error messages are not sent but logged):
```javascript
{"type":"error", "data":{"message": "The error message"}}
```
2. On connection established (all requirements were met and connection request was sent from game device):
```javascript
{"type":"game", "data":{"connected": true}}
```
3. Number of opponents remaining:
```javascript
{"type":"game", "data":{"search": 1}}  # if < 0 no more games are left
```
4. Show loading screen for a few seconds:
```javascript
{"type":"game", "data":{"loading": 2.5}}  # 2500 miliseconds
```
5. Setting up the environment
```javascript
{"type":"game", "data":{
    "color": "red",  # color of text for opponent
    "nick": "Tibi",  # name of opponent
    "avatar": "pirate", # avatar of opponent
    "stage": "temple"   # stage to play the match
}}
```
6. Send notification if opponent has already made their move (the move itself is unknown):
```javascript
{"type":"game", "data":{"move": true}}
```
7. Results of a single match (both players haven chosen a strategy)
```javascript
{"type":"game", "data":{
    "rounds_left": 1,   # number of rounds left, 0 means the match is over
    "gain_bot": 3,  # points gained by opponent this round
    "gain_subject": 3,  # points gained by player this round
    "score_bot": 10,    # total points of opponent for this match
    "score_subject": 12,    # total points of player for this match
    "move_bot": True,   # previously selected move of opponent
    "move_subject": False   # prviously selected move of player
}}
```
8. Match has ended, show "search" button for subject to be able to look for another opponent:
```javascript
{"type":"game", "data":{"end": true}}
```
9. The experiment is over, there are no more opponents. The subject is notified that they should remove their headset and go back to finishing the forms:
```javascript
{"type":"game", "data":{"exit": true}}
```