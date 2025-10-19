import os

command = ["clear","cls"]
description = "Clears the console"

def clear():
    os.system("cls" if os.name == "nt" else "clear")