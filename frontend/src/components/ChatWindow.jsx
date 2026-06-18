import { useEffect, useRef, useState } from "react";
import MessageBubble from "./MessageBubble.jsx";
import { sendChat } from "../api.js";

const WELCOME = {
  role: "bot",
  text: "Hi! Ask me anything about the Azure landing zone knowledge base.",
  sources: [],
};

export default function ChatWindow() {
  const [messages, setMessages] = useState([WELCOME]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function handleSend(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    setMessages((m) => [...m, { role: "user", text }]);
    setInput("");
    setLoading(true);

    try {
      const data = await sendChat(text);
      setMessages((m) => [
        ...m,
        { role: "bot", text: data.answer, sources: data.sources },
      ]);
    } catch (err) {
      setMessages((m) => [
        ...m,
        { role: "bot", text: `⚠️ ${err.message}`, sources: [] },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="chat">
      <header className="chat-header">
        <div className="dot" />
        <div>
          <div className="title">Knowledge Chat</div>
          <div className="subtitle">Vector search · RAG</div>
        </div>
      </header>

      <div className="chat-body">
        {messages.map((m, i) => (
          <MessageBubble key={i} message={m} />
        ))}
        {loading && (
          <div className="bubble-row bot">
            <div className="bubble bot typing">
              <span></span><span></span><span></span>
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form className="chat-input" onSubmit={handleSend}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your question…"
          disabled={loading}
        />
        <button type="submit" disabled={loading || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}
