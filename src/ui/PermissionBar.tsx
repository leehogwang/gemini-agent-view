import React from 'react';
import { Box, Text, useInput, Key } from 'ink';

interface PermissionBarProps {
  toolName: string;
  description: string;
  details?: string;
  onRespond: (action: 'allow' | 'always' | 'deny' | 'edit') => void;
}

export const PermissionBar: React.FC<PermissionBarProps> = ({
  toolName,
  description,
  details,
  onRespond,
}) => {
  useInput((input: string, key: Key) => {
    const char = input.toLowerCase();
    if (char === 'y') {
      onRespond('allow');
    } else if (char === 'a') {
      onRespond('always');
    } else if (char === 'n' || key.escape) {
      onRespond('deny');
    } else if (char === 'e') {
      onRespond('edit');
    }
  });

  return (
    <Box
      flexDirection="column"
      marginY={1}
      paddingX={1}
      paddingY={1}
      borderStyle="round"
      borderColor="yellow"
    >
      <Box marginBottom={1}>
        <Text bold color="yellow">
          Action Permission Required: [{toolName}]
        </Text>
      </Box>

      <Box marginBottom={1}>
        <Text color="white">{description}</Text>
      </Box>

      {details && (
        <Box marginBottom={1} paddingX={1} borderStyle="single" borderColor="gray">
          <Text color="gray">{details}</Text>
        </Box>
      )}

      <Box marginTop={1} justifyContent="space-between">
        <Text color="gray">
          Press <Text bold color="green">[y]</Text> Allow |{' '}
          <Text bold color="cyan">[a]</Text> Always Allow |{' '}
          <Text bold color="red">[n]</Text> Deny |{' '}
          <Text bold color="yellow">[e]</Text> Edit Prompt
        </Text>
      </Box>
    </Box>
  );
};
