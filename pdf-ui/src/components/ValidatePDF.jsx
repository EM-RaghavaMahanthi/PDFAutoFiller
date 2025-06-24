import React, { useState } from 'react';

export default function ValidatePDF({ jobId }) {
  const [file, setFile] = useState(null);
  const [csvData, setCsvData] = useState([]);
  const [csvColumns, setCsvColumns] = useState([]);
  const [downloadUrl, setDownloadUrl] = useState("");

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file || !jobId) return;

    const formData = new FormData();
    formData.append("validation_pdf", file);

    console.log(`Uploading to /validate/${jobId}`);

    try {
      const res = await fetch(`/validate/${jobId}`, {
        method: "POST",
        body: formData,
      });

      const result = await res.json();

      console.log(`Validation now done, formatting table`);

      if (result.status === "success") {
        setCsvColumns(result.columns);
        setCsvData(result.data);
        setDownloadUrl(result.csv_path);
      } else {
        alert(result.error || "Validation failed.");
      }
    } catch (err) {
      console.error("Validation error:", err);
      alert("Error during validation.");
    }
  };

  return (
    <div className="mt-6">
      <form onSubmit={handleSubmit} className="space-y-3">
        <input
          type="file"
          accept="application/pdf"
          onChange={handleFileChange}
          className="block"
        />
        <button
          type="submit"
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          Validate PDF
        </button>
      </form>

      {csvData.length > 0 && (
        <div className="mt-6">
          <h3 className="text-lg font-semibold">Validation Results</h3>
            <table className="min-w-full mt-3 border border-gray-300 text-sm">
            <thead className="bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white">
                <tr>
                {csvColumns.map((col) => (
                    <th key={col} className="px-2 py-1 border">{col}</th>
                ))}
                </tr>
            </thead>
            <tbody className="bg-white dark:bg-gray-800 text-gray-900 dark:text-white">
                {csvData.map((row, idx) => (
                <tr key={idx}>
                    {csvColumns.map((col) => (
                    <td key={col} className="px-2 py-1 border">{row[col]}</td>
                    ))}
                </tr>
                ))}
            </tbody>
            </table>

          <div className="mt-4">
            <a
              href={downloadUrl}
              download
              className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
            >
              Download CSV
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
