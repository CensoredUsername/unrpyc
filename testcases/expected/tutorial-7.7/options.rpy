













define config.name = _("Ren'Py Tutorial Game")





define gui.show_name = False




define config.version = renpy.version_string
define build.version = renpy.version_only




define gui.about = _("")






define build.name = "tutorial_7"







define config.has_sound = True
define config.has_music = True
define config.has_voice = True
























define config.enter_transition = dissolve
define config.exit_transition = dissolve




define config.after_load_transition = None




define config.end_game_transition = None
















define config.window = "auto"




define config.window_show_transition = Dissolve(.2)
define config.window_hide_transition = Dissolve(.2)







default preferences.text_cps = 0





default preferences.afm_time = 15
















define config.save_directory = "tutorial-7"






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














init python hide:
    import datetime

    today = datetime.date.today()
    if (today.month == 3) and (today.day == 19):
        
        
        config.mouse = { 'default' : [
            ("gui/mouse0.png", 0, 0),
            ("gui/mouse1.png", 0, 0),
            ("gui/mouse2.png", 0, 0),
            ("gui/mouse1.png", 0, 0),
        ] * 2 + [
            ("gui/mouse0.png", 0, 0),
        ] * (10 * 20)
}

define config.defer_tl_scripts = True
# Decompiled by unrpyc: https://github.com/CensoredUsername/unrpyc
