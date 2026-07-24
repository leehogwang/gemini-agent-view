import React, { useState } from 'react';
import { Box, Text, useInput, Key } from 'ink';

interface InputPromptProps {
  activeSessionName: string;
  onOpenAgentView: () => void;
  onSendMessage: (text: string) => void;
}

export const InputPrompt: React.FC<InputPromptProps> = ({
  activeSessionName,
  onOpenAgentView,
  onSendMessage,
}) => {
  const [value, setValue] = useState('');

  useInput((input: string, key: Key) => {
    // Left Arrow on Empty Input triggers Agent View transition
    if (key.leftArrow && value.length === 0) {
      onOpenAgentView();
      return;
    }

    // Ctrl + Left Arrow triggers Agent View transition
    if (key.ctrl && key.leftArrow) {
      onOpenAgentView();
      return;
    }

    // Backspace handling
    if (key.backspace || key.delete) {
      setValue((prev) => prev.slice(0, -1));
      return;
    }

    // Enter to submit prompt
    if (key.return) {
      if (value.trim() === '/agents' || value.trim() === '/bg') {
        setValue('');
        onOpenAgentView();
        return;
      }
      if (value.trim().length > 0) {
        onSendMessage(value);
        setValue('');
      }
      return;
    }

    // Standard character typing
    if (input && !key.ctrl && !key.meta) {
      setValue((prev) => prev + input);
    }
  });

  return (
    <Box flexDirection="column" marginTop={1}>
      <Box>
        <Text color="cyan" bold>
          ❯{' '}
        </Text>
        <Text>{value}</Text>
        <Text color="gray">▌</Text>
      </Box>
      <Box marginTop={1}>
        <Text color="gray">
          Press <Text color="cyan">←</Text> (on empty input) or <Text color="cyan">Ctrl+←</Text> or type <Text color="cyan">/agents</Text> to open Agent View
        </Text>
      </Box>
    </Box>
  );
};
