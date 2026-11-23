import { useState, useRef, useEffect, useCallback } from "react";
import { useWebSocket } from "../hooks/useWebSocket";
import { Send, Loader2, XCircle, ImagePlus, X } from "lucide-react";
import PlanCard from "./PlanCard";

type Message = {
  role: "user" | "assistant";
  content: string;
  image?: string;
  plan?: Record<string, unknown>;
  planWarnings?: string[];
  planError?: string;
};

type ImageEntry = { name: string; url: string };

const WS_URL = `ws://${window.location.host}/ws/chat`;

export default function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [attachedImage, setAttachedImage] = useState<string | null>(null);
  const [showGallery, setShowGallery] = useState(false);
  const [gallery, setGallery] = useState<ImageEntry[]>([]);
  const streamBuf = useRef("");
  const bottomRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(scrollToBottom, [messages, streaming]);

  const fetchGallery = async () => {
    try {
      const res = await fetch("/api/images/list");
      const data = await res.json();
      setGallery(data.images || []);
    } catch {}
  };

  const handleWS = useCallback((msg: { type: string; data: Record<string, unknown> }) => {
    switch (msg.type) {
      case "chunk":
        streamBuf.current += msg.data.content as string;
        setMessages((prev) => {
          const copy = [...prev];
          const last = copy[copy.length - 1];
          if (last?.role === "assistant") {
            copy[copy.length - 1] = { ...last, content: streamBuf.current };
          }
          return copy;
        });
        break;

      case "done":
        setStreaming(false);
        streamBuf.current = "";
        break;

      case "plan":
        setMessages((prev) => {
          const copy = [...prev];
          const last = copy[copy.length - 1];
          if (last?.role === "assistant") {
            copy[copy.length - 1] = {
              ...last,
              plan: msg.data.plan as Record<string, unknown>,
              planWarnings: msg.data.warnings as string[],
            };
          }
          return copy;
        });
        break;

      case "plan_error":
        setMessages((prev) => {
          const copy = [...prev];
          const last = copy[copy.length - 1];
          if (last?.role === "assistant") {
            copy[copy.length - 1] = { ...last, planError: msg.data.message as string };
          }
          return copy;
        });
        break;

      case "error":
        setStreaming(false);
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: `Error: ${msg.data.message}` },
        ]);
        break;
    }
  }, []);

  const { send, connected } = useWebSocket(WS_URL, handleWS);

  const handleSend = () => {
    const text = input.trim();
    if ((!text && !attachedImage) || streaming) return;

    setMessages((prev) => [
      ...prev,
      { role: "user", content: text, image: attachedImage || undefined },
      { role: "assistant", content: "" },
    ]);
    setStreaming(true);
    streamBuf.current = "";
    send({ content: text, image: attachedImage || undefined });
    setInput("");
    setAttachedImage(null);
  };

  const handleApprove = async (plan: Record<string, unknown>) => {
    const res = await fetch("/api/pipeline/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ plan }),
    });
    const data = await res.json();
    if (data.error) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Pipeline error: ${data.error}` },
      ]);
    } else {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Pipeline started: "${data.title}" (${data.total_clips} clips). Switch to Pipeline tab to monitor.` },
      ]);
    }
  };

  const openGallery = () => {
    fetchGallery();
    setShowGallery(true);
  };

  const pickImage = (name: string) => {
    setAttachedImage(name);
    setShowGallery(false);
  };

  return (
    <div className="h-full flex flex-col relative">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-zinc-500 text-center mt-20">
            <p className="text-xl mb-2">Describe the video you want to create</p>
            <p className="text-sm">The AI Director will plan scenes and generate them with Wan2.2</p>
            <p className="text-xs mt-2 text-zinc-600">Attach an image for Image-to-Video mode</p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[80%] rounded-lg px-4 py-2 text-sm leading-relaxed whitespace-pre-wrap chat-content
                ${msg.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-zinc-800 text-zinc-200"
                }`}
            >
              {msg.image && (
                <div className="mb-2">
                  <img
                    src={`/static/input/${msg.image}`}
                    alt={msg.image}
                    className="max-w-[200px] rounded border border-blue-400/30"
                  />
                  <span className="text-xs opacity-70">{msg.image}</span>
                </div>
              )}
              {msg.content}
              {msg.plan && (
                <PlanCard
                  plan={msg.plan}
                  warnings={msg.planWarnings}
                  onApprove={() => handleApprove(msg.plan!)}
                />
              )}
              {msg.planError && (
                <div className="mt-2 text-red-400 text-xs flex items-center gap-1">
                  <XCircle size={14} /> Plan error: {msg.planError}
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Attached image preview */}
      {attachedImage && (
        <div className="px-3 pt-2 flex items-center gap-2 text-xs text-blue-400">
          <img src={`/static/input/${attachedImage}`} alt="" className="w-8 h-8 rounded object-cover" />
          <span>{attachedImage}</span>
          <button onClick={() => setAttachedImage(null)} className="text-zinc-500 hover:text-zinc-300">
            <X size={14} />
          </button>
        </div>
      )}

      {/* Input */}
      <div className="border-t border-zinc-800 p-3">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full flex-shrink-0 ${connected ? "bg-green-500" : "bg-red-500"}`} />
          <button
            onClick={openGallery}
            className="p-2 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition"
            title="Attach image for I2V"
          >
            <ImagePlus size={18} />
          </button>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
            placeholder={connected ? "Describe your video..." : "Connecting..."}
            disabled={!connected || streaming}
            className="flex-1 bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm
              placeholder-zinc-500 focus:outline-none focus:border-zinc-500 disabled:opacity-50"
          />
          <button
            onClick={handleSend}
            disabled={!connected || streaming || (!input.trim() && !attachedImage)}
            className="p-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-30 transition"
          >
            {streaming ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
          </button>
        </div>
      </div>

      {/* Image Gallery Modal */}
      {showGallery && (
        <div className="absolute inset-0 bg-black/70 z-10 flex items-end">
          <div className="w-full bg-zinc-900 border-t border-zinc-700 rounded-t-xl p-4 max-h-[60%] overflow-y-auto">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium">Pick image for I2V</span>
              <button onClick={() => setShowGallery(false)} className="text-zinc-400 hover:text-white">
                <X size={18} />
              </button>
            </div>
            {gallery.length === 0 ? (
              <p className="text-zinc-500 text-sm text-center py-8">No images. Upload in Images tab first.</p>
            ) : (
              <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
                {gallery.map((img) => (
                  <button
                    key={img.name}
                    onClick={() => pickImage(img.name)}
                    className="rounded overflow-hidden border border-zinc-700 hover:border-blue-500 transition"
                  >
                    <img src={img.url} alt={img.name} className="w-full aspect-video object-cover" />
                    <p className="text-xs text-zinc-400 px-1 py-0.5 truncate">{img.name}</p>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
