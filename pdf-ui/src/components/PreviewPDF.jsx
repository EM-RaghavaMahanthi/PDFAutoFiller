import React from "react";

export default function PreviewPDF({ jobId }) {
  const previewUrl = `/download/${jobId}?preview=1`;
  return (
    <a
      href={previewUrl}
      target="_blank"
      rel="noopener noreferrer"
      className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 mr-2"
    >
      📄 Preview PDF
    </a>
  );
}
