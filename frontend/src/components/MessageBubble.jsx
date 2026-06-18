import SourceList from "./SourceList.jsx";

export default function MessageBubble({ message }) {
  const isUser = message.role === "user";
  return (
    <div className={`bubble-row ${isUser ? "user" : "bot"}`}>
      <div className={`bubble ${isUser ? "user" : "bot"}`}>
        <div className="bubble-text">{message.text}</div>
        {!isUser && message.sources?.length > 0 && (
          <SourceList sources={message.sources} />
        )}
      </div>
    </div>
  );
}
