import { useRef, useState } from "react";

import { api } from "../../api/client";
import { detailOf } from "./state";
import { primaryCls, secondaryCls } from "./ui";

export interface UploadedBill {
  imageId: string;
  contentType: string;
}

/**
 * Photo or PDF of the bill. The file is kept with the owner's figures (it is not
 * deleted) and shown beside the form so each field can be checked against it.
 * Nothing is read from it in this version: the owner types the fields.
 */
export function BillUpload({
  onUploaded,
  onTypeInstead,
}: {
  onUploaded: (bill: UploadedBill) => void;
  onTypeInstead: () => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const send = async (file: File) => {
    setBusy(true);
    setError(null);
    const body = new FormData();
    body.append("file", file);
    const { data, error: err } = await api.POST("/api/internal/owner/bill-images", {
      // The generated client types the body as the schema's { file: string }; the
      // browser needs the real FormData, so it is passed through as-is.
      body: body as unknown as { file: string },
      bodySerializer: (b: unknown) => b as FormData,
    });
    setBusy(false);
    if (!data) {
      setError(detailOf(err, "We could not upload that. Send a photo or PDF under 8 MB."));
      return;
    }
    onUploaded({ imageId: data.image_id, contentType: data.content_type });
  };

  return (
    <div className="flex max-w-[640px] flex-col gap-6">
      <input
        ref={input}
        type="file"
        accept="image/*,application/pdf"
        className="sr-only"
        aria-label="Bill photo or PDF"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void send(file);
        }}
      />
      <button
        type="button"
        className={primaryCls}
        disabled={busy}
        onClick={() => input.current?.click()}
      >
        {busy ? "Uploading…" : "Take a photo or choose a file"}
      </button>
      <button type="button" className={secondaryCls} onClick={onTypeInstead}>
        Type the units instead
      </button>
      <p className="text-[15px] text-cw-muted">
        We keep your bill for 12 months so you can see it beside your figures, then delete it; the
        figures you confirm stay. Only you can open it. You can delete it, or all your data, at any
        time.
      </p>
      {error && (
        <p role="alert" className="text-cw-negative">
          {error}
        </p>
      )}
    </div>
  );
}
