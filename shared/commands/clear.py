import os

command = ["clear", "cls"]
description = "Clears the console"


def function():
    os.system("cls" if os.name == "nt" else "clear")
