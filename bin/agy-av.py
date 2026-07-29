#!/usr/bin/env python3
import sys
import os
import glob
import json
import curses
import pty
import select
import termios
import tty
import signal
import fcntl
import struct
import time
import ctypes
import unicodedata
import shutil

AGY_BINARY = shutil.which("agy") or os.path.expanduser("~/.local/bin/agy")
CONV_DIR = os.path.expanduser("~/.gemini/antigravity-cli/conversations")
HISTORY_PATH = os.path.expanduser("~/.gemini/antigravity-cli/history.jsonl")
WORKSPACE_OVERRIDE_PATH = os.path.expanduser("~/.gemini/antigravity-cli/agy_av_workspace_overrides.json")
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_workspace_overrides():
    try:
        with open(WORKSPACE_OVERRIDE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_workspace_override(cid, workspace):
    data = load_workspace_overrides()
    data[cid] = workspace
    try:
        with open(WORKSPACE_OVERRIDE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass

def remove_workspace_override(cid):
    data = load_workspace_overrides()
    if cid in data:
        del data[cid]
        try:
            with open(WORKSPACE_OVERRIDE_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass

def find_and_kill_agy_pids_for_cid(cid):
    # agy doesn't honor a client-supplied --conversation id for brand new
    # sessions, and other agy-av terminal processes don't share our
    # in-memory ACTIVE_SESSIONS, so we scan /proc for the real process.
    killed = []
    try:
        pid_dirs = os.listdir("/proc")
    except OSError:
        return killed
    for pid_str in pid_dirs:
        if not pid_str.isdigit():
            continue
        try:
            with open(f"/proc/{pid_str}/cmdline", "rb") as f:
                raw = f.read()
            cmdline = " ".join(p.decode("utf-8", "ignore") for p in raw.split(b"\x00") if p)
            if "--conversation" in cmdline and cid in cmdline:
                os.kill(int(pid_str), signal.SIGTERM)
                killed.append(int(pid_str))
        except (OSError, ProcessLookupError, PermissionError, ValueError):
            pass
    return killed

def wait_for_pids_exit(pids, timeout=2.0):
    deadline = time.time() + timeout
    for p in pids:
        while time.time() < deadline and is_pid_alive(p):
            time.sleep(0.1)

def set_process_name(title="agy-av"):
    try:
        libc = ctypes.CDLL("libc.so.6")
        libc.prctl(15, title.encode("utf-8"), 0, 0, 0)
    except Exception:
        pass
    try:
        sys.stdout.write(f"\033]0;{title}\007")
        sys.stdout.flush()
    except Exception:
        pass

def get_display_width(text):
    w = 0
    for ch in text:
        if unicodedata.east_asian_width(ch) in ('F', 'W'):
            w += 2
        else:
            w += 1
    return w

def truncate_display_width(text, max_w):
    res = ""
    cur_w = 0
    for ch in text:
        cw = 2 if unicodedata.east_asian_width(ch) in ('F', 'W') else 1
        if cur_w + cw > max_w:
            break
        res += ch
        cur_w += cw
    return res, cur_w

def pad_display_width(text, target_w):
    t, w = truncate_display_width(text, target_w)
    return t + " " * max(0, target_w - w)

def format_time_ago(mtime):
    diff = time.time() - mtime
    if diff < 0:
        diff = 0
    if diff < 60:
        return f"{int(diff)}s"
    elif diff < 3600:
        return f"{int(diff // 60)}m"
    elif diff < 86400:
        return f"{int(diff // 3600)}h"
    else:
        return f"{int(diff // 86400)}d"

def shorten_workspace(ws_path):
    if not ws_path:
        return "~/gemini-like-claude"
    home = os.path.expanduser("~")
    if ws_path.startswith(home):
        return "~" + ws_path[len(home):]
    return ws_path

def resolve_new_session_workspace(tree_items, current_tree_idx, fallback):
    if not tree_items or current_tree_idx >= len(tree_items):
        return fallback
    return tree_items[current_tree_idx].get("workspace", fallback)

def should_suppress_on_agent_view_entry(sess, now):
    # Entering Agent View can kick a spurious redraw burst out of the origin
    # session's pty, which would otherwise be misread as real generation. Only
    # suppress when nothing was actually in flight -- otherwise a task that's
    # genuinely still generating gets masked and shows as "Done" too early.
    was_active = sess.get("is_generating") and (now - sess.get("last_activity", 0) < 6.0)
    return not was_active

# Global active background sessions registry: map conversation_id -> { "pid": pid, "master_fd": master_fd, "last_activity": float, "is_generating": bool, "suppress_until": float }
ACTIVE_SESSIONS = {}

def is_pid_alive(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False

def force_redraw(pid, master_fd, cid=None):
    if cid and cid in ACTIVE_SESSIONS:
        ACTIVE_SESSIONS[cid]["suppress_until"] = time.time() + 2.0

    try:
        ws = fcntl.ioctl(sys.stdin.fileno(), termios.TIOCGWINSZ, b"\x00" * 8)
        rows, cols = struct.unpack("HHHH", ws)[:2]

        ws_smaller = struct.pack("HHHH", max(1, rows - 1), cols, 0, 0)
        ws_real    = struct.pack("HHHH", rows, cols, 0, 0)

        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, ws_smaller)
        os.kill(pid, signal.SIGWINCH)
        time.sleep(0.05)
        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, ws_real)
        os.kill(pid, signal.SIGWINCH)
    except Exception:
        try:
            os.kill(pid, signal.SIGWINCH)
        except Exception:
            pass

def register_pty_activity(cid, sess):
    now = time.time()
    if now < sess.get("suppress_until", 0):
        return
    sess["is_generating"] = True
    sess["last_activity"] = now

def drain_background_ptys(exclude_fd=None):
    for cid, sess in list(ACTIVE_SESSIONS.items()):
        mfd = sess.get("master_fd")
        if mfd is not None and mfd != exclude_fd:
            try:
                r, _, _ = select.select([mfd], [], [], 0)
                if mfd in r:
                    data = os.read(mfd, 4096)
                    if data:
                        register_pty_activity(cid, sess)
            except (OSError, ValueError):
                pass

def get_session_status(cid, mtime, db_path):
    now = time.time()
    if cid in ACTIVE_SESSIONS:
        sess = ACTIVE_SESSIONS[cid]
        if sess.get("is_generating"):
            last_act = sess.get("last_activity", 0)
            if now - last_act < 6.0:
                return "running"
            else:
                sess["is_generating"] = False
                return "completed"
        else:
            return "completed"

    diff = now - mtime
    if diff < 3600:
        return "completed"
    else:
        return "idle"

def get_real_sessions():
    db_files = glob.glob(os.path.join(CONV_DIR, "*.db"))
    overrides = load_workspace_overrides()
    sessions_by_id = {}
    for f in db_files:
        cid = os.path.basename(f).replace(".db", "")
        mtime = os.path.getmtime(f)
        sessions_by_id[cid] = {
            "id": cid,
            "mtime": mtime,
            "path": f,
            "status": get_session_status(cid, mtime, f),
            "workspace": overrides.get(cid, REPO_ROOT),
            "title": f"agy Session {cid[:8]}",
            "summary": "",
            "time_ago": format_time_ago(mtime),
        }

    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8", errors="ignore") as hf:
                for line in hf:
                    try:
                        data = json.loads(line)
                        cid = data.get("conversationId")
                        text = data.get("display")
                        ws = data.get("workspace")
                        
                        if cid and cid in sessions_by_id:
                            sess = sessions_by_id[cid]
                            if ws:
                                sess["workspace"] = ws
                                
                            if text:
                                if text.startswith("/rename ") or text.startswith("/title "):
                                    parts = text.split(" ", 1)
                                    if len(parts) > 1 and parts[1].strip():
                                        sess["title"] = parts[1].strip()[:45]
                                elif not text.startswith("/"):
                                    if sess["title"].startswith("agy Session "):
                                        sess["title"] = text[:45]
                                    sess["summary"] = text.replace("\n", " ").strip()[:80]
                    except:
                        pass
        except:
            pass

    sessions_list = list(sessions_by_id.values())
    sessions_list.sort(key=lambda s: s["mtime"], reverse=True)
    return sessions_list

def get_grouped_workspace_tree(origin_cid=None):
    sessions = get_real_sessions()
    workspaces_map = {}
    for s in sessions:
        ws = s["workspace"]
        if ws not in workspaces_map:
            workspaces_map[ws] = []
        workspaces_map[ws].append(s)

    tree_items = []
    selectable_indices = []

    for ws, sess_list in workspaces_map.items():
        sess_list.sort(key=lambda x: x["mtime"], reverse=True)
        
        # Folder Header
        tree_items.append({
            "type": "header",
            "workspace": ws,
            "short_ws": shorten_workspace(ws)
        })
        
        for s in sess_list:
            item_idx = len(tree_items)
            selectable_indices.append(item_idx)
            tree_items.append({
                "type": "session",
                "session": s,
                "workspace": ws
            })

    return tree_items, selectable_indices

def run_agent_view_tui(stdscr, origin_cid=None):
    set_process_name("agy-av")
    curses.curs_set(0)
    curses.use_default_colors()
    
    if curses.has_colors():
        curses.init_pair(1, curses.COLOR_CYAN, -1)      # Gemini Cyan / Primary Accent
        curses.init_pair(2, curses.COLOR_RED, -1)       # Red
        curses.init_pair(3, curses.COLOR_YELLOW, -1)    # Yellow
        curses.init_pair(4, curses.COLOR_GREEN, -1)     # Green
        curses.init_pair(5, curses.COLOR_BLUE, -1)      # Blue Workspace Folder Header
        curses.init_pair(6, curses.COLOR_BLUE, -1)      # Gemini Blue
        curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_BLUE) # Selection Row Highlight

    spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    frame_idx = 0

    # Initial selection mapping
    tree_items, selectable_indices = get_grouped_workspace_tree(origin_cid=origin_cid)
    
    selected_sel_idx = 0
    if origin_cid:
        for idx, sel_i in enumerate(selectable_indices):
            if tree_items[sel_i].get("session", {}).get("id") == origin_cid:
                selected_sel_idx = idx
                break

    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        drain_background_ptys()

        tree_items, selectable_indices = get_grouped_workspace_tree(origin_cid=origin_cid)
        if not selectable_indices:
            selectable_indices = [0]
            selected_sel_idx = 0
        else:
            selected_sel_idx = max(0, min(selected_sel_idx, len(selectable_indices) - 1))

        current_tree_idx = selectable_indices[selected_sel_idx]

        frame_idx = (frame_idx + 1) % len(spinner_frames)
        spinner = spinner_frames[frame_idx]

        # Calculate counts
        all_sessions = [item["session"] for item in tree_items if item["type"] == "session"]
        awaiting_count = sum(1 for s in all_sessions if s["status"] == "needs_input")
        working_count = sum(1 for s in all_sessions if s["status"] == "running")
        completed_count = sum(1 for s in all_sessions if s["status"] in ("completed", "idle"))

        # 1. Clean, Minimalistic Header (No ASCII Mark / Logo)
        try:
            head_title = "Antigravity CLI v2.1.218 · Gemini 3.6 Flash · ~/gemini-like-claude"
            stats_text = f"{awaiting_count} awaiting input · {working_count} working · {completed_count} completed"
            sub_line = "Your conversation moved to the background — enter opens it · esc returns to it"

            stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
            stdscr.addnstr(0, 1, head_title, max(1, width - 2))
            stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)

            stdscr.addnstr(1, 1, stats_text, max(1, width - 2), curses.A_DIM)
            stdscr.addnstr(3, 1, sub_line, max(1, width - 2), curses.A_DIM)
        except Exception:
            pass

        # 2. Render Workspace Tree Grouping List (starting at line 5)
        max_rows = height - 6
        max_line_width = max(10, width - 2)

        for line_offset, item in enumerate(tree_items[:max_rows]):
            row_y = 5 + line_offset
            item_tree_idx = line_offset

            if item["type"] == "header":
                # Render Folder Header in Sleek Bold Blue (e.g. ~/food/Food-Nutrition-Estimation)
                ws_name = item["short_ws"]
                try:
                    stdscr.attron(curses.color_pair(5) | curses.A_BOLD)
                    stdscr.addnstr(row_y, 1, ws_name, max_line_width)
                    stdscr.attroff(curses.color_pair(5) | curses.A_BOLD)
                except Exception:
                    pass
            else:
                # Render Session Item inside Folder
                s = item["session"]
                is_selected = (item_tree_idx == current_tree_idx)
                is_origin = (origin_cid and s["id"] == origin_cid)

                st = s["status"]
                if is_selected:
                    bullet_sym = "❯ "
                elif st == "running":
                    bullet_sym = f"{spinner} "
                elif st == "needs_input":
                    bullet_sym = "✻ "
                else:
                    bullet_sym = " ∙ "

                if st == "running":
                    badge_text = "Running"
                    badge_attr = curses.color_pair(1) | curses.A_BOLD
                elif st == "needs_input":
                    badge_text = "Needs input"
                    badge_attr = curses.color_pair(3) | curses.A_BOLD
                elif st == "completed":
                    badge_text = "Done"
                    badge_attr = curses.color_pair(4)
                else:
                    badge_text = "Idle"
                    badge_attr = curses.A_DIM

                # Format title (display width max 28)
                raw_title = s["title"]
                w_title = get_display_width(raw_title)
                if w_title > 28:
                    clean_t, _ = truncate_display_width(raw_title, 26)
                    clean_t += ".."
                else:
                    clean_t = raw_title
                title_col = pad_display_width(clean_t, 28)

                # Format summary snippet & time ago
                summary_snippet = s.get("summary", "")
                if summary_snippet:
                    summary_part = f" · {summary_snippet}"
                else:
                    summary_part = ""

                time_str = s.get("time_ago", "1m")
                origin_tag = " (current)" if is_origin else ""

                try:
                    if is_selected:
                        # Full row highlight in blue
                        full_row = f" {bullet_sym}{title_col}  {badge_text}{summary_part}{origin_tag}"
                        w_full = get_display_width(full_row)
                        gap_len = max(1, width - 2 - w_full - len(time_str))
                        full_line_str = f"{full_row}{' ' * gap_len}{time_str}"
                        
                        safe_line = truncate_display_width(full_line_str, max_line_width)[0]
                        safe_line = pad_display_width(safe_line, max_line_width)

                        stdscr.attron(curses.color_pair(7) | curses.A_BOLD)
                        stdscr.addnstr(row_y, 1, safe_line, max_line_width)
                        stdscr.attroff(curses.color_pair(7) | curses.A_BOLD)
                    else:
                        # Unselected item: precise parts
                        # Bullet
                        if st == "needs_input":
                            stdscr.attron(curses.color_pair(3) | curses.A_BOLD)
                        elif st == "running":
                            stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
                        else:
                            stdscr.attron(curses.color_pair(4))

                        stdscr.addnstr(row_y, 1, f" {bullet_sym}", 3)
                        stdscr.attroff(curses.A_BOLD | curses.color_pair(1) | curses.color_pair(2) | curses.color_pair(3) | curses.color_pair(4))

                        # Title
                        stdscr.addnstr(row_y, 4, title_col, 28)

                        # Badge
                        stdscr.attron(badge_attr)
                        stdscr.addnstr(row_y, 34, badge_text, len(badge_text))
                        stdscr.attroff(badge_attr)

                        # Summary snippet
                        if summary_part and width > 60:
                            rem_w = width - 48 - len(time_str)
                            if rem_w > 5:
                                clean_sum = truncate_display_width(summary_part, rem_w)[0]
                                stdscr.addnstr(row_y, 34 + len(badge_text), clean_sum, rem_w, curses.A_DIM)

                        # Origin tag
                        if is_origin:
                            stdscr.attron(curses.color_pair(1))
                            stdscr.addnstr(row_y, width - len(time_str) - 12, origin_tag, 10)
                            stdscr.attroff(curses.color_pair(1))

                        # Time ago (right aligned)
                        stdscr.addnstr(row_y, width - len(time_str) - 1, time_str, len(time_str), curses.A_DIM)
                except Exception:
                    pass

        stdscr.refresh()

        stdscr.timeout(200)
        key = stdscr.getch()

        if key in (curses.KEY_UP, ord('k')):
            selected_sel_idx = max(0, selected_sel_idx - 1)
        elif key in (curses.KEY_DOWN, ord('j')):
            selected_sel_idx = min(len(selectable_indices) - 1, selected_sel_idx + 1)
        elif key in (10, 13):  # Enter key
            sel_tree_idx = selectable_indices[selected_sel_idx]
            target_item = tree_items[sel_tree_idx]
            if target_item.get("type") == "session":
                return {"action": "attach", "session_id": target_item["session"]["id"]}
        elif key in (14, ord('n')):  # Ctrl+N / 'n'
            target_ws = resolve_new_session_workspace(tree_items, current_tree_idx, os.getcwd())
            return {"action": "new", "workspace": target_ws}
        elif key in (24, 4, ord('x'), ord('d')):  # Ctrl+X / Ctrl+D / 'x' / 'd'
            sel_tree_idx = selectable_indices[selected_sel_idx]
            target_item = tree_items[sel_tree_idx]
            if target_item.get("type") == "session":
                target_cid = target_item["session"]["id"]
                killed_pids = []
                if target_cid in ACTIVE_SESSIONS:
                    try:
                        os.kill(ACTIVE_SESSIONS[target_cid]["pid"], signal.SIGTERM)
                        killed_pids.append(ACTIVE_SESSIONS[target_cid]["pid"])
                    except:
                        pass
                    del ACTIVE_SESSIONS[target_cid]
                # Also reach processes owned by *other* agy-av terminals,
                # since ACTIVE_SESSIONS is per-process and won't know about them.
                killed_pids.extend(find_and_kill_agy_pids_for_cid(target_cid))
                wait_for_pids_exit(killed_pids)
                try:
                    if os.path.exists(target_item["session"]["path"]):
                        os.remove(target_item["session"]["path"])
                except:
                    pass
                remove_workspace_override(target_cid)
                selected_sel_idx = max(0, selected_sel_idx - 1)
        elif key in (27, ord('q')):  # Esc / 'q'
            return {"action": "return", "origin_cid": origin_cid}

