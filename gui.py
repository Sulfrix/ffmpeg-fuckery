from __future__ import absolute_import
import json
from math import sin, cos, pi
import os
import io as fio
import string

import sys
from enum import Enum
import threading
import concurrent.futures
from tracemalloc import start

import pygame
from OpenGL.GL import *
from pygame.locals import *

import tkinter
import tkinter.filedialog

from imgui.integrations.pygame import PygameRenderer
import imgui
import imgui.core

import fuckery

def lerp(A, B, C):
    return (C * A) + ((1-C) * B)


# Thanks to https://stackoverflow.com/questions/63801960/how-to-prompt-user-to-open-a-file-with-python3-pygame
def prompt_normal_file():
    top = tkinter.Tk()
    top.withdraw()
    filename = tkinter.filedialog.askopenfilename(parent=top)
    top.destroy()
    return filename

def prompt_file():
    top = tkinter.Tk()
    top.withdraw()
    filename = tkinter.filedialog.askopenfilename(parent=top, filetypes=[('JSON files', '*.json'), ('All files', '*.*')])
    top.destroy()
    return filename

def prompt_video_file():
    top = tkinter.Tk()
    top.withdraw()
    filename = tkinter.filedialog.askopenfilename(parent=top, filetypes=[('MP4 files', '*.mp4')])
    top.destroy()
    return filename

def prompt_save_file():
    top = tkinter.Tk()
    top.withdraw()
    filename = tkinter.filedialog.asksaveasfilename(parent=top, filetypes=[('JSON files', '*.json'), ('All files', '*.*')])
    top.destroy()
    return filename

class EasingMode(Enum):
    SNAP = 0
    LINEAR = 1
    SIN_EASE_IN = 2
    SIN_EASE_OUT = 3
    SIN_EASE_INOUT = 4

class PropTimeline:
    def __init__(self, name: str, default_value: float):
        self.name = name
        self.keyframes = [Keyframe(1, default_value, EasingMode.SNAP)]

    def updatekeys(self):
        def sortfunc(fr: Keyframe):
            return fr.time
        self.keyframes.sort(key=sortfunc)
    
    def get_value_at(self, time: float):
        lastkey, nextkey = self.lastkey_and_nextkey(time)
        if not lastkey:
            return nextkey.lerp(None, time)
        return lastkey.lerp(nextkey, time)

    def lastkey_and_nextkey(self, time: float):
        if len(self.keyframes) == 1:
            return (self.keyframes[0], None)
        for i in range(len(self.keyframes)):
            key = self.keyframes[i]
            if key.time == time:
                return (key, None)
            if key.time > time:
                if i == 0:
                    return (None, key)
                return (self.keyframes[i-1], key)
        return (self.keyframes[len(self.keyframes)-1], None)
            
    def dictify(self):
        dictkeyframes = []
        for kf in self.keyframes:
            dictkeyframes.append(kf.dictify())
        dict = {
            "name": self.name,
            "keyframes": dictkeyframes
        }
        return dict

    def parse(dict):
        output = PropTimeline(dict["name"], 0)
        kfarr = []
        for v in dict["keyframes"]:
            kfarr.append(Keyframe.parse(v))
        output.keyframes = kfarr
        return output
        

class Keyframe:
    def __init__(self, time: float, value: float, easing_mode: EasingMode):
        self.time = time
        self.value = value
        self.easing_mode = easing_mode

    # Self will always be the preceding keyframe, with 'other' being the next one.
    def lerp(self, other, time: float):
        if not other:
            return self.value
        timeahead = time - self.time
        between = other.time - self.time
        frac = timeahead/between
        if frac <= 0:
            return self.value
        if frac >= 1:
            return other.value
        match self.easing_mode:
            case EasingMode.SNAP:
                return self.value
            case EasingMode.LINEAR:
                return lerp(other.value, self.value, frac)
            case EasingMode.SIN_EASE_IN:
                return lerp(other.value, self.value, 1 - cos((frac * pi) / 2))
            case EasingMode.SIN_EASE_OUT:
                return lerp(other.value, self.value, sin((frac * pi) / 2))
            case EasingMode.SIN_EASE_INOUT:
                return lerp(other.value, self.value, -(cos(pi * frac) - 1) / 2)
            case _:
                return self.value
    
    def dictify(self):
        dict = {
            "time": self.time,
            "value": self.value,
            "easing_mode": self.easing_mode.value
        }
        return dict

    def parse(dict):
        return Keyframe(dict["time"], dict["value"], EasingMode(dict["easing_mode"]))


