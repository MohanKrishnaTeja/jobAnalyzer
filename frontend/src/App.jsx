import React, { useState, useRef } from "react";
import ReactMarkdown from "react-markdown";
import jsPDF from "jspdf";
import "./index.css";

const BACKEND_URL = "http://localhost:8000/api/jobs/complete-analysis/";

function App() {
  const [curriculum, setCurriculum] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [messages, setMessages] = useState([]);
  const [markdownSections, setMarkdownSections] = useState([]);
  const outputRef = useRef(null);

  // Scroll to bottom on new message
  React.useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!curriculum.trim()) return;
    setMessages([]);
    setSubmitted(false);
    setStreaming(false);

    // POST request
    try {
      const res = await fetch(BACKEND_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ curriculum_text: curriculum }),
      });
      if (!res.ok) {
        setMessages([{ type: "error", content: "POST failed: " + res.status }]);
        return;
      }
      setSubmitted(true);
    } catch (err) {
      setMessages([{ type: "error", content: "Error: " + err }]);
    }
  };

  const handleView = () => {
    setMessages([]);
    setStreaming(true);
    setMarkdownSections([]); // reset
    const eventSource = new EventSource(
      `${BACKEND_URL}?curriculum_text=${encodeURIComponent(curriculum)}`
    );
    eventSource.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data);
        let msgType = "text";
        if (
          parsed.step === "summary_generated" ||
          parsed.step === "major_project_generated" ||
          parsed.step === "mini_projects_generated"
        ) {
          msgType = "markdown";
          setMarkdownSections((prev) => [...prev, parsed.data]);
        } else if (
          parsed.step === "skills_extracted" ||
          parsed.step === "roles_identified" ||
          parsed.step === "gaps_analyzed"
        ) {
          msgType = "list";
        } else if (parsed.step === "jobs_fetched") {
          msgType = "jobs";
        } else if (parsed.error) {
          msgType = "error";
        }
        setMessages((prev) => [
          ...prev,
          {
            type: msgType,
            step: parsed.step,
            content:
              msgType === "list"
                ? Array.isArray(parsed.data)
                  ? parsed.data
                  : parsed.data?.missing_skills || parsed.data?.job_market_skills || []
                : parsed.data || parsed.message || parsed.error,
          },
        ]);
        if (parsed.step === "complete" || parsed.error) {
          eventSource.close();
          setStreaming(false);
        }
      } catch {
        setMessages((prev) => [
          ...prev,
          { type: "error", content: "Error parsing stream data." },
        ]);
        eventSource.close();
        setStreaming(false);
      }
    };
    eventSource.onerror = () => {
      setMessages((prev) => [
        ...prev,
        { type: "error", content: "[Stream ended or error occurred]" },
      ]);
      eventSource.close();
      setStreaming(false);
    };
  };

  // Convert all parsed messages to plain text for download
  const getAnalysisText = () => {
    return messages.map((msg) => {
      if (msg.type === "markdown") {
        // Strip markdown formatting for plain text
        return msg.content.replace(/[#*_`>-]/g, "").trim();
      }
      if (msg.type === "list") {
        return (msg.step ? msg.step + ":\n" : "") + msg.content.map((item) => `- ${item}`).join("\n");
      }
      if (
        msg.step === "jobs_fetched" &&
        Array.isArray(msg.content) &&
        msg.content.length > 0 &&
        typeof msg.content[0] === "object"
      ) {
        // Format jobs as a table-like text
        const header = "Title | Company | Location | Source | Posted | Salary | Link\n" +
                       "----- | ------- | -------- | ------ | ------ | ------ | ----";
        const rows = msg.content.map(job =>
          [
            job.title,
            job.company,
            job.location,
            job.source_platform,
            job.posted_date,
            job.salary,
            job.job_url
          ].join(" | ")
        );
        return (msg.step ? msg.step + ":\n" : "") + header + "\n" + rows.join("\n");
      }
      if (msg.type === "error") {
        return "Error: " + msg.content;
      }
      // Default: text
      return (msg.step ? msg.step + ": " : "") + msg.content;
    }).join("\n\n---\n\n");
  };

  const handleDownloadParsed = () => {
    const textContent = getAnalysisText();
    const doc = new jsPDF({
      orientation: "portrait",
      unit: "pt",
      format: "a4"
    });
    // Split text into lines to fit the page width
    const lines = doc.splitTextToSize(textContent, 500);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(12);
    doc.text(lines, 40, 40);
    doc.save("analysis.pdf");
  };

  return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center">
      <div className="w-full max-w-xl bg-gray-800 rounded-lg shadow-lg p-8">
        <h2 className="text-2xl font-bold mb-4 text-white">Curriculum Analysis</h2>
        <form onSubmit={handleSubmit} className="mb-4">
          <textarea
            className="w-full h-28 p-2 rounded bg-gray-700 text-white border border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Paste your curriculum here..."
            value={curriculum}
            onChange={(e) => setCurriculum(e.target.value)}
            disabled={streaming}
          />
          <div className="flex gap-2 mt-2">
            <button
              type="submit"
              className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded disabled:bg-gray-600"
              disabled={streaming}
            >
              Submit
            </button>
            <button
              type="button"
              className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded disabled:bg-gray-600"
              disabled={!submitted || streaming}
              onClick={handleView}
            >
              View Analysis
            </button>
          </div>
        </form>
        <div
          ref={outputRef}
          className="bg-gray-950 text-green-300 rounded p-4 h-80 overflow-y-auto text-sm"
        >
          {messages.length === 0 && (
            <span className="text-gray-400">
              {streaming
                ? "Streaming analysis..."
                : "Submit your curriculum and click 'View Analysis'."}
            </span>
          )}
          {messages.map((msg, idx) => {
            // Render markdown (remove className from ReactMarkdown)
            if (msg.type === "markdown") {
              return (
                <div key={idx} className="mb-4 prose prose-invert">
                  <ReactMarkdown>{msg.content}</ReactMarkdown>
                </div>
              );
            }
            // Render list
            if (msg.type === "list") {
              return (
                <div key={idx} className="mb-2">
                  <ul className="list-disc ml-6">
                    {msg.content.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                </div>
              );
            }
            // Render jobs table if jobs_fetched step
            if (
              msg.step === "jobs_fetched" &&
              Array.isArray(msg.content) &&
              msg.content.length > 0 &&
              typeof msg.content[0] === "object"
            ) {
              return (
                <div key={idx} className="overflow-x-auto mb-4">
                  <table className="min-w-full text-xs text-left text-gray-300">
                    <thead>
                      <tr>
                        <th className="px-2 py-1">Title</th>
                        <th className="px-2 py-1">Company</th>
                        <th className="px-2 py-1">Location</th>
                        <th className="px-2 py-1">Source</th>
                        <th className="px-2 py-1">Posted</th>
                        <th className="px-2 py-1">Salary</th>
                        <th className="px-2 py-1">Description</th>
                        <th className="px-2 py-1">Link</th>
                      </tr>
                    </thead>
                    <tbody>
                      {msg.content.map((job, i) => (
                        <tr key={i} className="border-t border-gray-700">
                          <td className="px-2 py-1">{job.title}</td>
                          <td className="px-2 py-1">{job.company}</td>
                          <td className="px-2 py-1">{job.location}</td>
                          <td className="px-2 py-1">{job.source_platform}</td>
                          <td className="px-2 py-1">{job.posted_date}</td>
                          <td className="px-2 py-1">{job.salary}</td>
                          <td className="px-2 py-1 max-w-xs">
                            <div className="prose prose-invert max-w-xs">
                              <ReactMarkdown>{job.description}</ReactMarkdown>
                            </div>
                          </td>
                          <td className="px-2 py-1">
                            {job.job_url && (
                              <a
                                href={job.job_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-blue-400 underline"
                              >
                                View
                              </a>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              );
            }
            // Render error
            if (msg.type === "error") {
              return (
                <div key={idx} className="text-red-400 mb-2">
                  {msg.content}
                </div>
              );
            }
            // Default: render as text
            return (
              <div key={idx} className="mb-2">
                {msg.content}
              </div>
            );
          })}
        </div>
        {/* Download parsed analysis button */}
        {messages.length > 0 && !streaming && (
          <button
            className="mt-4 bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded"
            onClick={handleDownloadParsed}
          >
            Download Analysis as PDF
          </button>
        )}
      </div>
    </div>
  );
}

export default App;
