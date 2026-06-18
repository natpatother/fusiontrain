import { useState } from "react";
import ChatWindow from "./components/ChatWindow.jsx";
import UploadPanel from "./components/UploadPanel.jsx";

export default function App() {
  const [tab, setTab] = useState("chat");

  return (
    <div className="app-shell">
      <div className="panel">
        <nav className="tabs">
          <button
            className={tab === "chat" ? "active" : ""}
            onClick={() => setTab("chat")}
          >
            💬 Chat
          </button>
          <button
            className={tab === "upload" ? "active" : ""}
            onClick={() => setTab("upload")}
          >
            ⬆️ Upload
          </button>
        </nav>
        {tab === "chat" ? <ChatWindow /> : <UploadPanel />}
      </div>
    </div>
  );
}
