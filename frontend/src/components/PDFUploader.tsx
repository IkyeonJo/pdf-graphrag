import { useRef, useState } from "react";
import { api, type UploadResponse } from "../api/client";

type Props = {
  onUploaded: (res: UploadResponse) => void;
};

export function PDFUploader({ onUploaded }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>("");
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFile(file: File) {
    setError("");
    setBusy(true);
    try {
      const res = await api.upload(file);
      onUploaded(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className={[
        "rounded-lg border-2 border-dashed p-8 text-center transition-colors",
        dragActive
          ? "border-brand-500 bg-brand-50"
          : "border-slate-300 bg-white",
      ].join(" ")}
      onDragOver={(e) => {
        e.preventDefault();
        setDragActive(true);
      }}
      onDragLeave={() => setDragActive(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragActive(false);
        const f = e.dataTransfer.files?.[0];
        if (f) void handleFile(f);
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) void handleFile(f);
        }}
      />
      <div className="text-sm text-slate-600">
        {busy ? (
          <span className="font-medium text-brand-700">
            추출 중… 10–30초 소요
          </span>
        ) : (
          <>
            PDF 파일을 드래그하거나{" "}
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="font-medium text-brand-600 underline hover:text-brand-700"
            >
              클릭하여 선택
            </button>
          </>
        )}
      </div>
      {error && (
        <p className="mt-4 rounded bg-red-50 p-3 text-left text-xs text-red-700">
          {error}
        </p>
      )}
    </div>
  );
}