class VideoProject:
    def __init__(self, size, vidpath):
        self.defaultsize = size
        self.vidpath = vidpath
        self.timelines = [
            PropTimeline("width", size[0]),
            PropTimeline("height", size[1]),
            PropTimeline("sizepercent", 100)
        ]

    def get_size_at_time(self, time: float):
        mult = self.timelines[2].get_value_at(time)/100
        output = (self.timelines[0].get_value_at(time)*mult, self.timelines[1].get_value_at(time)*mult)
        #print(output)
        return output

    def dictify(self):
        dicttimelines = []
        for tl in self.timelines:
            dicttimelines.append(tl.dictify())
        dict = {
            "defaultsize": self.defaultsize,
            "timelines": dicttimelines,
            "vidpath": self.vidpath
        }
        return dict

    def parse(dict):
        output = VideoProject((dict["defaultsize"][0], dict["defaultsize"][1]), dict["vidpath"])
        tlarr = []
        for v in dict["timelines"]:
            tlarr.append(PropTimeline.parse(v))
        output.timelines = tlarr
        return output

path_memory = None

def main():
    global path_memory
    pygame.init()
    size = 1280, 720

    surface = pygame.display.set_mode(size, pygame.DOUBLEBUF | pygame.OPENGL | pygame.RESIZABLE)
    pygame.display.set_caption("FFMPEG Fuckery GUI")

    imgui.create_context()
    impl = PygameRenderer()

    io = imgui.get_io()
    io.display_size = size

    showsetup = False
    showmainwindow = False

    future = None

    activeprocess = False
    #imgui.push_style_var(imgui.STYLE_WINDOW_MIN_SIZE, (400, 300))

    input_filepath = "mp4.mp4"

    pygame.key.set_repeat(300, 100)
    getTicksLastFrame = 0

    runtime = None
    starttime = None

    maxthreads = 6

    showhelptext = True

    proj = None

    

    def dosave(force_ask):
        global path_memory
        if not path_memory or force_ask:
            path_memory = prompt_save_file()
        if path_memory:
            with open(path_memory, "w") as outfile:
                json.dump(proj.dictify(), outfile)


    info = pygame.display.Info()
    glViewport(0, 0, info.current_w, info.current_h)
    glDepthRange(0, 1)
    glMatrixMode(GL_PROJECTION)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    glShadeModel(GL_SMOOTH)
    glClearColor(0.0, 0.0, 0.0, 0.0)
    glClearDepth(1.0)
    glDisable(GL_DEPTH_TEST)
    glDisable(GL_LIGHTING)
    glDepthFunc(GL_LEQUAL)
    glHint(GL_PERSPECTIVE_CORRECTION_HINT, GL_NICEST)
    glEnable(GL_BLEND)
    
    texID = glGenTextures(1)
    def surfaceToTexture( pygame_surface ):
        
        rgb_surface = pygame.image.tostring( pygame_surface, 'RGB')
        glBindTexture(GL_TEXTURE_2D, texID)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP)
        surface_rect = pygame_surface.get_rect()
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, surface_rect.width, surface_rect.height, 0, GL_RGB, GL_UNSIGNED_BYTE, rgb_surface)
        glGenerateMipmap(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, 0) 

    deffont = io.fonts.add_font_from_file_ttf("Roboto-Regular.ttf", 16)
    pygamefont = pygame.font.Font("Roboto-Regular.ttf", 16)
    text = pygamefont.render("File > Setup new video... to get started", True, (0, 0, 0))
    offscreen = pygame.Surface(size) # A generic pyGame surface is used so i don't have to deal with OpenGL. I only need OpenGL for Dear Imgui.
    
    impl.refresh_font_texture()


    editor_selected_timeline = 0
    editor_keyframe_index = 0

    framecache = {}

    previewframe = 1

    previewfollowskey = False

    preview_surf = None
    scaled_preview = None
    lastsize = (-1, -1)
    lastframe = -1
    preview_size = (0, 0)

    while 1:
        

        t = pygame.time.get_ticks()
        # deltaTime in seconds.
        deltaTime = (t - getTicksLastFrame) / 1000.0
        getTicksLastFrame = t

        io.delta_time = deltaTime

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit()

            if event.type == pygame.VIDEORESIZE:
                print("Resize detected")
                size = (int(event.w), int(event.h))
                pygame.display.set_mode(size, pygame.display.get_surface().get_flags())
                offscreen = pygame.Surface(size)

            impl.process_event(event)

        offscreen.fill((255, 255, 255))
        if showhelptext:
            offscreen.blit(text, (0, 20))

        imgui.new_frame()

        imgui.push_font(deffont)

        if imgui.begin_main_menu_bar():
            if imgui.begin_menu("File", True):

                clicked_quit, selected_quit = imgui.menu_item(
                    "Quit", '', False, True
                )

                if clicked_quit:
                    exit(1)

                clicked_setup, selected_setup = imgui.menu_item(
                    "New...", "", False, True
                )

                if clicked_setup:
                    showsetup = True
                    showhelptext = False
                    showmainwindow = False
                    framecache = {}

                    previewframe = 1

                    previewfollowskey = False

                    preview_surf = None
                    scaled_preview = None
                    lastsize = (-1, -1)
                    lastframe = -1
                    preview_size = (0, 0)

                clicked_open, no = imgui.menu_item(
                    "Open...", "", False, True
                )

                if clicked_open:
                    prmt = prompt_file()
                    if prmt:
                        with open(prmt, 'r') as openfile:
                            proj = VideoProject.parse(json.load(openfile))
                        path_memory = prmt
                        fuckery.clean.cleanfiles()
                        fuckery.populate_frames(proj.vidpath)
                        fuckery.populateframecount()
                        fuckery.populatevidsize()
                        showsetup = False
                        showmainwindow = True
                        showhelptext = False
                        editor_selected_timeline = 0
                        editor_keyframe_index = 0
                        framecache = {}

                        previewframe = 1

                        previewfollowskey = False

                        preview_surf = None
                        scaled_preview = None
                        lastsize = (-1, -1)
                        lastframe = -1
                        preview_size = (0, 0)

                clicked_open_quick, no = imgui.menu_item(
                    "Open (Unsafe)...", "", False, True
                )

                if clicked_open_quick:
                    prmt = prompt_file()
                    if prmt:
                        with open(prmt, 'r') as openfile:
                            proj = VideoProject.parse(json.load(openfile))
                        if os.path.exists("framerate.txt"):
                            path_memory = prmt
                            fpsfile = open("framerate.txt", "r")
                            fuckery.framerate = fuckery.parse_framerate(fpsfile.read())
                            fpsfile.close()
                            fuckery.populateframecount()
                            fuckery.populatevidsize()
                            proj = VideoProject(fuckery.vidsize, proj.vidpath)
                            showsetup = False
                            showmainwindow = True
                            showhelptext = False
                            editor_selected_timeline = 0
                            editor_keyframe_index = 0
                            framecache = {}

                            previewframe = 1

                            previewfollowskey = False

                            preview_surf = None
                            scaled_preview = None
                            lastsize = (-1, -1)
                            lastframe = -1
                            preview_size = (0, 0)

                cansave = False
                if proj:
                    cansave = True

                title = "Save"
                if not path_memory:
                    title = "Save..."

                clicked_save, no = imgui.menu_item(
                    title, "", False, cansave
                )

                if clicked_save:
                    dosave(False)

                clicked_save_as, no = imgui.menu_item(
                    "Save As...", "", False, cansave
                )

                if clicked_save_as:
                    dosave(True)

                clicked_clean, selected_clean = imgui.menu_item(
                    "Close project and clean", "", False, True
                )

                if clicked_clean:
                    fuckery.clean.cleanfiles()
                    showmainwindow = False
                    proj = None

                imgui.end_menu()
            if imgui.begin_menu("Debug", True):

                clicked_view, selected_view = imgui.menu_item(
                    "View test.webm (output) in mpv", '', False, True
                )

                if clicked_view:
                    os.system("mpv ./test.webm")

                clicked_view, selected_view = imgui.menu_item(
                    "View test.webm (output) in default media viewer", '', False, True
                )

                if clicked_view:
                    os.system("test.webm")
                
                imgui.end_menu()
            imgui.end_main_menu_bar()

        #imgui.show_test_window()

        if showsetup:
            expanded, opened = imgui.begin("New Project", True)
            if imgui.button("Browse"):
                input_filepath = prompt_video_file()
            imgui.same_line()
            changed, input_filepath = imgui.input_text("File path", input_filepath, 256)
            if imgui.button("Create Project"):
                fuckery.clean.cleanfiles()
                fuckery.populate_frames(input_filepath)
                fuckery.populateframecount()
                fuckery.populatevidsize()
                proj = VideoProject(fuckery.vidsize, input_filepath)
                showsetup = False
                showmainwindow = True
                editor_selected_timeline = 0
                editor_keyframe_index = 0
            if imgui.button("Use existing files"):
                if os.path.exists("framerate.txt"):
                    fpsfile = open("framerate.txt", "r")
                    fuckery.framerate = fuckery.parse_framerate(fpsfile.read())
                    fpsfile.close()
                    fuckery.populateframecount()
                    fuckery.populatevidsize()
                    proj = VideoProject(fuckery.vidsize, input_filepath)
                    showsetup = False
                    showmainwindow = True
                    editor_selected_timeline = 0
                    editor_keyframe_index = 0
            imgui.end()
            if not opened:
                showsetup = False

        

        if showmainwindow:
            #imgui.set_next_window_size(0, 0, imgui.ONCE)
            imgui.begin("Wobbler", False, imgui.WINDOW_NO_RESIZE | imgui.WINDOW_ALWAYS_AUTO_RESIZE)
            if not activeprocess:
                imgui.text("Frames to process: " + str(fuckery.globalframecount))
                dontcare, maxthreads = imgui.slider_int("Threads", maxthreads, 1, 64)
                if imgui.button("Start resizing!"):
                    fuckery.framesprocessed = 0
                    fuckery.workproj = proj
                    starttime = t
                    manuallabor = False
                    if not manuallabor:
                        executor = concurrent.futures.ThreadPoolExecutor(max_workers = maxthreads)
                        executor.map(fuckery.do_conversion_resize, os.listdir("./frames/"))
                    else:
                        for name in os.listdir("./frames"):
                            fuckery.workone(name)
                    #fuckery.workone("0001.png")
                    activeprocess = True
                    #S
                if runtime:
                    imgui.text("Approximate render time: " + str(runtime/1000.0))
            else:
                frac = (fuckery.framesprocessed/fuckery.globalframecount)
                imgui.text("Please wait...")
                imgui.text("Frames processed: " + str(fuckery.framesprocessed) + "/" + str(fuckery.globalframecount) + " (" + str(int(frac*100)) + "%)")
                x, y = imgui.get_cursor_screen_pos()
                draw_list = imgui.get_window_draw_list()
                prog_w = 200
                prog_h = 10
                draw_list.add_rect_filled(x, y, x+prog_w, y+prog_h, imgui.get_color_u32_rgba(0.2,0.2,0.2,1))
                draw_list.add_rect_filled(x, y, x+(prog_w*frac), y+prog_h, imgui.get_color_u32_rgba(0.2,0.4,0.8,1))
                cur = imgui.get_cursor_pos()
                cur = (cur[0], cur[1]+prog_h)
                imgui.set_cursor_pos(cur)
                if fuckery.framesprocessed == fuckery.globalframecount:
                    fuckery.spitConcatFile()
                    fuckery.finalvid()
                    activeprocess = False
                    runtime = t - starttime
            imgui.end()


            if not activeprocess:
                imgui.begin("Size Key Editor", False, imgui.WINDOW_NO_RESIZE | imgui.WINDOW_ALWAYS_AUTO_RESIZE)
                if (imgui.button("Dump")):
                    print (json.dumps(proj.dictify(), indent=4))
                imgui.text("Video size: " + str(proj.defaultsize))
                dontcare, previewfollowskey = imgui.checkbox("Preview current keyframe", previewfollowskey)
                timechanged, previewframe = imgui.slider_int("Preview frame", previewframe, 1, fuckery.globalframecount)
                imgui.text("Timeline ID: " + str(editor_selected_timeline))
                items = list(map(lambda x: x.name, proj.timelines))
                tl_changed, editor_selected_timeline = imgui.combo("Property timeline", editor_selected_timeline, items)
                if tl_changed:
                    editor_keyframe_index = 0
                curtl = proj.timelines[editor_selected_timeline]
                kf_changed, editor_keyframe_index = imgui.slider_int("Keyframe", editor_keyframe_index, 0, len(curtl.keyframes)-1)
                if kf_changed:
                    if previewfollowskey:
                        previewframe = curtl.keyframes[editor_keyframe_index].time
                curkf = curtl.keyframes[editor_keyframe_index]
                cursor = imgui.get_cursor_pos()
                scur = imgui.get_cursor_screen_pos()
                draw_list = imgui.get_window_draw_list()
                tlw = 400
                tlh = 20
                kfw = 1
                kfh = 6
                draw_list.add_rect_filled(scur[0], scur[1], scur[0]+tlw, scur[1]+tlh, imgui.get_color_u32_rgba(0.5, 0.5, 0.5, 1))
                for i in range(len(curtl.keyframes)):
                    kf = curtl.keyframes[i]
                    xpos = scur[0]+((tlw-kfw)*((kf.time-1)/(fuckery.globalframecount-1)))
                    color = imgui.get_color_u32_rgba(59/255, 118/255, 255/255, 1)
                    if kf == curkf:
                        color = imgui.get_color_u32_rgba(0.5, 1, 0.8, 1)
                    draw_list.add_rect_filled(xpos, scur[1], xpos+kfw, scur[1]+tlh, color)
                    draw_list.add_circle_filled(xpos, scur[1]+tlh/2, kfh, color, 4)
                xpos = scur[0]+((tlw-kfw)*((previewframe-1)/(fuckery.globalframecount-1)))
                draw_list.add_rect_filled(xpos, scur[1], xpos+kfw, scur[1]+tlh, imgui.get_color_u32_rgba(1, 0, 0, 1))
                cursor = (cursor[0], cursor[1]+tlh+4)
                imgui.set_cursor_pos(cursor)
                if imgui.button("Add keyframe"):
                    curkf = Keyframe(curkf.time+1, curkf.value, curkf.easing_mode)
                    curtl.keyframes.append(curkf)
                    curtl.updatekeys()
                    editor_keyframe_index = curtl.keyframes.index(curkf)
                    if previewfollowskey:
                        previewframe = curtl.keyframes[editor_keyframe_index].time
                imgui.same_line()
                if imgui.button("Remove keyframe"):
                    if editor_keyframe_index > 1:
                        editor_keyframe_index = editor_keyframe_index - 1
                        curtl.keyframes.remove(curkf)
                    if previewfollowskey:
                        previewframe = curtl.keyframes[editor_keyframe_index].time
                if imgui.button("Prev. keyframe"):
                    editor_keyframe_index = editor_keyframe_index - 1
                    if editor_keyframe_index < 0:
                        editor_keyframe_index = len(curtl.keyframes)-1
                    if previewfollowskey:
                        previewframe = curtl.keyframes[editor_keyframe_index].time
                imgui.same_line()
                if imgui.button("Next keyframe"):
                    editor_keyframe_index = editor_keyframe_index + 1
                    if editor_keyframe_index == len(curtl.keyframes):
                        editor_keyframe_index = 0
                    if previewfollowskey:
                        previewframe = curtl.keyframes[editor_keyframe_index].time
                valuechanged, curkf.value = imgui.drag_int("Keyframe value", curkf.value, 1, 2, 2000)
                timechanged, curkf.time = imgui.slider_int("Keyframe time position", curkf.time, 1, fuckery.globalframecount)
                if timechanged:
                    curtl.updatekeys()
                    editor_keyframe_index = curtl.keyframes.index(curkf)
                    if previewfollowskey:
                        previewframe = curkf.time
                    

                imgui.text("Easing ID: " + str(curkf.easing_mode.value))
                easechanged, easeindex = imgui.combo("Easing type", curkf.easing_mode.value, list(map(lambda x: x.name, EasingMode)))
                if easechanged:
                    curkf.easing_mode = EasingMode(easeindex)

                #imgui.text("Timeline ID: " + str(editor_selected_timeline))
                imgui.end()

                strtime = str(previewframe)
                if not strtime in framecache:
                    framecache[strtime] = pygame.image.load("./frames/" + strtime.zfill(4) + ".png")
                    preview_surf = framecache[strtime]
                else:
                    preview_surf = framecache[strtime]
                preview_size = proj.get_size_at_time(previewframe)

        # note: cannot use screen.fill((1, 1, 1)) because pygame's screen
        #       does not support fill() on OpenGL sufraces
        glClearColor(1, 1, 1, 1)
        glClear(GL_COLOR_BUFFER_BIT)
        

        glClear(GL_COLOR_BUFFER_BIT)
        glLoadIdentity()
        glDisable(GL_LIGHTING)
        glEnable(GL_TEXTURE_2D)

        if preview_surf:
            if lastsize != preview_size or lastframe != previewframe:
                scaled_preview = pygame.transform.scale(preview_surf, preview_size)
                lastsize = preview_size
                lastframe = previewframe
            offscreen.blit(scaled_preview, (0, 20))


        surfaceToTexture(offscreen)
        glBindTexture(GL_TEXTURE_2D, texID)
        #imgui.set_next_window_size(1280/3, 720/3)
        #imgui.begin("Testing window.", False, imgui.WINDOW_NO_SCROLLBAR | imgui.WINDOW_NO_TITLE_BAR | imgui.WINDOW_NO_RESIZE | imgui.WINDOW_ALWAYS_AUTO_RESIZE | imgui.WINDOW_NO_SAVED_SETTINGS)
        #imgui.image(texID, 1280/3, 720/3)
        #imgui.end()
        glBegin(GL_QUADS)
        glTexCoord2f(0, 0); glVertex2f(-1, 1)
        glTexCoord2f(0, 1); glVertex2f(-1, -1)
        glTexCoord2f(1, 1); glVertex2f(1, -1)
        glTexCoord2f(1, 0); glVertex2f(1, 1)
        glEnd()

        imgui.pop_font()
        imgui.render()
        impl.render(imgui.get_draw_data())

        pygame.display.flip()
        pygame.time.Clock().tick(300)


if __name__ == "__main__":
    main()