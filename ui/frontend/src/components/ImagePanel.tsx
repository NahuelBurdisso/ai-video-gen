import { useState, useEffect, useRef } from "react";
import { Upload, Image as ImageIcon, Trash2 } from "lucide-react";

type ImageEntry = { name: string; size: number; url: string };

export default function ImagePanel() {
  const [images, setImages] = useState<ImageEntry[]>([]);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const fetchImages = async () => {
    try {
      const res = await fetch("/api/images/list");
      const data = await res.json();
      setImages(data.images || []);
    } catch {}
  };

  useEffect(() => {
    fetchImages();
  }, []);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    const form = new FormData();
    form.append("file", file);

    try {
      await fetch("/api/images/upload", { method: "POST", body: form });
      await fetchImages();
    } catch {}
    setUploading(false);
    if (fileRef.current) fileRef.current.value = "";
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="h-full overflow-y-auto p-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold">Input Images</h2>
        <label className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 rounded text-sm cursor-pointer transition">
          <Upload size={16} />
          {uploading ? "Uploading..." : "Upload"}
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            onChange={handleUpload}
            className="hidden"
            disabled={uploading}
          />
        </label>
      </div>

      <p className="text-zinc-500 text-sm mb-4">
        Upload images here to use with Image-to-Video generation. Reference them by filename in chat.
      </p>

      {images.length === 0 ? (
        <div className="text-center text-zinc-500 mt-16">
          <ImageIcon size={48} className="mx-auto mb-3 opacity-30" />
          <p>No images uploaded yet</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {images.map((img) => (
            <div key={img.name} className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden">
              <img
                src={img.url}
                alt={img.name}
                className="w-full aspect-video object-cover"
              />
              <div className="p-2">
                <p className="text-xs text-zinc-300 truncate">{img.name}</p>
                <p className="text-xs text-zinc-500">{formatSize(img.size)}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
