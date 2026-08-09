import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Send, Sparkles, RefreshCw, AlertCircle, MessageSquare, Trash2, ArrowDown,
} from 'lucide-react';
import renderMarkdown from './markdown';

/**
 * The AI coach.
 *
 * The previous screen was a page of cards: a permanent "Rate Limited - Using
 * Fallback Responses" banner that was hardcoded and therefore always wrong, a
 * grid listing six internal agent names, a "Chat with AI Assistant" heading
 * above a bordered box, and light-theme styling inside a dark app.
 *
 * A conversation should look like a conversation. So: the messages are the
 * page, the composer sits at the bottom, and everything else appears only when
 * it has something to say.
 *
 *  - Service status shows ONLY when something is actually wrong. A warning
 *    that is always visible is one nobody reads.
 *  - The empty state is a real opener drawn from the user's own day, with
 *    tappable suggestions, rather than "Start a conversation!".
 *  - The agent list is gone. Users do not care that ChefGenius and FitMentor
 *    are separate services; that was internal architecture on display.
 */

function Bubble({ message }) {
  const isUser = message.type === 'user';
  return (
    <div className={`msg-row ${isUser ? 'msg-row-user' : ''}`}>
      {!isUser && (
        <div className="msg-avatar">
          <Sparkles size={14} />
        </div>
      )}
      <div className={`msg-bubble ${isUser ? 'msg-user' : 'msg-bot'}`}>
        {isUser ? (
          <div style={{ whiteSpace: 'pre-wrap' }}>{message.content}</div>
        ) : (
          <div
            className="recipe-body"
            dangerouslySetInnerHTML={{ __html: renderMarkdown(message.content) }}
          />
        )}
        <div className="msg-time">
          {message.timestamp.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}
        </div>
      </div>
    </div>
  );
}

