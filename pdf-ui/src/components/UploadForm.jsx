import React, { useState } from "react";

export default function UploadForm({ onJobStart }) {
  const [pdfFile, setPdfFile] = useState(null);
  const [jsonFile, setJsonFile] = useState(null);
  const [formData, setFormData] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [readyToStart, setReadyToStart] = useState(false);

  const handleUpload = async () => {
    if (!pdfFile || !jsonFile) return;

    const data = new FormData();
    data.append("input_pdf", pdfFile);
    data.append("input_json", jsonFile);

    setUploading(true);
    // simulate "uploading" (just saving files in memory)
    setTimeout(() => {
      setFormData(data);
      setReadyToStart(true);
      setUploading(false);
    }, 1000); // 1 second fake delay to mimic uploading
  };

  const handleStartJob = async () => {
    if (!formData) return;

    try {
      const response = await fetch("/start", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();
      onJobStart(data.job_id);
    } catch (err) {
      console.error("Job start failed:", err);
    }
  };

  return (
    <div className="space-y-4 mb-6">
      <div>
        <label className="block mb-1 font-semibold">PDF File</label>
        <input type="file" accept="application/pdf" onChange={(e) => setPdfFile(e.target.files[0])} />
      </div>
      <div>
        <label className="block mb-1 font-semibold">JSON File</label>
        <input type="file" accept=".json" onChange={(e) => setJsonFile(e.target.files[0])} />
      </div>

      {!readyToStart ? (
        <button
          onClick={handleUpload}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          disabled={uploading || !pdfFile || !jsonFile}
        >
          {uploading ? "Uploading..." : "Upload Files"}
        </button>
      ) : (
        <button
          onClick={handleStartJob}
          className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
        >
          Start Job
        </button>
      )}
    </div>
  );
}
