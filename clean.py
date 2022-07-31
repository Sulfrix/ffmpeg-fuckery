from os import listdir, system
from os.path import isfile, join
import os
import shutil
import settings


def cleanfiles():
    shutil.rmtree("./frames")
    os.mkdir("./frames")

    shutil.rmtree("./vids")
    os.mkdir("./vids")

    removeexist("still.png")
    removeexist(settings.outputfile)
    removeexist("concat.txt")
    removeexist("audio.aac")

def removeexist(path):
    if os.path.exists(path):
        os.remove(path)

if __name__ == "__main__":
    print("Manual clean")
    cleanfiles()