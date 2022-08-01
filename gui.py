from __future__ import absolute_import
import os
import io as fio

import sys

import threading
import concurrent.futures
from tracemalloc import start

import pygame
from OpenGL.GL import *
from pygame.locals import *

from imgui.integrations.pygame import PygameRenderer
import imgui
import imgui.core

import fuckery


def main():
    pygame.init()
    size = 1280, 720

    surface = pygame.display.set_mode(size, pygame.DOUBLEBUF | pygame.OPENGL | pygame.RESIZABLE)
    pygame.display.set_caption("FFMPEG Fuckery GUI")

    imgui.create_context()
    impl = PygameRenderer()

    io = imgui.get_io()
    io.display_size = size
    io.backend_flags |= imgui.BACKEND_HAS_GAMEPAD

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
                    "Setup new video...", "", False, True
                )

                if clicked_setup:
                    showsetup = True
                    showhelptext = False
                    showmainwindow = False

                clicked_clean, selected_clean = imgui.menu_item(
                    "Clean directories", "", False, True
                )

                if clicked_clean:
                    fuckery.clean.cleanfiles()
                    showmainwindow = False

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
            expanded, opened = imgui.begin("Setup", True)
            changed, input_filepath = imgui.input_text("File path", input_filepath, 256)
            if imgui.button("Initialize files"):
                fuckery.clean.cleanfiles()
                fuckery.populate_frames(input_filepath)
                fuckery.populateframecount()
                showsetup = False
                showmainwindow = True
            if imgui.button("Use existing files"):
                if os.path.exists("framerate.txt"):
                    fpsfile = open("framerate.txt", "r")
                    fuckery.framerate = fuckery.parse_framerate(fpsfile.read())
                    fpsfile.close()
                    fuckery.populateframecount()
                    showsetup = False
                    showmainwindow = True
            imgui.end()
            if not opened:
                showsetup = False

        if showmainwindow:
            #imgui.set_next_window_size(0, 0, imgui.ONCE)
            imgui.begin("Wobbler", False, imgui.WINDOW_NO_RESIZE | imgui.WINDOW_ALWAYS_AUTO_RESIZE)
            if not activeprocess:
                imgui.text("Frames to process: " + str(fuckery.globalframecount))
                dontcare, maxthreads = imgui.slider_int("Threads", maxthreads, 1, 64)
                expanded, dontcare = imgui.collapsing_header("Python size formula", None)

                if expanded:
                    dontcare, fuckery.size_formula = imgui.input_text_multiline("size formula", fuckery.size_formula, 2048, 1000, 512)
                if imgui.button("Start resizing!"):
                    fuckery.framesprocessed = 0
                    starttime = t
                    executor = concurrent.futures.ThreadPoolExecutor(max_workers = maxthreads)
                    executor.map(fuckery.do_conversion_resize, os.listdir("./frames/"))
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

        # note: cannot use screen.fill((1, 1, 1)) because pygame's screen
        #       does not support fill() on OpenGL sufraces
        glClearColor(1, 1, 1, 1)
        glClear(GL_COLOR_BUFFER_BIT)
        

        glClear(GL_COLOR_BUFFER_BIT)
        glLoadIdentity()
        glDisable(GL_LIGHTING)
        glEnable(GL_TEXTURE_2D)


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