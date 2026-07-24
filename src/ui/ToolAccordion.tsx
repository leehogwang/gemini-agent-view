import React, { useState, useEffect } from 'react';
import { Box, Text } from 'ink';
import { ToolCallState } from '../session/types.js';

interface ToolAccordionProps {
  toolCall: ToolCallState;
  isExpandedByDefault?: boolean;
}

const SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];

export const ToolAccordion: React.FC<ToolAccordionProps> = ({
  toolCall,
  isExpandedByDefault = false,
}) => {
  const [isExpanded, setIsExpanded] = useState(isExpandedByDefault);
  const [frameIdx, setFrameIdx] = useState(0);

  useEffect(() => {
    if (toolCall.status === 'running') {
      const timer = setInterval(() => {
        setFrameIdx((prev) => (prev + 1) % SPINNER_FRAMES.length);
      }, 100);
      return () => clearInterval(timer);
    }
  }, [toolCall.status]);

  const durationMs = toolCall.endTime
    ? toolCall.endTime - toolCall.startTime
    : Date.now() - toolCall.startTime;

  const formattedDuration = (durationMs / 1000).toFixed(1) + 's';

  const getStatusBadge = () => {
    switch (toolCall.status) {
      case 'running':
        return (
          <Text color="cyan" bold>
            {SPINNER_FRAMES[frameIdx]} Executing {toolCall.name}... ({formattedDuration})
          </Text>
        );
      case 'completed':
        return (
          <Text color="green">
            ✓ Ran {toolCall.name} ({formattedDuration})
          </Text>
        );
      case 'error':
        return (
          <Text color="red" bold>
            ✖ Failed {toolCall.name} ({formattedDuration})
          </Text>
        );
      case 'pending_approval':
        return (
          <Text color="yellow" bold>
            ? Awaiting approval for {toolCall.name}
          </Text>
        );
      default:
        return <Text color="gray">{toolCall.name}</Text>;
    }
  };

  return (
    <Box flexDirection="column" marginY={1} paddingLeft={1} borderStyle="round" borderColor="gray">
      {/* Header Line */}
      <Box justifyContent="space-between">
        <Box>
          <Text color="gray">{isExpanded ? '▼ ' : '▶ '}</Text>
          {getStatusBadge()}
        </Box>
        {toolCall.args && (
          <Text color="gray" dimColor>
            {JSON.stringify(toolCall.args).slice(0, 40)}
          </Text>
        )}
      </Box>

      {/* Expanded Accordion Details */}
      {isExpanded && (
        <Box flexDirection="column" marginTop={1} paddingLeft={2}>
          {toolCall.args && (
            <Box flexDirection="column" marginBottom={1}>
              <Text color="cyan" bold>
                Parameters:
              </Text>
              <Text color="gray">{JSON.stringify(toolCall.args, null, 2)}</Text>
            </Box>
          )}

          {toolCall.diffSnippet && (
            <Box flexDirection="column" marginBottom={1} borderStyle="single" borderColor="blue">
              <Text color="blue" bold>
                Proposed Changes:
              </Text>
              {toolCall.diffSnippet.split('\n').map((line, idx) => {
                let color = 'white';
                if (line.startsWith('+')) color = 'green';
                if (line.startsWith('-')) color = 'red';
                return (
                  <Text key={idx} color={color}>
                    {line}
                  </Text>
                );
              })}
            </Box>
          )}

          {toolCall.output && (
            <Box flexDirection="column">
              <Text color="magenta" bold>
                Output:
              </Text>
              <Text color="white">{toolCall.output.slice(0, 500)}</Text>
            </Box>
          )}
        </Box>
      )}
    </Box>
  );
};