def sync_winsize(master_fd):
    try:
        ws = fcntl.ioctl(sys.stdin.fileno(), termios.TIOCGWINSZ, b"\x00" * 8)
        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, ws)
    except:
        pass

def run_pty_proxy(cmd_args, current_cid=None, target_workspace=None):
    set_process_name("agy-av")
    if "--dangerously-skip-permissions" not in cmd_args:
        cmd_args = ["--dangerously-skip-permissions"] + cmd_args

    is_new_process = False
    pending_new_cid = False
    known_db_before = set()
    pending_deadline = 0
    if current_cid and current_cid in ACTIVE_SESSIONS:
        sess = ACTIVE_SESSIONS[current_cid]
        pid = sess["pid"]
        master_fd = sess["master_fd"]
        force_redraw(pid, master_fd, cid=current_cid)
    else:
        is_new_process = True
        cmd = [AGY_BINARY] + cmd_args
        # agy assigns its own conversation id for brand new sessions (it
        # ignores a client-supplied --conversation id it hasn't seen before),
        # so we don't know the real id up front. Snapshot existing .db files
        # and diff against them once the child creates its own, below.
        pending_new_cid = current_cid is None
        known_db_before = set(glob.glob(os.path.join(CONV_DIR, "*.db"))) if pending_new_cid else set()
        pending_deadline = time.time() + 15.0

        pid, master_fd = pty.fork()
        if pid == 0:
            if target_workspace:
                try:
                    os.chdir(target_workspace)
                except OSError:
                    pass
            os.execv(AGY_BINARY, cmd)

        if current_cid:
            ACTIVE_SESSIONS[current_cid] = {
                "pid": pid,
                "master_fd": master_fd,
                "last_activity": time.time(),
                "is_generating": False,
                "suppress_until": time.time() + 2.0,
            }

    sync_winsize(master_fd)
    signal.signal(signal.SIGWINCH, lambda sig, frame: sync_winsize(master_fd))

    shadow_buffer = ""
    last_left_arrow_time = 0.0
    is_in_startup_phase = is_new_process
    startup_buffer = ""
    startup_start_time = time.time()
    old_tty = termios.tcgetattr(sys.stdin.fileno())

    try:
        tty.setraw(sys.stdin.fileno())
        while True:
            drain_background_ptys(exclude_fd=master_fd)

            if pending_new_cid:
                if time.time() >= pending_deadline:
                    pending_new_cid = False
                else:
                    new_dbs = set(glob.glob(os.path.join(CONV_DIR, "*.db"))) - known_db_before
                    if new_dbs:
                        current_cid = os.path.basename(sorted(new_dbs)[0])[:-3]
                        if target_workspace:
                            save_workspace_override(current_cid, target_workspace)
                        ACTIVE_SESSIONS[current_cid] = {
                            "pid": pid,
                            "master_fd": master_fd,
                            "last_activity": time.time(),
                            "is_generating": False,
                            "suppress_until": time.time() + 2.0,
                        }
                        pending_new_cid = False

            r, w, e = select.select([sys.stdin.fileno(), master_fd], [], [], 0.05)

            # Handle user input from stdin
            if sys.stdin.fileno() in r:
                try:
                    data = os.read(sys.stdin.fileno(), 1024)
                    if not data:
                        break

                    # Detect Left Arrow sequences
                    is_left_arrow = (b"\x1b[D" in data or b"\x1b[OD" in data)
                    is_ctrl_left = (b"\x1b[1;5D" in data or b"\x1b[1;3D" in data or b"\x1b[5D" in data or b"\x1b[1;2D" in data)
                    left_count = data.count(b"\x1b[D") + data.count(b"\x1b[OD")

                    trigger_agent_view = False
                    now = time.time()

                    # Clean input check: has_user_input is True ONLY if shadow_buffer contains non-whitespace user typed text
                    has_user_input = (len(shadow_buffer.strip()) > 0)

                    if not has_user_input:
                        if is_ctrl_left:
                            trigger_agent_view = True
                        elif is_left_arrow or left_count >= 1:
                            if left_count >= 2: # Double left arrow in single read!
                                trigger_agent_view = True
                                last_left_arrow_time = 0.0
                            elif now - last_left_arrow_time <= 0.6: # Double tap within 0.6s!
                                trigger_agent_view = True
                                last_left_arrow_time = 0.0
                            else:
                                last_left_arrow_time = now

                    if trigger_agent_view:
                        if current_cid and current_cid in ACTIVE_SESSIONS:
                            sess = ACTIVE_SESSIONS[current_cid]
                            if should_suppress_on_agent_view_entry(sess, time.time()):
                                sess["suppress_until"] = time.time() + 2.0

                        sys.stdout.write("\x1b[?1049h")
                        sys.stdout.flush()
                        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_tty)

                        res = curses.wrapper(lambda s: run_agent_view_tui(s, origin_cid=current_cid))

                        tty.setraw(sys.stdin.fileno())
                        sys.stdout.write("\x1b[?1049l")
                        sys.stdout.flush()

                        shadow_buffer = ""
                        last_left_arrow_time = 0.0

                        if res and res.get("action") == "attach":
                            target_cid = res["session_id"]
                            if target_cid == current_cid:
                                shadow_buffer = ""
                                force_redraw(pid, master_fd, cid=current_cid)
                                continue
                            else:
                                if current_cid and pid:
                                    prev_sess = ACTIVE_SESSIONS.get(current_cid, {})
                                    ACTIVE_SESSIONS[current_cid] = {
                                        "pid": pid,
                                        "master_fd": master_fd,
                                        "last_activity": prev_sess.get("last_activity", time.time()),
                                        "is_generating": prev_sess.get("is_generating", False),
                                        "suppress_until": time.time() + 2.0,
                                    }
                                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_tty)
                                return run_pty_proxy(["--conversation", target_cid], current_cid=target_cid)

                        elif res and res.get("action") == "new":
                            if current_cid and pid:
                                prev_sess = ACTIVE_SESSIONS.get(current_cid, {})
                                ACTIVE_SESSIONS[current_cid] = {
                                    "pid": pid,
                                    "master_fd": master_fd,
                                    "last_activity": prev_sess.get("last_activity", time.time()),
                                    "is_generating": prev_sess.get("is_generating", False),
                                    "suppress_until": time.time() + 2.0,
                                }
                            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_tty)
                            return run_pty_proxy([], target_workspace=res.get("workspace"))

                        else:
                            shadow_buffer = ""
                            force_redraw(pid, master_fd, cid=current_cid)
                            continue
                    else:
                        # Clear buffer on Enter (\r, \n), Ctrl+C (\x03), Ctrl+U (\x15), Ctrl+L (\x0c)
                        for b in data:
                            if b in (13, 10, 3, 21, 12):
                                if current_cid and current_cid in ACTIVE_SESSIONS and len(shadow_buffer.strip()) > 0 and b in (13, 10):
                                    ACTIVE_SESSIONS[current_cid]["is_generating"] = True
                                    ACTIVE_SESSIONS[current_cid]["last_activity"] = time.time()
                                shadow_buffer = ""
                            elif b in (127, 8):
                                shadow_buffer = shadow_buffer[:-1]
                            elif 32 <= b <= 126 and not data.startswith(b"\x1b"):
                                shadow_buffer += chr(b)

                        os.write(master_fd, data)
                except OSError:
                    break

            if master_fd in r:
                try:
                    output = os.read(master_fd, 4096)
                    if not output:
                        break
                    if current_cid and current_cid in ACTIVE_SESSIONS:
                        register_pty_activity(current_cid, ACTIVE_SESSIONS[current_cid])

                    if is_in_startup_phase:
                        decoded = output.decode("utf-8", errors="ignore")
                        startup_buffer += decoded
                        
                        if "Signing in..." in startup_buffer or "Welcome to the Antigravity CLI" in startup_buffer or "not signed in" in startup_buffer:
                            if "❯" in startup_buffer or time.time() - startup_start_time > 4.0:
                                is_in_startup_phase = False
                                prompt_idx = startup_buffer.find("❯")
                                if prompt_idx != -1:
                                    sys.stdout.write("\x1b[2J\x1b[H")
                                    sys.stdout.write(startup_buffer[prompt_idx:])
                                    sys.stdout.flush()
                                else:
                                    sys.stdout.write("\x1b[2J\x1b[H")
                                    sys.stdout.flush()
                            continue
                        else:
                            is_in_startup_phase = False

                    os.write(sys.stdout.fileno(), output)
                    sys.stdout.flush()
                except OSError:
                    break

            res_pid, status = os.waitpid(pid, os.WNOHANG)
            if res_pid == pid:
                if current_cid and current_cid in ACTIVE_SESSIONS:
                    del ACTIVE_SESSIONS[current_cid]
                break
    finally:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_tty)

def main():
    set_process_name("agy-av")
    args = sys.argv[1:]
    if len(args) > 0 and args[0] in ("--agent-view", "-a", "agents", "/agents"):
        res = curses.wrapper(lambda s: run_agent_view_tui(s))
        if res and res.get("action") == "attach":
            run_pty_proxy(["--conversation", res["session_id"]], current_cid=res["session_id"])
        elif res and res.get("action") == "new":
            run_pty_proxy([], target_workspace=res.get("workspace"))
        return

    run_pty_proxy(args)

if __name__ == "__main__":
    main()
