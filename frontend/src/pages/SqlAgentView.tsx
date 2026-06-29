import { useState, useRef, useEffect } from 'react';
import { Bot, User, Send, Loader2 } from 'lucide-react';

interface Message {
  id: string;
  role: 'user' | 'bot';
  content: string;
}

export const SqlAgentView = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: inputValue.trim(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);

    try {
      const requestPayload = {
        question: userMessage.content,
        context_limit: 3,
        include_explanation: false
      };

      console.log('Sending request to /api/v1/nl2sql:', requestPayload);

      const response = await fetch('http://localhost:8000/api/v1/nl2sql', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestPayload),
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('Backend validation error / bad response:', {
          status: response.status,
          statusText: response.statusText,
          body: errorText
        });
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const textResponse = await response.text();
      console.log('Response body:', textResponse);

      let botContent = textResponse;
      try {
        const json = JSON.parse(textResponse);
        if (json.sql) {
          botContent = json.sql;
        } else if (typeof json === 'string') {
          botContent = json;
        }
      } catch (e) {
        // Not JSON, just text
      }

      const botMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'bot',
        content: botContent,
      };

      setMessages((prev) => [...prev, botMessage]);
    } catch (error) {
      console.error('Error fetching SQL query:', error);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'bot',
        content: 'Unable to fetch response. Please try again.',
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-50 dark:bg-slate-900 w-full rounded-xl shadow-inner border border-slate-200 dark:border-slate-800 overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 shadow-sm flex items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-cyan-100 dark:bg-cyan-900/30 flex items-center justify-center text-cyan-600 dark:text-cyan-400">
          <Bot className="w-6 h-6" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-100">Matrices UI</h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">Natural Language to SQL Agent</p>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-slate-500 dark:text-slate-400 opacity-60">
            <Bot className="w-16 h-16 mb-4 opacity-50" />
            <p className="text-lg font-medium text-slate-700 dark:text-slate-300">Welcome to Matrices UI</p>
            <p className="text-sm">Ask a question to generate SQL queries.</p>
          </div>
        ) : (
          messages.map((message) => (
            <div
              key={message.id}
              className={`flex w-full ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div className={`flex max-w-[80%] gap-3 ${message.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${message.role === 'user'
                    ? 'bg-blue-600 text-white'
                    : 'bg-cyan-600 text-white'
                  }`}>
                  {message.role === 'user' ? <User className="w-5 h-5" /> : <Bot className="w-5 h-5" />}
                </div>

                <div className={`flex flex-col ${message.role === 'user' ? 'items-end' : 'items-start'}`}>
                  <div className={`px-4 py-3 rounded-2xl ${message.role === 'user'
                      ? 'bg-blue-600 text-white rounded-tr-none'
                      : 'bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200 rounded-tl-none shadow-sm'
                    }`}>
                    {message.role === 'bot' && message.content !== 'Unable to fetch response. Please try again.' ? (
                      <pre className="text-sm font-mono whitespace-pre-wrap break-words overflow-x-auto">
                        <code>{message.content}</code>
                      </pre>
                    ) : (
                      <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))
        )}

        {isLoading && (
          <div className="flex w-full justify-start">
            <div className="flex gap-3 flex-row">
              <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 bg-cyan-600 text-white">
                <Bot className="w-5 h-5" />
              </div>
              <div className="px-4 py-3 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200 rounded-tl-none shadow-sm flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-cyan-600 dark:text-cyan-400" />
                <span className="text-sm text-slate-500">Generating SQL...</span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 bg-white dark:bg-slate-950 border-t border-slate-200 dark:border-slate-800">
        <form onSubmit={handleSubmit} className="relative flex items-end gap-2 max-w-4xl mx-auto">
          <div className="relative flex-1">
            <textarea
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(e);
                }
              }}
              placeholder="Ask a question about your database..."
              className="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl px-4 py-3 pr-12 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500/50 resize-none min-h-[52px] max-h-[150px] overflow-y-auto"
              rows={1}
              disabled={isLoading}
            />
          </div>
          <button
            type="submit"
            disabled={!inputValue.trim() || isLoading}
            className="flex-shrink-0 bg-cyan-600 hover:bg-cyan-700 disabled:opacity-50 disabled:hover:bg-cyan-600 text-white rounded-xl w-[52px] h-[52px] flex items-center justify-center transition-colors"
          >
            <Send className="w-5 h-5 ml-1" />
          </button>
        </form>
        <p className="text-center text-xs text-slate-400 dark:text-slate-500 mt-3">
          Matrices UI converts natural language directly to SQL queries.
        </p>
      </div>
    </div>
  );
};