export default function Assistant({ apiBase, userName }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [status, setStatus] = useState(null);
  const [opener, setOpener] = useState(null);
  const [error, setError] = useState('');
  const [atBottom, setAtBottom] = useState(true);

  const scrollRef = useRef(null);
  const inputRef = useRef(null);
  const endRef = useRef(null);

  const headers = useCallback(() => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('token')}`,
  }), []);

  // --- load history, opener and real service state ---------------------
  useEffect(() => {
    let cancelled = false;

    fetch(`${apiBase}/chatbot/history?limit=60`, { headers: headers() })
      .then((r) => (r.ok ? r.json() : []))
      .then((rows) => {
        if (cancelled || !Array.isArray(rows)) return;
        setMessages(rows.map((row, i) => ({
          id: `h${i}`,
          type: row.role === 'user' ? 'user' : 'bot',
          content: row.content || '',
          timestamp: row.timestamp ? new Date(row.timestamp) : new Date(),
        })));
      })
      .catch(() => {});

    fetch(`${apiBase}/chatbot/opener`, { headers: headers() })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => !cancelled && d && setOpener(d))
      .catch(() => {});

    fetch(`${apiBase}/chatbot/status`, { headers: headers() })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => !cancelled && d && setStatus(d))
      .catch(() => {});

    return () => { cancelled = true; };
  }, [apiBase, headers]);

  // Keep the newest message in view, but never yank the page while someone is
  // reading back through a long plan.
  useEffect(() => {
    if (atBottom) endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, sending, atBottom]);

  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    setAtBottom(el.scrollHeight - el.scrollTop - el.clientHeight < 120);
  };

  const send = async (text) => {
    const query = (text ?? input).trim();
    if (!query || sending) return;

    setMessages((prev) => [...prev, {
      id: Date.now(), type: 'user', content: query, timestamp: new Date(),
    }]);
    setInput('');
    setSending(true);
    setError('');
    setAtBottom(true);

    try {
      const res = await fetch(`${apiBase}/chatbot/chat/simple`, {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({ query }),
      });
      const data = await res.json().catch(() => ({}));
      const reply = (data.response || '').trim();

      if (!res.ok || !reply) {
        setError(
          typeof data.detail === 'string'
            ? data.detail
            : "I couldn't get a reply just then. Try again in a moment."
        );
      } else {
        setMessages((prev) => [...prev, {
          id: Date.now() + 1, type: 'bot', content: reply, timestamp: new Date(),
        }]);
      }
      // The service may have degraded during that call.
      fetch(`${apiBase}/chatbot/status`, { headers: headers() })
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => d && setStatus(d))
        .catch(() => {});
    } catch {
      setError('Could not reach the server. Is the backend running?');
    } finally {
      setSending(false);
      inputRef.current?.focus();
    }
  };

  const clearHistory = async () => {
    setMessages([]);
    setError('');
    try {
      await fetch(`${apiBase}/chatbot/history`, { method: 'DELETE', headers: headers() });
    } catch { /* the screen is already clear; a failed delete is not worth a dialog */ }
    fetch(`${apiBase}/chatbot/opener`, { headers: headers() })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d && setOpener(d))
      .catch(() => {});
  };

  const onKeyDown = (e) => {
    // Enter sends, Shift+Enter is a newline - what every chat app does.
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const empty = messages.length === 0;

  return (
    <div className="chat-page">
      {/* --- header ---------------------------------------------------- */}
      <div className="chat-head">
        <div className="flex items-center" style={{ gap: '0.75rem', minWidth: 0 }}>
          <div className="chat-head-mark">
            <Sparkles size={18} color="#fff" />
          </div>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontWeight: 700, letterSpacing: '-0.01em' }}>NutriCoach</div>
            <div className="section-sub" style={{ fontSize: '0.75rem' }}>
              Meals, workouts and plans — built around your day
            </div>
          </div>
        </div>
        {!empty && (
          <button className="ghost-btn chat-new" onClick={clearHistory} title="Start a new conversation">
            {/* The label is hidden on a phone by CSS, leaving a square icon
                button - the two-word label wrapped onto two lines and made the
                header taller than the first message. */}
            <Trash2 size={14} /> <span className="chat-new-label">New chat</span>
          </button>
        )}
      </div>

      {/* Shown only when something is genuinely wrong. */}
      {status && status.state !== 'ready' && status.message && (
        <div className={`chat-status ${status.state === 'down' ? 'is-down' : 'is-degraded'}`}>
          <AlertCircle size={14} />
          <span>{status.message}</span>
        </div>
      )}

      {/* --- messages -------------------------------------------------- */}
      <div className="chat-scroll" ref={scrollRef} onScroll={onScroll}>
        {empty ? (
          <div className="chat-welcome">
            <div className="chat-welcome-mark">
              <MessageSquare size={26} />
            </div>
            <p className="chat-welcome-text">
              {opener?.greeting
                || `Hi${userName ? ` ${userName.split(' ')[0]}` : ''}. What can I help with today?`}
            </p>
            {opener?.suggestions?.length > 0 && (
              <div className="chat-suggestions">
                {opener.suggestions.map((s) => (
                  <button key={s} className="suggest-chip" onClick={() => send(s)}>
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="chat-thread">
            {messages.map((m) => <Bubble key={m.id} message={m} />)}

            {sending && (
              <div className="msg-row">
                <div className="msg-avatar"><Sparkles size={14} /></div>
                <div className="msg-bubble msg-bot">
                  <div className="typing">
                    <span /><span /><span />
                  </div>
                </div>
              </div>
            )}

            {error && (
              <div className="auth-error" style={{ margin: '0 0 0 2.4rem', maxWidth: 420 }}>
                <AlertCircle size={15} /> <span>{error}</span>
              </div>
            )}

            <div ref={endRef} />
          </div>
        )}
      </div>

      {!atBottom && !empty && (
        <button
          className="scroll-down"
          onClick={() => { setAtBottom(true); endRef.current?.scrollIntoView({ behavior: 'smooth' }); }}
          aria-label="Jump to latest"
        >
          <ArrowDown size={16} />
        </button>
      )}

      {/* --- composer -------------------------------------------------- */}
      <div className="chat-composer">
        <textarea
          ref={inputRef}
          className="chat-input"
          rows={1}
          placeholder="Ask about meals, workouts, or what to eat next…"
          value={input}
          disabled={status?.state === 'down'}
          onChange={(e) => {
            setInput(e.target.value);
            // Grow with the text, up to a limit, then scroll.
            e.target.style.height = 'auto';
            e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
          }}
          onKeyDown={onKeyDown}
        />
        <button
          className="chat-send"
          onClick={() => send()}
          disabled={!input.trim() || sending || status?.state === 'down'}
          aria-label="Send"
        >
          {sending ? <RefreshCw size={17} className="spin" /> : <Send size={17} />}
        </button>
      </div>
    </div>
  );
}
