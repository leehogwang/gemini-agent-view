import assert from 'assert';
import { SessionManager } from '../dist/session/SessionManager.js';

console.log('Running SessionManager 1:1 Parity Tests...');

const manager = new SessionManager();

// Test 1: Initialization
const active = manager.getActiveSession();
assert(active !== null, 'Initial active session should exist');
assert(active.name.length > 0, 'Active session must have a valid title');
assert.strictEqual(manager.getViewMode(), 'CHAT');
console.log('✓ Test 1 Passed: Initial active session created cleanly.');

// Test 2: Entering Agent View safely backgrounds active session
const activeBefore = manager.getActiveSession();
manager.enterAgentView();
assert.strictEqual(manager.getViewMode(), 'AGENT_VIEW');
const origin = manager.getOriginSession();
assert(origin !== null, 'Origin session should be recorded');
assert.strictEqual(origin.id, activeBefore.id);
assert.strictEqual(origin.isBackgrounded, true, 'Active session must be backgrounded safely on Agent View entry');
console.log('✓ Test 2 Passed: Active session backgrounded safely without data loss.');

// Test 3: Returning via Esc restores origin session
const restored = manager.returnToOriginSession();
assert.strictEqual(manager.getViewMode(), 'CHAT');
assert(restored !== null, 'Restored session must exist');
assert.strictEqual(restored.id, activeBefore.id);
assert.strictEqual(restored.isBackgrounded, false);
console.log('✓ Test 3 Passed: Esc key restores origin session cleanly.');

// Test 4: Creating new session (Ctrl+N)
const initialCount = manager.getSessions().length;
const newSession = manager.createSession('New Subagent Task');
assert.strictEqual(manager.getSessions().length, initialCount + 1);
assert.strictEqual(newSession.name, 'New Subagent Task');
console.log('✓ Test 4 Passed: Ctrl+N creates new session.');

// Test 5: Attaching session (Enter)
manager.enterAgentView();
const attached = manager.attachSession(newSession.id);
assert.strictEqual(attached.id, newSession.id);
assert.strictEqual(manager.getActiveSession().id, newSession.id);
assert.strictEqual(manager.getViewMode(), 'CHAT');
console.log('✓ Test 5 Passed: Enter attaches selected session.');

// Test 6: Subagent Hierarchical Tree Navigation
const parentSession = manager.createSession('Parent Task Orchestrator');
const subagentSession = manager.createSession('Code Review Subagent', parentSession.id, 'Code Reviewer');
const hierarchical = manager.getHierarchicalSessions();
const parentItem = hierarchical.find(h => h.session.id === parentSession.id);
const subagentItem = hierarchical.find(h => h.session.id === subagentSession.id);
assert(parentItem !== undefined, 'Parent session must exist in hierarchy tree');
assert(subagentItem !== undefined, 'Subagent session must exist in hierarchy tree');
assert.strictEqual(subagentItem.depth, parentItem.depth + 1, 'Subagent depth must be 1 greater than parent');
console.log('✓ Test 6 Passed: Subagent hierarchical tree node mapping verified.');

// Test 7: Explicit termination (Ctrl+X / Ctrl+D)
const countBeforeKill = manager.getSessions().length;
const terminated = manager.terminateSession(newSession.id);
assert.strictEqual(terminated, true);
assert.strictEqual(manager.getSessions().length, countBeforeKill - 1);
console.log('✓ Test 7 Passed: Explicit Ctrl+X/Ctrl+D terminates session.');

manager.stopWatcher();

console.log('\n🎉 ALL SESSION MANAGER PARITY TESTS PASSED SUCCESSFULLY!');
