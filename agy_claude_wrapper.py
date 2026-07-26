#!/usr/bin/env python3
import sys
import os
import glob
import json
import curses
import subprocess
import signal
import time

AGY_BINARY = "/home/202421012/.local/bin/agy"
CONV_DIR = "/home/202421012/.gemini/antigravity-cli/conversations"
HISTORY_PATH = "/home/202421012/.gemini/antigravity-cli/history.jsonl"

def get_real_sessions():
    db_files = glob.glob(os.path.join(CONV_DIR, "*.db"))
    sessions = []
    for f in db_files:
        cid = os.path.basename(f).replace(".db", "")
        mtime = os.path.getmtime(f)
        sessions.append({"id": cid, "mtime": mtime, "path": f})

    sessions.sort(key=lambda s: s["mtime"], reverse=True)

    titles = {}
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8", errors="ignore") as hf:
                for line in hf:
                    try:
                        data = json.loads(line)
                        cid = data.get("conversationId")
                        text = data.get("display")
                        if cid and text and not text.startswith("/"):
                            titles[cid] = text[:50]
                    except:
                        pass
        except:
            pass

    for s in sessions:
        cid = s["id"]
        cid_short = cid[:8]
        s["title"] = titles.get(cid, f"agy Session {cid_short}")

    return sessions

def run_agent_view(stdscr, origin_cid=None):
    curses.curs_set(0)
    curses.use_default_colors()
    
    # Initialize color pairs
    if curses.has_colors():
        curses.init_pair(1, curses.COLOR_MAGENTA, -1)
        curses.init_pair(2, curses.COLOR_CYAN, -1)
        curses.init_pair(3, curses.COLOR_GREEN, -1)
        curses.init_pair(4, curses.COLOR_YELLOW, -1)
        curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLUE)

    selected_idx = 0

    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        sessions = get_real_sessions()

        # Render Header
        header_str = "🤖 agy — Agent View (Session Manager)"
        sub_header = f"Total Real agy Sessions: {len(sessions)} | 1:1 Claude Code Parity"
        
        try:
            stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
            stdscr.addstr(1, 2, header_str[:width-4])
            stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)

            stdscr.addstr(2, 2, sub_header[:width-4], curses.A_DIM)
            stdscr.hline(3, 2, curses.ACS_HLINE, width - 4)
        except:
            pass

        # Render Session List
        max_rows = height - 8
        for idx, s in enumerate(sessions[:max_rows]):
            row_y = 4 + idx
            is_selected = (idx == selected_idx)
            is_origin = (origin_cid and s["id"] == origin_cid)

            marker = "❯ " if is_selected else "  "
            title_text = s["title"]
            cid_text = f"[{s['id'][:8]}]"
            origin_text = " (current / backgrounded)" if is_origin else ""

            line_str = f"{marker}{cid_text} {title_text}{origin_text}"
            line_str = line_str[:width - 4]

            try:
                if is_selected:
                    stdscr.attron(curses.color_pair(5) | curses.A_BOLD)
                    stdscr.addstr(row_y, 2, line_str.ljust(width - 4))
                    stdscr.attroff(curses.color_pair(5) | curses.A_BOLD)
                else:
                    if is_origin:
                        stdscr.attron(curses.color_pair(1))
                        stdscr.addstr(row_y, 2, line_str)
                        stdscr.attroff(curses.color_pair(1))
                    else:
                        stdscr.addstr(row_y, 2, line_str)
            except:
                pass

        # Render Footer Controls
        footer_y = height - 2
        footer_str = "[↑/↓] Select | [Enter] Attach | [Ctrl+N / n] New | [Ctrl+X / Ctrl+D] Kill | [Esc] Return"
        try:
            stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
            stdscr.addstr(footer_y, 2, footer_str[:width-4])
            stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)
        except:
            pass

        stdscr.refresh()

        # Handle Keyboard Input
        key = stdscr.getch()

        if key in (curses.KEY_UP, ord('k')):
            selected_idx = max(0, selected_idx - 1)
        elif key in (curses.KEY_DOWN, ord('j')):
            selected_idx = min(len(sessions) - 1, selected_idx + 1)
        elif key in (10, 13):  # Enter key
            if sessions and selected_idx < len(sessions):
                return {"action": "attach", "session_id": sessions[selected_idx]["id"]}
        elif key in (14, ord('n')):  # Ctrl+N (ASCII 14) or 'n'
            return {"action": "new"}
        elif key in (24, 4, ord('x'), ord('d')):  # Ctrl+X (24), Ctrl+D (4), 'x', 'd'
            if sessions and selected_idx < len(sessions):
                target = sessions[selected_idx]
                try:
                    if os.path.exists(target["path"]):
                        os.remove(target["path"])
                except:
                    pass
                selected_idx = max(0, selected_idx - 1)
        elif key in (27, ord('q')):  # Esc (27) or 'q'
            return {"action": "return", "session_id": origin_cid}

def main():
    origin_cid = None

    # Check if user invoked with direct arguments
    if len(sys.argv) > 1 and sys.argv[1] in ("--agent-view", "agents", "/agents"):
        res = curses.wrapper(lambda stdscr: run_agent_view(stdscr, origin_cid))
        if res and res.get("action") == "attach":
            cmd = [AGY_BINARY, "--conversation", res["session_id"]]
            os.execv(AGY_BINARY, cmd)
        elif res and res.get("action") == "new":
            os.execv(AGY_BINARY, [AGY_BINARY])
        else:
            return

    # Default launch: run real agy interactive session directly
    # If agy binary is invoked directly, user gets 100% original agy design and features!
    print("Launching original agy with Agent View support...")
    print("Tip: Run 'agy-av --agent-view' or press Ctrl+C then type 'agy-av --agent-view' to open Agent View.")
    time.sleep(0.5)

    cmd = [AGY_BINARY] + sys.argv[1:]
    os.execv(AGY_BINARY, cmd)

if __name__ == "__main__":
    main()
