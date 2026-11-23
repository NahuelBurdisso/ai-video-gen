import { useState } from "react";
import ChatPanel from "./components/ChatPanel";
import PipelinePanel from "./components/PipelinePanel";
import ImagePanel from "./components/ImagePanel";
import { Film, MessageSquare, Image } from "lucide-react";

type Tab = "chat" | "pipeline" | "images";

export default function App() {
  const [tab, setTab] = useState<Tab>("chat");

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <header className="flex items-center justify-between px-4 py-2 border-b border-zinc-800 bg-zinc-900/80 backdrop-blur">
        <h1 className="text-lg font-semibold tracking-tight">AI Video Director</h1>
        <nav className="flex gap-1">
          {([
            ["chat", MessageSquare, "Chat"],
            ["pipeline", Film, "Pipeline"],
            ["images", Image, "Images"],
          ] as const).map(([id, Icon, label]) => (
            <button
              key={id}
              onClick={() => setTab(id as Tab)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-sm transition
                ${tab === id ? "bg-zinc-700 text-white" : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800"}`}
            >
              <Icon size={16} />
              {label}
            </button>
          ))}
        </nav>
      </header>

      {/* Content */}
      <main className="flex-1 overflow-hidden">
        {tab === "chat" && <ChatPanel />}
        {tab === "pipeline" && <PipelinePanel />}
        {tab === "images" && <ImagePanel />}
      </main>
    </div>
  );
}
