import React, { useState, useEffect } from 'react';
import { Box, Text, useInput, Key } from 'ink';
import { SessionManager } from '../session/SessionManager.js';
import { SessionItem } from './SessionItem.js';

interface AgentViewProps {
  sessionManager: SessionManager;
  onAttachSession: (id: string) => void;
  onReturnToOrigin: () => void;
}

const SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];

export const AgentView: React.FC<AgentViewProps> = ({
  sessionManager,
  onAttachSession,
  onReturnToOrigin,
}) => {
  const originSession = sessionManager.getOriginSession();
  const activeSession = sessionManager.getActiveSession();
  const targetId = originSession?.id || activeSession?.id;

  const [hierarchicalSessions, setHierarchicalSessions] = useState(() =>
    sessionManager.getHierarchicalSessions()
  );

  const [selectedIndex, setSelectedIndex] = useState(() => {
    const sessions = sessionManager.getHierarchicalSessions();
    if (!targetId) return 0;
    const foundIdx = sessions.findIndex((item) => item.session.id === targetId);
    return foundIdx !== -1 ? foundIdx : 0;
  });

  const [frameIdx, setFrameIdx] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setHierarchicalSessions(sessionManager.getHierarchicalSessions());
      setFrameIdx((prev) => (prev + 1) % SPINNER_FRAMES.length);
    }, 200);
    return () => clearInterval(timer);
  }, [sessionManager]);

  useInput((input: string, key: Key) => {
    // Navigation: Up/Down Arrow or 'k'/'j'
    if (key.upArrow || input === 'k') {
      setSelectedIndex((prev) => Math.max(0, prev - 1));
    }
    if (key.downArrow || input === 'j') {
      setSelectedIndex((prev) =>
        Math.min(hierarchicalSessions.length - 1, prev + 1)
      );
    }

    // Attach selected session: Enter
    if (key.return && hierarchicalSessions[selectedIndex]) {
      onAttachSession(hierarchicalSessions[selectedIndex].session.id);
    }

    // Create New Session: Ctrl+N or 'n'
    if ((key.ctrl && input === 'n') || input === 'n') {
      const newSession = sessionManager.createSession();
      const updated = sessionManager.getHierarchicalSessions();
      setHierarchicalSessions(updated);
      const newIdx = updated.findIndex((item) => item.session.id === newSession.id);
      if (newIdx !== -1) setSelectedIndex(newIdx);
    }

    // Terminate Session: Ctrl+X / Ctrl+D or 'x' / 'd'
    if (
      (key.ctrl && input === 'x') ||
      (key.ctrl && input === 'd') ||
      input === 'x' ||
      input === 'd'
    ) {
      const targetItem = hierarchicalSessions[selectedIndex];
      if (targetItem) {
        sessionManager.terminateSession(targetItem.session.id);
        const updated = sessionManager.getHierarchicalSessions();
        setHierarchicalSessions(updated);
        setSelectedIndex((prev) =>
          Math.min(updated.length - 1, Math.max(0, prev))
        );
      }
    }

    // Exit Agent View / Return to origin backgrounded session: Esc
    if (key.escape) {
      onReturnToOrigin();
    }
  });

  const runningCount = hierarchicalSessions.filter(
    (item) => item.session.status === 'running'
  ).length;

  return (
    <Box flexDirection="column" padding={1} borderStyle="round" borderColor="cyan">
      {/* Authentic agy Header */}
      <Box marginBottom={1} flexDirection="column">
        <Box justifyContent="space-between">
          <Text bold color="cyan">
            agy agent view
          </Text>
          <Text color="cyan" bold>
            {SPINNER_FRAMES[frameIdx]} Active Tasks: {runningCount}
          </Text>
        </Box>
        <Text color="gray">
          Total sessions: {hierarchicalSessions.length} · Preserved background processes
        </Text>
      </Box>

      {/* Session List */}
      <Box flexDirection="column" marginY={1}>
        {hierarchicalSessions.map((item, index) => (
          <SessionItem
            key={item.session.id}
            session={item.session}
            depth={item.depth}
            isSelected={index === selectedIndex}
            isOrigin={item.session.id === originSession?.id}
          />
        ))}
      </Box>

      {/* Footer Hints */}
      <Box marginTop={1} borderStyle="single" borderTop borderBottom={false} borderLeft={false} borderRight={false} borderColor="cyan">
        <Text color="cyan" bold>
          [↑/↓] Select  [Enter] Attach  [n] New  [x] Kill  [Esc] Back
        </Text>
      </Box>
    </Box>
  );
};
