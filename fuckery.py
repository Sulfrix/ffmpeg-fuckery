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
        try:
            probe = ffmpeg.probe(path)
        except ffmpeg._run.Error as err:
            print(err.stderr)
            

        system("ffmpeg -hide_banner -i " + path + " -pix_fmt rgba frames/%04d.png")
        system("ffmpeg -y -hide_banner -loglevel error -i " + path + " audio.opus")

        this.framerate_field = probe["streams"][0]["r_frame_rate"]

        this.framerate = parse_framerate(framerate_field)
        
    else:
        dupframe(settings.dupeframe_count)
        this.framerate = 60
        this.framerate_field = "60"
    print("Framerate is " + str(framerate))
    

    frameratefile = open("./framerate.txt", "w")
    frameratefile.write(str(framerate))
    frameratefile.close()
    

def parse_framerate(ff):
    framerate = 30
    print("parsing the: " + ff)
    if "/" in ff:
        dividends = ff.split("/")
        framerate = float(dividends[0])/float(dividends[1])
        this.delta_time = 1/framerate
        this.framerate_field = ff
        this.use_rawfield = False
    else:
        framerate = float(ff)
        this.delta_time = 1/framerate
    return framerate



# dupframe(100)

workproj = None

def get_size(origwidth, origheight, frame, maxframe):
    return workproj.get_size_at_time(float(frame))

# Create the concat file that FFMPEG needs

globalframecount = 0

framesprocessed = 0

vidsize = (0, 0)

def populateframecount():
    framelist = listdir("./frames")
    this.globalframecount = len(framelist)

def populatevidsize():
    framelist = listdir("./frames")
    im = Image.open("./frames/" + framelist[0])
    this.vidsize = im.size
    im.close()

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
        print("Resizing " + str(framenumber) + " to " + str(size))
        im = im.resize(size)
        im.save(path)
        im.close()
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
    print(this.delta_time)
    while not frameQueue.empty():
        fr = frameQueue.get()[1]
        file.write("file '" + fr.path + "'\nduration " + str(fr.duration) + "\n")
    file.close()


def do_conversion_resize(name):
    workone(name)


def finalvid():
    if not settings.dupeframe:
        use = str(framerate)
        if float(framerate).is_integer:
            use = str(int(framerate))
        if use_rawfield:
            use = framerate_field
        print(str(framerate))
        print(framerate_field)
        print(use)
        system("ffmpeg -safe 0 -hide_banner -y -f concat -i concat.txt -i audio.opus -c copy -r " + use + " test.webm")
    else:
        print("Outputting with framerate " + str(framerate))
        system("ffmpeg -safe 0 -hide_banner -y -r " + str(framerate) +" -f concat -i concat.txt -c copy test.webm")

#system("ffmpeg -y -framerate 30 -f image2 -i frames/%04d.png -c:v libvpx-vp9 -pix_fmt yuva420p output.webm")

if __name__ == "__main__":
    clean.cleanfiles()
    populate_frames("mp4.mp4")
    do_conversion_resize()
    finalvid()