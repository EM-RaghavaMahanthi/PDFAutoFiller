import React, { useState } from "react";

export default function UploadForm({ onJobStart }) {
  const [pdfFile, setPdfFile] = useState(null);
  const [jsonFile, setJsonFile] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!pdfFile || !jsonFile) return;

    const formData = new FormData();
    formData.append("input_pdf", pdfFile);
    formData.append("input_json", jsonFile);

    setLoading(true);

    try {
      const response = await fetch("/start", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();
      onJobStart(data.job_id);
    } catch (err) {
      console.error("Upload failed:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4 mb-6">
      <div>
        <label className="block mb-1 font-semibold">PDF File</label>
        <input type="file" accept="application/pdf" onChange={(e) => setPdfFile(e.target.files[0])} />
      </div>
      <div>
        <label className="block mb-1 font-semibold">JSON File</label>
        <input type="file" accept=".json" onChange={(e) => setJsonFile(e.target.files[0])} />
      </div>
      <button
        type="submit"
        className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        disabled={loading}
      >
        {loading ? "Uploading..." : "Start Job"}
      </button>
    </form>
  );
}
