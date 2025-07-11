import React from "react";

export default function DownloadButton({ jobId }) {
  const handleDownload = () => {
    window.open(`/download/${jobId}`, "_blank");
  };

  return (
    <button
      onClick={handleDownload}
      className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
    >
      Download Filled PDF
    </button>
  );
}
