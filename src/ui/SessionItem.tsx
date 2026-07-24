import React from 'react';
import { Box, Text } from 'ink';
import { AgentSession } from '../session/types.js';

interface SessionItemProps {
  session: AgentSession;
  isSelected: boolean;
  isOrigin: boolean;
  depth?: number;
}

export const SessionItem: React.FC<SessionItemProps> = ({
  session,
  isSelected,
  isOrigin,
  depth = 0,
}) => {
  const renderStatusBadge = () => {
    switch (session.status) {
      case 'running':
        return <Text color="cyan" bold>⠋ Running</Text>;
      case 'needs_input':
        return <Text color="yellow" bold>? Needs Input</Text>;
      case 'completed':
        return <Text color="green">✓ Completed</Text>;
      case 'error':
        return <Text color="red" bold>✖ Error</Text>;
      default:
        return <Text color="gray">○ Idle</Text>;
    }
  };

  const indentStr = depth > 0 ? '  '.repeat(depth) + '└─ ' : '';
  const cidShort = session.id.slice(0, 8);
  const displayName = session.name || `agy Session ${cidShort}`;

  return (
    <Box paddingX={1} marginY={0}>
      {/* Pointer */}
      <Text bold={isSelected} color={isSelected ? 'cyan' : 'gray'}>
        {isSelected ? '❯ ' : '  '}
      </Text>
      <Text color="gray">{indentStr}</Text>

      {/* Main Title Display with selection background */}
      <Box width={46}>
        <Text
          bold={isSelected}
          color={isSelected ? 'white' : 'white'}
          backgroundColor={isSelected ? 'blue' : undefined}
        >
          {displayName.slice(0, 42).padEnd(42, ' ')}
        </Text>
      </Box>

      {/* Role Tag */}
      {session.role ? (
        <Box width={20}>
          <Text color="magenta" bold={isSelected}>
            [{session.role.slice(0, 18)}]
          </Text>
        </Box>
      ) : (
        <Box width={20} />
      )}

      {/* Status Badge */}
      <Box width={16}>{renderStatusBadge()}</Box>

      {/* Origin Session Tag */}
      {isOrigin && (
        <Box width={24}>
          <Text color="magenta" italic bold>
            (current / backgrounded)
          </Text>
        </Box>
      )}

      {/* Task Summary */}
      {session.currentTask && (
        <Box width={30}>
          <Text color="gray" dimColor>
            {session.currentTask.slice(0, 28)}
          </Text>
        </Box>
      )}
    </Box>
  );
};
