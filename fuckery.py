# Sulfrix's "WEBM" Fuckery program
# Uses FFMPEG to split a file into all of its frames, and allows for each one to be resized indivisually.
# WEBM supports dynamic resolution, so certain players will show this resolution change and resize accordingly.

from math import sin, cos
from PIL import Image
import PIL
from os import listdir, system
from os.path import isfile, join
import os
import shutil
from duplicateframe import dupframe
import clean
import ffmpeg
import settings
import sys
from queue import Queue, PriorityQueue


this = sys.modules[__name__]

use_rawfield = False
framerate_field = ""

framerate = 25
delta_time = 1/60

# There's an option to use an actual video or duplicate a still of the first frame of a video.
# This allows images to be resized.


def populate_frames(path):
    if not settings.dupeframe:

        probe = ffmpeg.probe(path)

        system("ffmpeg -hide_banner -i " + path + " -pix_fmt rgba frames/%04d.png")
        system("ffmpeg -y -hide_banner -loglevel error -i " + path + " audio.opus")

        this.framerate_field = probe["streams"][0]["r_frame_rate"]

        this.framerate = parse_framerate(framerate_field)
        
    else:
        dupframe(settings.dupeframe_count)
        this.framerate = 60
        this.framerate_field = "60"
    print("Framerate is " + str(framerate))
    this.delta_time = 1/framerate

    frameratefile = open("./framerate.txt", "w")
    frameratefile.write(framerate_field)
    frameratefile.close()
    

def parse_framerate(framerate_field):
    framerate = 30
    if "/" in framerate_field:
        dividends = framerate_field.split("/")
        framerate = float(dividends[0])/float(dividends[1])
        this.use_rawfield = True
    else:
        framerate = float(framerate_field)
    return framerate



# dupframe(100)


size_formula = "return (origwidth, origheight*(sin(frame*delta_time*20)+1)/2)"

def get_size(origwidth, origheight, frame, maxframe):
    eval(size_formula)

# Create the concat file that FFMPEG needs

globalframecount = 0

framesprocessed = 0

def populateframecount():

    framelist = listdir("./frames")
    this.globalframecount = len(framelist)

frameQueue = PriorityQueue()
workQueue = Queue()

class VidFrame:
    def __init__(self, index, path, duration) -> None:
        self.index = index
        self.path = path
        self.duration = duration

def workone(name):
    path = join("./frames/", name)
    framecount = this.globalframecount
    if isfile(path):
        # Open with Pillow
        im = Image.open(path)
        width, height = im.size
        strnum = name.rsplit(".", 1)[0]
        framenumber = int(strnum)
        # Run size formula
        size = get_size(width, height, framenumber, framecount)
        size = (int(max(size[0], 2)), int(max(size[1], 2)))
        im = im.resize(size)
        im.save(path)
        #print("resized " + str(framenumber) + "/" +
        #      str(framecount) + " to " + str(size))
        vidpath = "./vids/" + strnum + ".webm"
        # Now this part may be confusing and/or horrifying.
        # FFMPEG doesn't support using -concat to turn a PNG sequence into a .webm video, so EACH FRAME is converted to ITS OWN SEPERATE FILE
        # These are what FFMPEG eventually converts to a full video
        system("ffmpeg -y -hide_banner -loglevel error -i " + path + " " + vidpath)
        
        frame = VidFrame(framenumber, vidpath, delta_time)
        frameQueue.put((framenumber, frame))
        this.framesprocessed = this.framesprocessed + 1

def spitConcatFile():
    file = open("./concat.txt", "w")
    while not frameQueue.empty():
        fr = frameQueue.get()[1]
        file.write("file '" + fr.path + "'\nduration " + str(fr.duration) + "\n")
    file.close()


def do_conversion_resize(name):
    workone(name)


def finalvid():
    if not settings.dupeframe:
        use = str(framerate)
        if use_rawfield:
            use = framerate_field
        system("ffmpeg -hide_banner -y -r " + use +
               " -f concat -safe 0 -i concat.txt -i audio.opus -c copy test.webm")
    else:
        system("ffmpeg -hide_banner -y -r " + str(framerate) +
               " -f concat -safe 0 -i concat.txt -c copy test.webm")

#system("ffmpeg -y -framerate 30 -f image2 -i frames/%04d.png -c:v libvpx-vp9 -pix_fmt yuva420p output.webm")

if __name__ == "__main__":
    clean.cleanfiles()
    populate_frames("mp4.mp4")
    do_conversion_resize()
    finalvid()