#!/usr/bin/env node
import React, { useState, useEffect } from 'react';
import { render, Box, Text } from 'ink';
import { SessionManager } from './session/SessionManager.js';
import { AgentView } from './ui/AgentView.js';
import { InputPrompt } from './ui/InputPrompt.js';
import { ToolAccordion } from './ui/ToolAccordion.js';
import { PermissionBar } from './ui/PermissionBar.js';
import { ToolCallState, TranscriptMessage } from './session/types.js';

export const MainApp: React.FC<{ sessionManager: SessionManager }> = ({
  sessionManager,
}) => {
  const [viewMode, setViewMode] = useState(() => sessionManager.getViewMode());
  const [messages, setMessages] = useState<TranscriptMessage[]>([
    {
      id: 'init-msg',
      sender: 'system',
      text: 'Type your prompt below. Press ← (on empty line) or Ctrl+← or /agents for Agent View.',
      timestamp: Date.now(),
    },
  ]);
  const [activeToolCall, setActiveToolCall] = useState<ToolCallState | null>(null);
  const [pendingApproval, setPendingApproval] = useState<{
    toolName: string;
    description: string;
    details?: string;
  } | null>(null);

  const activeSession = sessionManager.getActiveSession();

  const handleOpenAgentView = () => {
    sessionManager.enterAgentView();
    setViewMode('AGENT_VIEW');
  };

  const handleAttachSession = (id: string) => {
    sessionManager.attachSession(id);
    setViewMode('CHAT');
  };

  const handleReturnToOrigin = () => {
    sessionManager.returnToOriginSession();
    setViewMode('CHAT');
  };

  const handleSendMessage = (text: string) => {
    const userMsg: TranscriptMessage = {
      id: `msg-${Date.now()}`,
      sender: 'user',
      text: text,
      timestamp: Date.now(),
    };

    setMessages((prev) => [...prev, userMsg]);

    if (text.startsWith('/run') || text.includes('bash') || text.includes('edit')) {
      const toolName = text.includes('edit') ? 'write_file' : 'run_command';
      
      setPendingApproval({
        toolName,
        description: `Execute tool action requested: ${text}`,
        details: text.includes('edit')
          ? '+ const newFeature = true;\n- const oldFeature = false;'
          : `CommandLine: ${text}`,
      });
    } else {
      setTimeout(() => {
        setMessages((prev) => [
          ...prev,
          {
            id: `resp-${Date.now()}`,
            sender: 'assistant',
            text: `Response generated in session [${activeSession?.name || 'Main Conversation'}]`,
            timestamp: Date.now(),
          },
        ]);
      }, 500);
    }
  };

  const handlePermissionRespond = (action: 'allow' | 'always' | 'deny' | 'edit') => {
    if (!pendingApproval) return;
    const { toolName } = pendingApproval;
    setPendingApproval(null);

    if (action === 'allow' || action === 'always') {
      const toolState: ToolCallState = {
        id: `tool-${Date.now()}`,
        name: toolName,
        status: 'running',
        startTime: Date.now(),
        args: { action },
      };
      setActiveToolCall(toolState);

      setTimeout(() => {
        setActiveToolCall((prev) =>
          prev ? { ...prev, status: 'completed', endTime: Date.now(), output: 'Success' } : null
        );
        setMessages((prev) => [
          ...prev,
          {
            id: `resp-${Date.now()}`,
            sender: 'assistant',
            text: `Tool [${toolName}] executed successfully.`,
            timestamp: Date.now(),
          },
        ]);
      }, 1200);
    } else {
      setMessages((prev) => [
        ...prev,
        {
          id: `resp-${Date.now()}`,
          sender: 'system',
          text: `Action [${toolName}] was ${action === 'deny' ? 'denied' : 'edited'}.`,
          timestamp: Date.now(),
        },
      ]);
    }
  };

  if (viewMode === 'AGENT_VIEW') {
    return (
      <AgentView
        sessionManager={sessionManager}
        onAttachSession={handleAttachSession}
        onReturnToOrigin={handleReturnToOrigin}
      />
    );
  }

  return (
    <Box flexDirection="column" padding={1}>
      {/* Authentic agy Header */}
      <Box marginBottom={1} justifyContent="space-between" borderStyle="single" borderColor="magenta">
        <Text bold color="magenta">
          agy (gemini-3.5-flash) | Session: {activeSession?.name || 'Main Conversation'}
        </Text>
        <Text color="gray">
          Workspace: {process.cwd()}
        </Text>
      </Box>

      {/* Messages Stream */}
      <Box flexDirection="column" marginY={1}>
        {messages.slice(-8).map((msg) => (
          <Box key={msg.id} marginY={0}>
            {msg.sender === 'user' && (
              <Text color="green" bold>
                ❯ {msg.text}
              </Text>
            )}
            {msg.sender === 'assistant' && (
              <Text color="white">
                {msg.text}
              </Text>
            )}
            {msg.sender === 'system' && (
              <Text color="gray" italic>
                {msg.text}
              </Text>
            )}
          </Box>
        ))}
      </Box>

      {/* Active Tool Accordion */}
      {activeToolCall && (
        <ToolAccordion toolCall={activeToolCall} isExpandedByDefault={true} />
      )}

      {/* Interactive Permission Bar */}
      {pendingApproval && (
        <PermissionBar
          toolName={pendingApproval.toolName}
          description={pendingApproval.description}
          details={pendingApproval.details}
          onRespond={handlePermissionRespond}
        />
      )}

      {/* Sleek Input Prompt with ← and Ctrl+← Handler */}
      <InputPrompt
        activeSessionName={activeSession?.name || 'Main Conversation'}
        onOpenAgentView={handleOpenAgentView}
        onSendMessage={handleSendMessage}
      />
    </Box>
  );
};

const manager = new SessionManager();
render(<MainApp sessionManager={manager} />);
