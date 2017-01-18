#!/usr/bin/env python
"""
<Program Name>
  uptane_banners.py

<Author>
  Lukas Puehringer <lukas.puehringer@nyu.edu>

<Started>
  Jan 10, 2017

<Copyright>
  See LICENSE for licensing information.

<Purpose>
  Provides functions to read text files (e.g. ASCII art) and print them
  horizontally centered to a bash terminal.

"""
import os
import time
import textwrap
import demo
from demo.uptane_sounds import (play,
  TADA, WON, LOST, LOST2, SATAN, WITCH, DOOMED, ICE, ICE2)
from subprocess import Popen, call, PIPE

# Bash font color escape sequences
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
DARK_BLUE = "\033[38;5;20m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[97m"

# Bash background color escape sequences
BLACK_BG = "\033[40m"
BLUE_BG = "\033[44m"
DARK_BLUE_BG = "\033[48;5;20m"
WHITE_BG = "\033[107m"
GRAY_BG = "\033[100m"
RED_BG = "\033[41m"
MAGENTA_BG = "\033[45m"
GREEN_BG = "\033[42m"
YELLOW_BG = "\033[43m"

RESET_COLOR = '\033[0m'

def get_screen_size():
  """Calls bash command `stty size` and returns standard output, i.e.
  width and height of current terminal (blocking call). """
  process = Popen('stty size', shell=True, stdout=PIPE)
  process.wait()
  rows, cols = process.stdout.read().split()
  return int(rows), int(cols)


def clear_screen():
  """Calls bash command `clear`, clears the current terminal (blocking call). """
  call('clear')


def load_banner(file_path):
  """Loads text from file, appends each line to an array and returns array. """
  banner = open(file_path, 'r').read()
  return banner.split("\n")



def print_banner(banner_array, show_for=False, color=False, color_bg=False,
    text=False, sound=False):
  """
  <Purpose>
    Clears current terminal window and prints passed banner array and
    optionally passed text.
    The banner and the text centered horizontally.

    Font color and background color are ignored for the text. The text is
    framed with the background color.


  <Arguments>
    banner_array:
      Array of string (lines to print)

    show_for: (optional)
      If passed, sleep for given time (in seconds) and then clears the screen.
      Note, if a sound is passed as well, the show_for time is added to the
      duration of the sound

    color: (optional)
      If passed, fills the banner font. Use one of the constants above.

    color_bg: (optional)
      If passed, fills the banner background. Use one of the constants above.

    text: (optional)
      Text to be displayed below the banner. Can be a string or a list.
      If it is a string the lines are split at "\n". Additionally the text
      is wrapped to fit the width of the current terminal minus a hard-coded
      margin.

    sound: (optional)
      If passed and one of the required command line player can be found,
      the sound is played in a subprocess at the passed path (blocking).

  <Exceptions>
    Exception if banner width exceeds terminal width
    Exception if banner height plus text height exceed terminal height

  <Side Effects>
    Clears terminal and prints passed banner to terminal

  <Returns>
    None
  """

  rows, cols = get_screen_size()
  content_height = 0

  # Get left padding
  banner_width = len(max(banner_array, key=len))

  if banner_width > cols:
    raise Exception("Banner width exceeds terminal width.")
  elif banner_width == cols:
    left_fill = 0
  else:
    left_fill = int((cols - banner_width) / 2)

  clear_screen()

  # Print banner, horizontally left and right padded
  for line in banner_array:
    right_fill = cols - left_fill - len(line)
    # Right and left fill with spaces (for alignment and background color)
    output = (left_fill * " ") + line + (right_fill * " ")
    if color:
      output = color + output

    if color_bg:
      output = color_bg + output

    if color or color_bg:
      output += RESET_COLOR

    print(output)

  # Text can be a list or an \n separated string
  text_array = []
  if text:
    margin_len = 10
    if not isinstance(text, list):
      text = text.split("\n")

    # Wrap line if it is too long
    for line in text:
      text_array += textwrap.wrap(line, cols - 2 * margin_len)

    # Raise exception if banner and text exceed terminal height
    if len(banner_array) + len(text_array) > rows:
      raise Exception("Text exceeds terminal height.")

    for output in text_array:
      output_width = cols - 2 * margin_len
      margin = " " * margin_len

      if color_bg:
        margin = (color_bg + margin + RESET_COLOR)

      output = "{margin}{output:^{width}}{margin}".format(
          margin=margin,
          output=output,
          width=output_width)

      print(output)


  # Fill bottom if color_bg is specified
  if color_bg:
    for i in range(rows - (len(banner_array) + len(text_array)) - 1):
      print(color_bg + cols * " " + RESET_COLOR)

  if sound:
    play(sound, True)

  if show_for:
    time.sleep(show_for)
    clear_screen()


BANNER_UPDATED = load_banner(demo.DEMO_DIR + "/ascii/updated.txt")
BANNER_DEFENDED = load_banner(demo.DEMO_DIR + "/ascii/defended.txt")
BANNER_FROZEN = load_banner(demo.DEMO_DIR + "/ascii/frozen.txt")
BANNER_HACKED = load_banner(demo.DEMO_DIR + "/ascii/hacked.txt")
BANNER_COMPROMISED = load_banner(demo.DEMO_DIR + "/ascii/compromised.txt")
BANNER_REPLAY = load_banner(demo.DEMO_DIR + "/ascii/replay.txt")
BANNER_NO_UPDATE = load_banner(demo.DEMO_DIR + "/ascii/no_update.txt")
BANNER_NO_UPDATE_NEEDED = load_banner(demo.DEMO_DIR + "/ascii/no_update_needed.txt")

def main():

  while True:
    preview_all_banners()


def preview_all_banners():
  text = "The details of the update or attack will appear here."

  #print_banner(BANNER_UPDATED, color=GREEN, show_for=3, text=text, sound=WON)
  print_banner(BANNER_UPDATED, color=WHITE+GREEN_BG, show_for=1, text=text, sound=WON)
  print_banner(BANNER_DEFENDED, color=WHITE+DARK_BLUE_BG, show_for=1, text=text, sound=TADA)
  print_banner(BANNER_FROZEN, color=CYAN+GRAY_BG, show_for=1, text=text, sound=ICE)
  #print_banner(BANNER_COMPROMISED, color=RED, color_bg=BLACK_BG, show_for=3, sound=SATAN)
  print_banner(BANNER_COMPROMISED, color=WHITE+RED_BG, show_for=1, text=text, sound=WITCH)
  #print_banner(BANNER_HACKED, color=RED, color_bg=BLACK_BG, show_for=3, text=text, sound=DOOMED)
  print_banner(BANNER_HACKED, color=WHITE+RED_BG, show_for=1, text=text, sound=DOOMED)
  #print_banner(BANNER_REPLAY, color=RED, color_bg=BLACK_BG, show_for=3, sound=WITCH)
  #print_banner(BANNER_NO_UPDATE_NEEDED, color=RED, color_bg=BLACK_BG, show_for=3)
  #print_banner(BANNER_REPLAY, color=RED, color_bg=BLACK_BG, show_for=3, sound=WITCH)
  #print_banner(BANNER_NO_UPDATE_NEEDED, color=RED, color_bg=BLACK_BG, show_for=3)
  print_banner(BANNER_REPLAY, color=WHITE+BLACK_BG, show_for=1, text=text, sound=SATAN)
  print_banner(BANNER_NO_UPDATE, color=WHITE+BLACK_BG, text=text, show_for=1)
  print_banner(BANNER_NO_UPDATE_NEEDED, color=WHITE+BLACK_BG, text=text, show_for=1)



if __name__ == "__main__":
  main()
