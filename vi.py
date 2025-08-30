#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Minimal vi editor with Chinese support
"""

import curses
import curses.ascii
import sys
import os
import locale

# Set locale for UTF-8 support
locale.setlocale(locale.LC_ALL, '')

class Editor:
    def __init__(self, filename=None):
        self.filename = filename
        self.buffer = [""]
        self.pos = (0, 0)  # (line, column)
        self.mode = "command"  # command, insert, visual
        self.visual_start = None
        self.utf8buffer = []
        self.load_file()

    def load_file(self):
        if self.filename and os.path.exists(self.filename):
            with open(self.filename, 'r', encoding='utf-8') as f:
                self.buffer = [line.rstrip('\n\r') for line in f.readlines()]
                if not self.buffer:
                    self.buffer = [""]

    def save_file(self):
        if self.filename:
            with open(self.filename, 'w', encoding='utf-8') as f:
                for line in self.buffer:
                    f.write(line + '\n')

    def main_loop(self, stdscr):
        self.stdscr = stdscr
        curses.use_default_colors()
        self.maxy, self.maxx = stdscr.getmaxyx()
        self.refresh()
        while True:
            ch = stdscr.getch()
            if not self.handle_input(ch):
                break

    def handle_input(self, ch):
        if self.mode == "command":
            return self.handle_command(ch)
        elif self.mode == "insert":
            return self.handle_insert(ch)
        elif self.mode == "visual":
            return self.handle_visual(ch)
        return True

    def handle_command(self, ch):
        if ch == ord('i'):
            self.mode = "insert"
        elif ch == ord('a'):
            if self.pos[1] < len(self.buffer[self.pos[0]]):
                self.pos = (self.pos[0], self.pos[1] + 1)
            self.mode = "insert"
        elif ch == ord('v'):
            self.mode = "visual"
            self.visual_start = self.pos
        elif ch == ord('h'):
            if self.pos[1] > 0:
                self.pos = (self.pos[0], self.pos[1] - 1)
        elif ch == ord('l'):
            if self.pos[1] < len(self.buffer[self.pos[0]]):
                self.pos = (self.pos[0], self.pos[1] + 1)
        elif ch == ord('j'):
            if self.pos[0] < len(self.buffer) - 1:
                next_line_len = len(self.buffer[self.pos[0] + 1])
                self.pos = (self.pos[0] + 1, min(self.pos[1], next_line_len))
        elif ch == ord('k'):
            if self.pos[0] > 0:
                prev_line_len = len(self.buffer[self.pos[0] - 1])
                self.pos = (self.pos[0] - 1, min(self.pos[1], prev_line_len))
        elif ch == ord(':'):
            self.handle_ex_command()
        self.refresh()
        return True

    def handle_insert(self, ch):
        s = None
        if ch < 256 and ch != 27:
            try:
                s = bytes(self.utf8buffer + [ch]).decode("utf-8")
                self.utf8buffer = []
            except UnicodeDecodeError:
                self.utf8buffer.append(ch)
        else:
            self.utf8buffer = []

        if ch == 27:  # ESC
            self.mode = "command"
            if self.pos[1] > 0:
                self.pos = (self.pos[0], self.pos[1] - 1)
        elif ch == 10:  # Enter
            line = self.buffer[self.pos[0]]
            self.buffer[self.pos[0]] = line[:self.pos[1]]
            self.buffer.insert(self.pos[0] + 1, line[self.pos[1]:])
            self.pos = (self.pos[0] + 1, 0)
        elif ch == curses.KEY_BACKSPACE or ch == 127:
            if self.pos[1] > 0:
                line = self.buffer[self.pos[0]]
                self.buffer[self.pos[0]] = line[:self.pos[1]-1] + line[self.pos[1]:]
                self.pos = (self.pos[0], self.pos[1] - 1)
        elif s and not curses.ascii.isctrl(chr(ch)):
            line = self.buffer[self.pos[0]]
            self.buffer[self.pos[0]] = line[:self.pos[1]] + s + line[self.pos[1]:]
            self.pos = (self.pos[0], self.pos[1] + len(s))
        self.refresh()
        return True

    def handle_visual(self, ch):
        if ch == 27:  # ESC
            self.mode = "command"
            self.visual_start = None
        elif ch == ord('d'):
            # Delete visual selection
            start_line, start_col = self.visual_start
            end_line, end_col = self.pos
            if start_line > end_line or (start_line == end_line and start_col > end_col):
                start_line, end_line = end_line, start_line
                start_col, end_col = end_col, start_col
            if start_line == end_line:
                line = self.buffer[start_line]
                self.buffer[start_line] = line[:start_col] + line[end_col:]
                self.pos = (start_line, start_col)
            else:
                # Multi-line delete
                self.buffer[start_line] = self.buffer[start_line][:start_col] + self.buffer[end_line][end_col:]
                del self.buffer[start_line+1:end_line+1]
                self.pos = (start_line, start_col)
            self.mode = "command"
            self.visual_start = None
        elif ch == ord('y'):
            # Yank visual selection
            self.mode = "command"
            self.visual_start = None
        elif ch in (ord('h'), ord('j'), ord('k'), ord('l')):
            self.handle_command(ch)
        self.refresh()
        return True

    def handle_ex_command(self):
        # Simple :w and :q
        curses.echo()
        self.stdscr.addstr(self.maxy-1, 0, ":")
        try:
            cmd_bytes = self.stdscr.getstr(self.maxy-1, 1, 10)
            cmd = cmd_bytes.decode('utf-8') if cmd_bytes else ""
        except:
            cmd = ""
        curses.noecho()
        if cmd == 'w':
            self.save_file()
        elif cmd == 'q':
            return False
        elif cmd == 'wq':
            self.save_file()
            return False
        return True

    def pos2buffer(self, pos):
        """Convert screen position to buffer position, handling wide characters"""
        y, x = pos
        line = self.buffer[y]
        p = 0
        i = 0
        for i, c in enumerate(line):
            if p >= x:
                return i
            width = 2 if ord(c) > 127 else 1  # Simple wide char detection
            p += width
        return i + (x - p) + 1

    def buffer2x(self, y, p):
        """Convert buffer position to screen x, handling wide characters"""
        x = 0
        for c in self.buffer[y][:p]:
            width = 2 if ord(c) > 127 else 1
            x += width
        return x

    def refresh(self):
        # Avoid full clear to prevent flickering, only update changed lines
        for i, line in enumerate(self.buffer):
            if i >= self.maxy - 1:
                break
            # Clear the line and redraw
            self.stdscr.move(i, 0)
            self.stdscr.clrtoeol()
            try:
                self.stdscr.addstr(i, 0, line[:self.maxx-1])
            except curses.error:
                pass

        # Status line
        self.stdscr.move(self.maxy-1, 0)
        self.stdscr.clrtoeol()
        status = f"-- {self.mode.upper()} --"
        if self.filename:
            status += f" {self.filename}"
        try:
            self.stdscr.addstr(self.maxy-1, 0, status[:self.maxx-1])
        except curses.error:
            pass

        # Fill remaining lines with ~
        for i in range(len(self.buffer), self.maxy-1):
            self.stdscr.move(i, 0)
            self.stdscr.clrtoeol()
            try:
                self.stdscr.addstr(i, 0, "~")
            except curses.error:
                pass

        # Cursor
        screen_x = self.buffer2x(self.pos[0], self.pos[1])
        try:
            self.stdscr.move(self.pos[0], min(screen_x, self.maxx-1))
        except curses.error:
            pass
        self.stdscr.refresh()

def main():
    filename = sys.argv[1] if len(sys.argv) > 1 else None
    editor = Editor(filename)
    curses.wrapper(editor.main_loop)

if __name__ == "__main__":
    main()
