import React from 'react';
import type { ChatMessage } from '../../types';

interface MessageListProps {
  messages: ChatMessage[];
}

export const MessageList: React.FC<MessageListProps> = ({ messages }) => {
  return (
    <div className="space-y-4">
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`flex ${msg.role === 'scientist' ? 'justify-end' : 'justify-start'}`}
        >
          <div
            className={`max-w-3xl px-4 py-3 rounded-lg ${
              msg.role === 'scientist'
                ? 'bg-indigo-600 text-white'
                : 'bg-gray-100 text-gray-800'
            }`}
          >
            <div className="text-sm whitespace-pre-wrap">{msg.content}</div>
            <div
              className={`text-xs mt-1 ${
                msg.role === 'scientist' ? 'text-indigo-200' : 'text-gray-500'
              }`}
            >
              {new Date(msg.timestamp).toLocaleTimeString()}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};
