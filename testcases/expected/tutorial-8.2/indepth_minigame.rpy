example minigame:

    init python:

        class PongDisplayable(renpy.Displayable):

            def __init__(self):

                renpy.Displayable.__init__(self)



                self.PADDLE_WIDTH = 12
                self.PADDLE_HEIGHT = 95
                self.PADDLE_X = 240
                self.BALL_WIDTH = 15
                self.BALL_HEIGHT = 15
                self.COURT_TOP = 129
                self.COURT_BOTTOM = 650



                self.paddle = Solid("#ffffff", xsize=self.PADDLE_WIDTH, ysize=self.PADDLE_HEIGHT)
                self.ball = Solid("#ffffff", xsize=self.BALL_WIDTH, ysize=self.BALL_HEIGHT)


                self.stuck = True


                self.playery = (self.COURT_BOTTOM - self.COURT_TOP) / 2
                self.computery = self.playery


                self.computerspeed = 380.0



                self.bx = self.PADDLE_X + self.PADDLE_WIDTH + 10
                self.by = self.playery
                self.bdx = .5
                self.bdy = .5
                self.bspeed = 350.0


                self.oldst = None


                self.winner = None

            def visit(self):
                return [ self.paddle, self.ball ]



            def render(self, width, height, st, at):


                r = renpy.Render(width, height)


                if self.oldst is None:
                    self.oldst = st

                dtime = st - self.oldst
                self.oldst = st


                speed = dtime * self.bspeed
                oldbx = self.bx

                if self.stuck:
                    self.by = self.playery
                else:
                    self.bx += self.bdx * speed
                    self.by += self.bdy * speed



                cspeed = self.computerspeed * dtime
                if abs(self.by - self.computery) <= cspeed:
                    self.computery = self.by
                else:
                    self.computery += cspeed * (self.by - self.computery) / abs(self.by - self.computery)




                ball_top = self.COURT_TOP + self.BALL_HEIGHT / 2
                if self.by < ball_top:
                    self.by = ball_top + (ball_top - self.by)
                    self.bdy = -self.bdy

                    if not self.stuck:
                        renpy.sound.play("pong_beep.opus", channel=0)


                ball_bot = self.COURT_BOTTOM - self.BALL_HEIGHT / 2
                if self.by > ball_bot:
                    self.by = ball_bot - (self.by - ball_bot)
                    self.bdy = -self.bdy

                    if not self.stuck:
                        renpy.sound.play("pong_beep.opus", channel=0)


                def paddle(px, py, hotside):






                    pi = renpy.render(self.paddle, width, height, st, at)



                    r.blit(pi, (int(px), int(py - self.PADDLE_HEIGHT / 2)))

                    if py - self.PADDLE_HEIGHT / 2 <= self.by <= py + self.PADDLE_HEIGHT / 2:

                        hit = False

                        if oldbx >= hotside >= self.bx:
                            self.bx = hotside + (hotside - self.bx)
                            self.bdx = -self.bdx
                            hit = True

                        elif oldbx <= hotside <= self.bx:
                            self.bx = hotside - (self.bx - hotside)
                            self.bdx = -self.bdx
                            hit = True

                        if hit:
                            renpy.sound.play("pong_boop.opus", channel=1)
                            self.bspeed *= 1.10


                paddle(self.PADDLE_X, self.playery, self.PADDLE_X + self.PADDLE_WIDTH)
                paddle(width - self.PADDLE_X - self.PADDLE_WIDTH, self.computery, width - self.PADDLE_X - self.PADDLE_WIDTH)


                ball = renpy.render(self.ball, width, height, st, at)
                r.blit(ball, (int(self.bx - self.BALL_WIDTH / 2),
                              int(self.by - self.BALL_HEIGHT / 2)))


                if self.bx < -50:
                    self.winner = "eileen"



                    renpy.timeout(0)

                elif self.bx > width + 50:
                    self.winner = "player"
                    renpy.timeout(0)



                renpy.redraw(self, 0)


                return r


            def event(self, ev, x, y, st):

                import pygame



                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    self.stuck = False


                    renpy.restart_interaction()


                y = max(y, self.COURT_TOP)
                y = min(y, self.COURT_BOTTOM)
                self.playery = y



                if self.winner:
                    return self.winner
                else:
                    raise renpy.IgnoreEvent()

    screen pong():

        default pong = PongDisplayable()

        add "bg pong field"

        add pong

        text _("Player"):
            xpos 240
            xanchor 0.5
            ypos 25
            size 40

        text _("Eileen"):
            xpos (1280 - 240)
            xanchor 0.5
            ypos 25
            size 40

        if pong.stuck:
            text _("Click to Begin"):
                xalign 0.5
                ypos 50
                size 40



label demo_minigame:

    e "You may want to mix Ren'Py with other forms of gameplay. There are a couple of ways to do this."

    e "The first is with the screen system, which can be used to display data and create button and menu based interfaces."

    e "Screens will work for many simulation-style games and RPGs."

    e "When screens are not enough, you can write a creator-defined displayable to extend Ren'Py itself. A creator-defined displayable can process raw events and draw to the screen." id demo_minigame_a92baa6b

    e "That makes it possible to create all kinds of minigames. Would you like to play some pong?"

example minigame hide:
    label play_pong:

        window hide  
        $ quick_menu = False

        call screen pong

        $ quick_menu = True
        window show

    show eileen vhappy

    if _return == "eileen":

        e "I win!"

    else:

        e "You won! Congratulations."

label pong_done:

    show eileen happy

    menu:
        e "Would you like to play again?"
        "Sure.":


            jump play_pong
        "No thanks.":


            pass

    show example minigame large

    e "Here's the source code for the minigame. It's very complex, and assumes you understand Python well."

    e "I won't go over it in detail here. You can read more about it in the {a=https://www.renpy.org/doc/html/udd.html}Creator-Defined Displayable documentation{/a}."

    hide example

    e "Minigames can spice up your visual novel, but be careful – not every visual novel player wants to be good at arcade games."

    e "Part of the reason Ren'Py works well is that it's meant for certain types of games, like visual novels and life simulations."

    e "The further afield you get from those games, the more you'll find yourself fighting Ren'Py. At some point, it makes sense to consider other engines."

    show eileen vhappy

    e "And that's fine with us. We'll always be here for you when you're making visual novels."

    show eileen happy

    return
# Decompiled by unrpyc: https://github.com/CensoredUsername/unrpyc
