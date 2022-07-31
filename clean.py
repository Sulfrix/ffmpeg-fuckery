from os import listdir, system
from os.path import isfile, join
import os
import shutil
import settings


def cleanfiles():
    rmtreeexist("./frames")
    os.mkdir("./frames")

    rmtreeexist("./vids")
    os.mkdir("./vids")

    removeexist("still.png")
    removeexist(settings.outputfile)
    removeexist("concat.txt")
    removeexist("audio.aac")

def removeexist(path):
    if os.path.exists(path):
        os.remove(path)

def rmtreeexist(path):
    if os.path.exists(path):
        shutil.rmtree(path)

if __name__ == "__main__":
    print("Manual clean")
    cleanfiles()