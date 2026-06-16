import { useServingInvoke } from '@databricks/appkit-ui/react';
import { useState } from 'react';
import { Bot, User, Send } from 'lucide-react';

interface ChatChoice {
  message?: { content?: string };
}
interface ChatResponse {
  choices?: ChatChoice[];
}

function extractContent(data: unknown): string {
  const resp = data as ChatResponse;
  return resp?.choices?.[0]?.message?.content ?? JSON.stringify(data);
}

const SYSTEM_PROMPT =
  'You are the Lumen Virtue assistant, helping a team work with a dataset of healthcare facilities. ' +
  'Help with concise, friendly answers: drafting outreach to facilities, summarizing information, and ' +
  'brainstorming how to analyze facility data. Keep responses short and practical.';

const SUGGESTIONS = [
  'Draft an outreach email to a hospital',
  'Ideas to analyze facility coverage gaps',
  'Summarize what makes a facility well-equipped',
];

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

export function ServingPage() {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const { invoke, loading, error } = useServingInvoke({ messages: [] });

  function send(text: string) {
    const content = text.trim();
    if (!content || loading) return;

    const userMessage: Message = { id: crypto.randomUUID(), role: 'user', content };
    // Prime the model with context as a user/assistant pair (the endpoint accepts
    // only user/assistant roles). These priming turns are sent but never displayed.
    const fullMessages = [
      { role: 'user' as const, content: SYSTEM_PROMPT },
      { role: 'assistant' as const, content: 'Understood — I am the Lumen Virtue assistant. How can I help?' },
      ...messages.map(({ role, content }) => ({ role, content })),
      { role: 'user' as const, content },
    ];

    setMessages((prev) => [...prev, userMessage]);
    setInput('');

    void invoke({ messages: fullMessages }).then((result) => {
      if (result) {
        setMessages((prev) => [
          ...prev,
          { id: crypto.randomUUID(), role: 'assistant', content: extractContent(result) },
        ]);
      }
    });
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    send(input);
  }

  const empty = messages.length === 0;

  return (
    <div className="max-w-4xl mx-auto px-4 md:px-6 py-8 space-y-5">
      <div className="space-y-1">
        <h2 className="text-2xl font-bold text-foreground flex items-center gap-2">
          <Bot className="h-5 w-5 text-primary" /> Lumen Virtue Assistant
        </h2>
        <p className="text-sm text-muted-foreground">Powered by Claude Opus 4.8 on Databricks Model Serving.</p>
      </div>

      <div className="border rounded-xl flex flex-col h-[min(620px,72vh)] bg-card">
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {empty && (
            <div className="h-full flex flex-col items-center justify-center text-center gap-4 px-6">
              <span className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
                <Bot className="h-6 w-6" />
              </span>
              <p className="text-sm text-muted-foreground max-w-sm">
                Ask the assistant anything — drafting outreach, brainstorming, or summarizing facility data.
              </p>
              <div className="flex flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => send(s)}
                    className="rounded-full border px-3 py-1.5 text-xs text-muted-foreground hover:border-primary/40 hover:text-foreground transition-colors"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <div key={msg.id} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {msg.role === 'assistant' && (
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                  <Bot className="h-4 w-4" />
                </span>
              )}
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-2 ${
                  msg.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted text-foreground'
                }`}
              >
                <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
              </div>
              {msg.role === 'user' && (
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
                  <User className="h-4 w-4" />
                </span>
              )}
            </div>
          ))}

          {loading && (
            <div className="flex gap-3 justify-start">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                <Bot className="h-4 w-4" />
              </span>
              <div className="rounded-2xl px-4 py-2 bg-muted text-muted-foreground">
                <p className="text-sm">Thinking…</p>
              </div>
            </div>
          )}

          {error && <div className="text-destructive text-sm p-2 bg-destructive/10 rounded">Error: {error}</div>}
        </div>

        <form onSubmit={handleSubmit} className="border-t p-3 flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Send a message..."
            className="flex-1 rounded-md border px-3 py-2 text-sm bg-background"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary text-primary-foreground px-4 py-2 text-sm font-medium disabled:opacity-50"
          >
            <Send className="h-4 w-4" /> Send
          </button>
        </form>
      </div>
    </div>
  );
}
