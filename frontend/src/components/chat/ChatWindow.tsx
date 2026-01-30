import React, { useState, useEffect, useRef } from 'react';
import { sendChatMessage, getChatHistory } from '../../services/api';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import type { ChatMessage } from '../../types';
import { Card } from '../common/Card';

interface Props {
  goalId: string;
}

export const ChatWindow: React.FC<Props> = ({ goalId }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [contextIds, setContextIds] = useState<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const loadHistory = async () => {
      try {
        const history = await getChatHistory(goalId);
        setMessages(history.messages || []);
      } catch (error) {
        console.error('Failed to load chat history:', error);
      }
    };
    loadHistory();
  }, [goalId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (content: string) => {
    const userMessage: ChatMessage = {
      id: `temp-${Date.now()}`,
      role: 'scientist',
      content,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);

    try {
      const response = await sendChatMessage(goalId, content);
      const aiMessage: ChatMessage = {
        id: `ai-${Date.now()}`,
        role: 'assistant',
        content: response.message,
        timestamp: response.timestamp,
      };
      setMessages((prev) => [...prev, aiMessage]);
      setContextIds(response.context_used || []);
    } catch (error) {
      console.error('Failed to send message:', error);
      const errorMessage: ChatMessage = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: 'Sorry, there was an error processing your message. Please try again.',
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card padding={false} className="h-[600px] flex flex-col">
      <div className="p-4 border-b bg-gray-50">
        <h2 className="text-lg font-semibold text-gray-800">Chat with AI Co-Scientist</h2>
        {contextIds.length > 0 && (
          <p className="text-sm text-gray-500 mt-1">
            Using context from {contextIds.length} hypothesis(es)
          </p>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <MessageList messages={messages} />
        {loading && (
          <div className="flex items-center gap-2 text-gray-500 mt-4">
            <div className="animate-pulse">Thinking...</div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 border-t bg-gray-50">
        <MessageInput onSend={handleSend} disabled={loading} />
      </div>
    </Card>
  );
};
