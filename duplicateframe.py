from os import listdir, system
from os.path import isfile, join
import os
from re import I
import shutil


def dupframe(num):
    system("ffmpeg -y -i mp4.mp4 still.png")
    for i in range(num):
        x = i+1
        name = "./frames/" + (str(x)).zfill(4) + ".png"
        print(name)
        shutil.copyfile("still.png", name)