import React, { useState } from 'react';
import UploadForm from './components/UploadForm';
import StatusLog from './components/StatusLog';
import DownloadButton from './components/DownloadButton';
import DarkModeToggle from './components/DarkModeToggle';
import PreviewPDF from './components/PreviewPDF';
import ValidatePDF from './components/ValidatePDF';
import Spinner from "./components/Spinner";

export default function App() {
  const [jobId, setJobId] = useState(null);
  const [statusLogs, setStatusLogs] = useState([]);
  const [done, setDone] = useState(false);

  const handleJobStart = (id) => {
    if (jobId === id) return;

    setJobId(id);
    setStatusLogs(["📄 Job Started..."]);
    setDone(false);

    const eventSource = new EventSource(`/stream/${id}`);

    eventSource.onmessage = (e) => {
      const message = `✅ ${e.data}`;
      setStatusLogs((prev) => {
        if (prev.includes(message)) return prev;
        return [...prev, message];
      });

      if (e.data.includes("Done filling.")) {
        setDone(true);
        eventSource.close();
      }
    };

    eventSource.onerror = (err) => {
      console.error("SSE error:", err);
      eventSource.close();
    };
  };

  return (
    <div className="min-h-screen bg-gray-100 dark:bg-gray-900 text-gray-900 dark:text-white transition-colors">
      <div className="max-w-2xl mx-auto py-12 px-6 space-y-6">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-bold">PDF AutoFiller</h1>
          <DarkModeToggle />
        </div>

        <UploadForm onJobStart={handleJobStart} />

        <div className="bg-white dark:bg-gray-800 p-4 rounded shadow max-h-96 overflow-y-auto">
          <StatusLog logs={statusLogs} />
        </div>

        {!done && jobId && (
          <div className="flex justify-center mt-4">
            <Spinner />
          </div>
        )}

        {done && jobId && (
          <>
            <div className="flex space-x-4 mt-6">
              <PreviewPDF jobId={jobId} />
              <DownloadButton jobId={jobId} />
            </div>

            <ValidatePDF jobId={jobId} />
          </>
        )}
      </div>
    </div>
  );
}
