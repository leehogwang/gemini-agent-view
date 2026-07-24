export type AgentStatus = 'running' | 'needs_input' | 'idle' | 'completed' | 'error';

export interface ToolCallState {
  id: string;
  name: string;
  args?: Record<string, any>;
  status: 'running' | 'completed' | 'error' | 'pending_approval';
  startTime: number;
  endTime?: number;
  output?: string;
  diffSnippet?: string;
}

export interface TranscriptMessage {
  id: string;
  sender: 'user' | 'assistant' | 'system' | 'tool';
  text: string;
  timestamp: number;
  toolCall?: ToolCallState;
}

export interface AgentSession {
  id: string;
  name: string;
  createdAt: number;
  lastActiveAt: number;
  status: AgentStatus;
  unreadCount?: number;
  lastMessageSummary?: string;
  isBackgrounded: boolean;
  worktreePath?: string;
  parentId?: string;
  role?: string;
  currentTask?: string;
  messages?: TranscriptMessage[];
  pendingApproval?: {
    toolName: string;
    description: string;
    details?: string;
  };
}

export type ViewMode = 'CHAT' | 'AGENT_VIEW';

export interface KeyPressInput {
  leftArrow?: boolean;
  upArrow?: boolean;
  downArrow?: boolean;
  return?: boolean;
  escape?: boolean;
  ctrl?: boolean;
  meta?: boolean;
  shift?: boolean;
}
