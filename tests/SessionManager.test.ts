import { SessionManager } from '../src/session/SessionManager.js';

describe('SessionManager Engine (Claude Code Agent View 1:1 Parity)', () => {
  let manager: SessionManager;

  beforeEach(() => {
    manager = new SessionManager();
  });

  afterEach(() => {
    manager.stopWatcher();
  });

  test('Initializes with a default main conversation session', () => {
    const active = manager.getActiveSession();
    expect(active).not.toBeNull();
    expect(manager.getViewMode()).toBe('CHAT');
  });

  test('Safe session backgrounding: enterAgentView() backgrounds current session without destroying it', () => {
    const activeBefore = manager.getActiveSession()!;
    manager.enterAgentView();

    expect(manager.getViewMode()).toBe('AGENT_VIEW');
    const origin = manager.getOriginSession();
    expect(origin).not.toBeNull();
    expect(origin?.id).toBe(activeBefore.id);
    expect(origin?.isBackgrounded).toBe(true);

    const sessions = manager.getSessions();
    expect(sessions.find((s) => s.id === activeBefore.id)).toBeDefined();
  });

  test('Return to origin session on Esc: returnToOriginSession() restores origin session state', () => {
    const activeBefore = manager.getActiveSession()!;
    manager.enterAgentView();
    expect(manager.getViewMode()).toBe('AGENT_VIEW');

    const restored = manager.returnToOriginSession();
    expect(manager.getViewMode()).toBe('CHAT');
    expect(restored).not.toBeNull();
    expect(restored?.id).toBe(activeBefore.id);
    expect(restored?.isBackgrounded).toBe(false);
  });

  test('Creating new session (Ctrl+N) adds session to list', () => {
    const initialCount = manager.getSessions().length;
    const newSession = manager.createSession('Feature Development Session');

    expect(manager.getSessions().length).toBe(initialCount + 1);
    expect(newSession.name).toBe('Feature Development Session');
  });

  test('Subagent tree structure: getHierarchicalSessions() returns parent-child relationships', () => {
    const parent = manager.createSession('Parent Orchestrator');
    const child = manager.createSession('Child Subagent', parent.id, 'Codebase Researcher');

    const tree = manager.getHierarchicalSessions();
    const parentItem = tree.find((t) => t.session.id === parent.id);
    const childItem = tree.find((t) => t.session.id === child.id);

    expect(parentItem).toBeDefined();
    expect(childItem).toBeDefined();
    expect(childItem?.depth).toBe(parentItem!.depth + 1);
  });

  test('Explicit termination (Ctrl+X / Ctrl+D) removes session permanently', () => {
    const newSession = manager.createSession('Temp Session');
    expect(manager.getSessions().find((s) => s.id === newSession.id)).toBeDefined();

    const result = manager.terminateSession(newSession.id);
    expect(result).toBe(true);
    expect(manager.getSessions().find((s) => s.id === newSession.id)).toBeUndefined();
  });
});
