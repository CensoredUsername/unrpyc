













define config.name = _("The Question")





define gui.show_name = True




define config.version = "7.0"





define gui.about = _("""Character Art: Deji.
Original Character Art: derik.

Background Art: Mugenjohncel.
Original Background Art: DaFool

Music By: Alessio

Written By: mikey""")






define build.name = "the_question"


define build.version = "7.0"






define config.has_sound = True
define config.has_music = True
define config.has_voice = False
























define config.enter_transition = dissolve
define config.exit_transition = dissolve




define config.after_load_transition = None




define config.end_game_transition = None
















define config.window = "auto"




define config.window_show_transition = Dissolve(.2)
define config.window_hide_transition = Dissolve(.2)







default preferences.text_cps = 0





default preferences.afm_time = 15
















define config.save_directory = "the_question-7"






define config.window_icon = "gui/window_icon.png"






init python:


    config.searchpath.append(config.renpy_base + "/sdk-fonts")
    build.classify_renpy("sdk-fonts/**", "all")
    build._sdk_fonts = True




















    build.classify('**~', None)
    build.classify('**.bak', None)
    build.classify('**/.**', None)
    build.classify('**/#**', None)
    build.classify('**/thumbs.db', None)









    build.documentation('*.html')
    build.documentation('*.txt')











define build.itch_project = "renpytom/the-question"



define config.console = True
# Decompiled by unrpyc: https://github.com/CensoredUsername/unrpyc
