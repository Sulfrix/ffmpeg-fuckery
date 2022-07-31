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

clean.cleanfiles()

use_rawfield = False
framerate_field = ""

# There's an option to use an actual video or duplicate a still of the first frame of a video.
# This allows images to be resized.
if not settings.dupeframe:

    probe = ffmpeg.probe("mp4.mp4")

    system("ffmpeg -hide_banner -i mp4.mp4 -pix_fmt rgba frames/%04d.png")
    system("ffmpeg -y -hide_banner -loglevel error -i mp4.mp4 audio.opus")

    framerate_field = probe["streams"][0]["r_frame_rate"]

    if "/" in framerate_field:
        dividends = framerate_field.split("/")
        framerate = int(dividends[0])/int(dividends[1])
        use_rawfield = True
    else:
        framerate = int(framerate_field)
else:
    dupframe(settings.dupeframe_count)
    framerate = 60



print("Framerate is " + str(framerate))
delta_time = 1/framerate

#dupframe(100)

# Create the concat file that FFMPEG needs
thefile = open("./concat.txt", "w")

# For a given frame, return a new size for it. This is like a 'size formula'
def get_size(origwidth, origheight, frame, maxframe):
    return (origwidth, origheight*(sin(frame*delta_time*20)+1)/2)

framelist = listdir("./frames")
framecount = len(framelist)

for name in framelist:
    path = join("./frames/", name)
    if isfile(path):
        # Open with Pillow
        im = Image.open(path)

        width, height = im.size

        strnum = name.rsplit( ".", 1 )[ 0 ]

        framenumber = int(strnum)

        # Run size formula
        size = get_size(width, height, framenumber, framecount)

        size = (int(max(size[0], 2)), int(max(size[1], 2)))
 
        im = im.resize(size)

        im.save(path)

        print("resized " + str(framenumber) + "/" + str(framecount) + " to " + str(size))

        vidpath = "./vids/" + strnum + ".webm"

        # Now this part may be confusing and/or horrifying.
        # FFMPEG doesn't support using -concat to turn a PNG sequence into a .webm video, so EACH FRAME is converted to ITS OWN SEPERATE FILE
        # These are what FFMPEG eventually converts to a full video
        system("ffmpeg -hide_banner -loglevel error -i " + path + " " + vidpath)

        thefile.write("file '" + vidpath + "'\n")
        thefile.write("duration " + str(delta_time) + "\n")


thefile.close()

if not settings.dupeframe:
    use = str(framerate)
    if use_rawfield:
        use = framerate_field
    system("ffmpeg -y -r " + use + " -f concat -safe 0 -i concat.txt -i audio.opus -c copy test.webm")
else:
    system("ffmpeg -y -r " + str(framerate) + " -f concat -safe 0 -i concat.txt -c copy test.webm")

#system("ffmpeg -y -framerate 30 -f image2 -i frames/%04d.png -c:v libvpx-vp9 -pix_fmt yuva420p output.webm")