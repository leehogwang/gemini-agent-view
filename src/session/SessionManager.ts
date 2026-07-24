import fs from 'fs';
import path from 'path';
import { AgentSession, ViewMode, AgentStatus } from './types.js';

const CONV_DIR = '/home/202421012/.gemini/antigravity-cli/conversations';
const HISTORY_PATH = '/home/202421012/.gemini/antigravity-cli/history.jsonl';

export class SessionManager {
  private sessions: Map<string, AgentSession> = new Map();
  private activeSessionId: string | null = null;
  private originSessionId: string | null = null;
  private currentViewMode: ViewMode = 'CHAT';
  private fileWatcher: fs.FSWatcher | null = null;

  constructor() {
    this.syncRealSessions();
    if (this.sessions.size === 0) {
      const defaultSession = this.createSession('Main Conversation');
      this.activeSessionId = defaultSession.id;
    } else {
      const firstSession = this.getSessions()[0];
      this.activeSessionId = firstSession.id;
    }

    this.startWatcher();
  }

  private startWatcher(): void {
    if (fs.existsSync(CONV_DIR)) {
      try {
        this.fileWatcher = fs.watch(CONV_DIR, () => {
          this.syncRealSessions();
        });
      } catch {}
    }
  }

  public stopWatcher(): void {
    if (this.fileWatcher) {
      this.fileWatcher.close();
      this.fileWatcher = null;
    }
  }

  private computeStatus(cid: string, mtime: number, dbPath: string): AgentStatus {
    const existing = this.sessions.get(cid);
    if (existing && existing.status === 'running') {
      const activeDiff = (Date.now() - existing.lastActiveAt) / 1000;
      if (activeDiff < 4) {
        return 'running';
      }
    }

    const diff = (Date.now() - mtime) / 1000;
    if (diff < 3600) {
      return 'completed';
    }
    return 'idle';
  }

  /**
   * Sync real agy sessions from ~/.gemini/antigravity-cli/
   */
  public syncRealSessions(): void {
    if (!fs.existsSync(CONV_DIR)) return;

    const titles: Record<string, string> = {};
    const renamedTitles: Record<string, string> = {};

    if (fs.existsSync(HISTORY_PATH)) {
      try {
        const content = fs.readFileSync(HISTORY_PATH, 'utf-8');
        const lines = content.split('\n');
        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const data = JSON.parse(line);
            if (data.conversationId && data.display) {
              if (data.display.startsWith('/rename ') || data.display.startsWith('/title ')) {
                const name = data.display.split(' ').slice(1).join(' ').trim();
                if (name) renamedTitles[data.conversationId] = name.slice(0, 50);
              } else if (!data.display.startsWith('/')) {
                if (!titles[data.conversationId]) {
                  titles[data.conversationId] = data.display.slice(0, 50);
                }
              }
            }
          } catch {}
        }
      } catch {}
    }

    try {
      const files = fs.readdirSync(CONV_DIR);
      for (const file of files) {
        if (file.endsWith('.db')) {
          const cid = file.replace('.db', '');
          const filePath = path.join(CONV_DIR, file);
          const stat = fs.statSync(filePath);
          const title = renamedTitles[cid] || titles[cid] || `agy Session ${cid.slice(0, 8)}`;
          const status = this.computeStatus(cid, stat.mtimeMs, filePath);

          if (!this.sessions.has(cid)) {
            this.sessions.set(cid, {
              id: cid,
              name: title,
              createdAt: stat.birthtimeMs || stat.mtimeMs,
              lastActiveAt: stat.mtimeMs,
              status,
              isBackgrounded: false,
            });
          } else {
            const existing = this.sessions.get(cid)!;
            existing.lastActiveAt = stat.mtimeMs;
            existing.status = status;
            existing.name = title;
          }
        }
      }
    } catch {}
  }

  public createSession(name?: string, parentId?: string, role?: string): AgentSession {
    const id = `session-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`;
    const sessionName = name || `Agent Session ${this.sessions.size + 1}`;
    const session: AgentSession = {
      id,
      name: sessionName,
      createdAt: Date.now(),
      lastActiveAt: Date.now(),
      status: 'idle',
      isBackgrounded: false,
      parentId,
      role,
    };
    this.sessions.set(id, session);
    return session;
  }

  public getSessions(): AgentSession[] {
    this.syncRealSessions();
    return Array.from(this.sessions.values()).sort(
      (a, b) => b.lastActiveAt - a.lastActiveAt
    );
  }

  /**
   * Return hierarchical tree list of sessions (parent sessions with subagents nested)
   */
  public getHierarchicalSessions(): { session: AgentSession; depth: number }[] {
    const all = this.getSessions();
    const result: { session: AgentSession; depth: number }[] = [];
    const visited = new Set<string>();

    const addBranch = (parentId: string | undefined, depth: number) => {
      const children = all.filter((s) => s.parentId === parentId);
      for (const child of children) {
        if (!visited.has(child.id)) {
          visited.add(child.id);
          result.push({ session: child, depth });
          addBranch(child.id, depth + 1);
        }
      }
    };

    const roots = all.filter((s) => !s.parentId || !this.sessions.has(s.parentId));
    for (const root of roots) {
      if (!visited.has(root.id)) {
        visited.add(root.id);
        result.push({ session: root, depth: 0 });
        addBranch(root.id, 1);
      }
    }

    return result;
  }

  public getActiveSession(): AgentSession | null {
    if (!this.activeSessionId) return null;
    return this.sessions.get(this.activeSessionId) || null;
  }

  public getOriginSession(): AgentSession | null {
    if (!this.originSessionId) return null;
    return this.sessions.get(this.originSessionId) || null;
  }

  public getViewMode(): ViewMode {
    return this.currentViewMode;
  }

  public enterAgentView(): void {
    if (this.activeSessionId) {
      const active = this.sessions.get(this.activeSessionId);
      if (active) {
        active.isBackgrounded = true;
        this.originSessionId = active.id;
      }
    }
    this.currentViewMode = 'AGENT_VIEW';
  }

  public returnToOriginSession(): AgentSession | null {
    this.currentViewMode = 'CHAT';
    if (this.originSessionId && this.sessions.has(this.originSessionId)) {
      return this.attachSession(this.originSessionId);
    }
    if (this.activeSessionId && this.sessions.has(this.activeSessionId)) {
      return this.attachSession(this.activeSessionId);
    }
    return null;
  }

  public attachSession(id: string): AgentSession {
    const session = this.sessions.get(id);
    if (!session) {
      throw new Error(`Session with ID ${id} not found.`);
    }

    if (this.activeSessionId && this.activeSessionId !== id) {
      const prev = this.sessions.get(this.activeSessionId);
      if (prev) prev.isBackgrounded = true;
    }

    session.isBackgrounded = false;
    session.lastActiveAt = Date.now();
    this.activeSessionId = id;
    this.currentViewMode = 'CHAT';
    return session;
  }

  public terminateSession(id: string): boolean {
    if (!this.sessions.has(id)) return false;

    const dbPath = path.join(CONV_DIR, `${id}.db`);
    if (fs.existsSync(dbPath)) {
      try {
        fs.unlinkSync(dbPath);
      } catch {}
    }

    this.sessions.delete(id);

    if (this.originSessionId === id) {
      this.originSessionId = null;
    }

    if (this.activeSessionId === id) {
      const remaining = this.getSessions();
      if (remaining.length > 0) {
        this.attachSession(remaining[0].id);
      } else {
        const newSession = this.createSession('Main Conversation');
        this.attachSession(newSession.id);
      }
    }
    return true;
  }
}
