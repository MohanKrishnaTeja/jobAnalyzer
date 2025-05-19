import React, { useState, useRef } from "react";
import ReactMarkdown from "react-markdown";

const BACKEND_URL = "http://localhost:8000/api/jobs/complete-analysis/";

export default function CurriculumAnalysis() {
  const [curriculum, setCurriculum] = useState("");
  const [output, setOutput] = useState([]);
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const eventSourceRef = useRef(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!curriculum.trim()) return;
    setLoading(true);
    setOutput([]);
    setSubmitted(false);

    try {
      const res = await fetch(BACKEND_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ curriculum_text: curriculum }),
      });
      if (!res.ok) {
        setOutput([{ type: "error", text: "POST failed: " + res.status }]);
        setLoading(false);
        return;
      }
      setSubmitted(true);
      setLoading(false);
    } catch (err) {
      setOutput([{ type: "error", text: "Error: " + err }]);
      setLoading(false);
    }
  };

  const handleView = () => {
    setOutput([]);
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    const es = new window.EventSource(
      BACKEND_URL + "?curriculum_text=" + encodeURIComponent(curriculum)
    );
    eventSourceRef.current = es;
    es.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data);
        setOutput((prev) => [
          ...prev,
          {
            type: parsed.step === "summary_generated" ||
                  parsed.step === "major_project_generated" ||
                  parsed.step === "mini_projects_generated"
              ? "markdown"
              : "json",
            data: parsed,
          },
        ]);
        if (parsed.step === "complete") {
          es.close();
        }
      } catch {
        setOutput((prev) => [
          ...prev,
          { type: "error", text: "Error parsing SSE data." },
        ]);
      }
    };
    es.onerror = () => {
      setOutput((prev) => [
        ...prev,
        { type: "error", text: "[Stream ended or error occurred]" },
      ]);
      es.close();
    };
  };

  return (
    <div className="max-w-xl mx-auto bg-gray-900 text-white p-6 rounded shadow mt-10">
      <h2 className="text-2xl mb-4 font-bold">Curriculum Analysis</h2>
      <form onSubmit={handleSubmit}>
        <textarea
          className="w-full h-28 p-2 rounded bg-gray-800 text-white mb-2"
          value={curriculum}
          onChange={(e) => setCurriculum(e.target.value)}
          placeholder="Paste your curriculum here..."
        />
        <div className="flex gap-2">
          <button
            type="submit"
            className="bg-blue-600 px-4 py-2 rounded hover:bg-blue-700"
            disabled={loading}
          >
            {loading ? "Submitting..." : "Submit"}
          </button>
          <button
            type="button"
            className="bg-green-600 px-4 py-2 rounded hover:bg-green-700"
            disabled={!submitted}
            onClick={handleView}
          >
            View Analysis
          </button>
        </div>
      </form>
      <div className="mt-6">
        {output.map((item, idx) =>
          item.type === "markdown" ? (
            <div key={idx} className="bg-gray-800 p-3 rounded mb-2">
              <ReactMarkdown>{String(item.data.data)}</ReactMarkdown>
            </div>
          ) : item.type === "json" ? (
            <pre key={idx} className="bg-gray-800 p-3 rounded mb-2 whitespace-pre-wrap">
              {JSON.stringify(item.data, null, 2)}
            </pre>
          ) : (
            <div key={idx} className="text-red-400">{item.text}</div>
          )
        )}
      </div>
    </div>
  );
}
