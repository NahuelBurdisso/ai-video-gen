import { CheckCircle, AlertTriangle } from "lucide-react";

type Props = {
  plan: Record<string, unknown>;
  warnings?: string[];
  onApprove: () => void;
};

export default function PlanCard({ plan, warnings, onApprove }: Props) {
  const p = (plan as any).plan || plan;
  const scenes = p.scenes || [];
  const settings = p.settings || {};

  return (
    <div className="mt-3 bg-zinc-900 border border-zinc-700 rounded-lg p-3 text-xs">
      <div className="font-semibold text-zinc-300 mb-2">Generation Plan: {p.title}</div>

      <div className="text-zinc-400 mb-2">
        {scenes.length} scene{scenes.length !== 1 ? "s" : ""} |{" "}
        {settings.resolution?.[0]}x{settings.resolution?.[1]} |{" "}
        {settings.steps} steps | cfg {settings.cfg}
      </div>

      {scenes.map((s: any, i: number) => (
        <div key={i} className="mb-1.5 pl-2 border-l-2 border-zinc-700">
          <span className="text-zinc-500">Scene {i + 1}</span>{" "}
          <span className="text-zinc-400">({s.duration}s)</span>
          <div className="text-zinc-300 truncate">{s.prompt}</div>
          {s.input_image && (
            <div className="text-blue-400">Image: {s.input_image}</div>
          )}
        </div>
      ))}

      {warnings && warnings.length > 0 && (
        <div className="mt-2 space-y-1">
          {warnings.map((w, i) => (
            <div key={i} className="text-yellow-400 flex items-center gap-1">
              <AlertTriangle size={12} /> {w}
            </div>
          ))}
        </div>
      )}

      <button
        onClick={onApprove}
        className="mt-2 flex items-center gap-1.5 px-3 py-1.5 bg-green-600 hover:bg-green-500 rounded text-white text-xs font-medium transition"
      >
        <CheckCircle size={14} /> Approve & Generate
      </button>
    </div>
  );
}
