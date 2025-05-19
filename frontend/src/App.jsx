import React, { useState, useRef } from "react";
import ReactMarkdown from "react-markdown";
import jsPDF from "jspdf";
import { CheckCircleIcon, ClockIcon, ArrowPathIcon } from "@heroicons/react/24/solid";
import { Card, CardHeader, CardTitle, CardContent } from "./components/ui/card";
import { Button } from "./components/ui/button";
import { Textarea } from "./components/ui/textarea";
import "./index.css";

const BACKEND_URL = "http://localhost:8000/api/jobs/complete-analysis/";

const STEPS = [
  { key: "extracting_skills", label: "Analyzing your curriculum..." },
  { key: "skills_extracted", label: "Skills extracted" },
  { key: "identifying_roles", label: "Identifying relevant job roles..." },
  { key: "roles_identified", label: "Roles identified" },
  { key: "fetching_jobs", label: "Fetching relevant job listings..." },
  { key: "jobs_fetched", label: "Jobs fetched" },
  { key: "generating_summary", label: "Analyzing job requirements..." },
  { key: "summary_generated", label: "Job summary generated" },
  { key: "analyzing_gaps", label: "Analyzing skill gaps..." },
  { key: "gaps_analyzed", label: "Skill gaps analyzed" },
  { key: "generating_projects", label: "Generating project recommendations..." },
  { key: "major_project_generated", label: "Major project generated" },
  { key: "mini_projects_generated", label: "Mini projects generated" },
  { key: "complete", label: "Analysis complete!" },
];

function App() {
  const [curriculum, setCurriculum] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [messages, setMessages] = useState([]);
  const [progress, setProgress] = useState([]);
  const outputRef = useRef(null);

  React.useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!curriculum.trim()) return;
    setMessages([]);
    setProgress([]);
    setSubmitted(false);
    setStreaming(false);

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
    setProgress([]);
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
        // Update progress
        if (parsed.step) {
          setProgress((prev) =>
            prev.includes(parsed.step) ? prev : [...prev, parsed.step]
          );
        }
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

  const getAnalysisText = () => {
    return messages.map((msg) => {
      if (msg.type === "markdown") {
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
    const lines = doc.splitTextToSize(textContent, 500);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(12);
    doc.text(lines, 40, 40);
    doc.save("analysis.pdf");
  };

  // Stepper icon helpers
  const getStepIcon = (step, idx, currentIdx, progressArr) => {
    if (progressArr.length === 0) {
      // Before analysis: all clocks
      return <ClockIcon className="w-5 h-5 text-gray-400 inline mr-2" />;
    }
    if (step === "complete" && progressArr.includes("complete")) {
      return <CheckCircleIcon className="w-5 h-5 text-green-500 inline mr-2" />;
    }
    if (idx < currentIdx) {
      return <CheckCircleIcon className="w-5 h-5 text-green-500 inline mr-2" />;
    }
    if (idx === currentStepIdx && step !== "complete") {
      return <ArrowPathIcon className="w-5 h-5 text-blue-500 animate-spin inline mr-2" />;
    }
    return <ClockIcon className="w-5 h-5 text-gray-400 inline mr-2" />;
  };

  // Find current step index
  const currentStepIdx = progress.length
    ? STEPS.findIndex((s) => s.key === progress[progress.length - 1])
    : 0;

  return (
    <div className="min-h-screen bg-gray-50 font-sans">
      <main className=" p-4 flex flex-row gap-8 h-screen">
        {/* Left: Input Card (30%) */}
        <div className="h-full overflow-y-auto">
          <Card className="mb-8 md:mb-0">
            <CardHeader>
              <CardTitle className="text-xl font-semibold text-gray-800">Analyze Your Curriculum</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit}>
                <Textarea
                  className="w-full h-32 mb-4"
                  placeholder="Paste your curriculum text here..."
                  value={curriculum}
                  onChange={(e) => setCurriculum(e.target.value)}
                  disabled={streaming}
                />
                <div className="flex gap-3">
                  <Button
                    type="submit"
                    className="bg-blue-600 hover:bg-blue-700 text-white px-5 py-2 rounded-lg font-semibold shadow disabled:bg-gray-400 transition"
                    disabled={streaming}
                  >
                    Analyze
                  </Button>
                  <Button
                    type="button"
                    className="bg-teal-600 hover:bg-teal-700 text-white px-5 py-2 rounded-lg font-semibold shadow disabled:bg-gray-400 transition"
                    disabled={!submitted || streaming}
                    onClick={handleView}
                  >
                    View Results
                  </Button>
                  {messages.length > 0 && !streaming && (
                    <Button
                      className="bg-purple-600 hover:bg-purple-700 text-white px-5 py-2 rounded-lg font-semibold shadow transition"
                      onClick={handleDownloadParsed}
                      type="button"
                    >
                      Download PDF
                    </Button>
                  )}
                </div>
              </form>
              <div>
                <h2 className="text-xl font-semibold mb-4 text-gray-800 mt-6">Analysis Progress</h2>
                {/* Stepper */}
                <ol className="mb-6">
                  {STEPS.map((step, idx) => (
                    <li
                      key={step.key}
                      className={
                        progress.length === 0
                          ? "flex items-center mb-2 text-gray-400"
                          : `flex items-center mb-2 ${
                              idx === currentStepIdx && progress.includes(step.key)
                                ? "font-bold text-blue-700"
                                : idx < currentStepIdx
                                ? "text-gray-500"
                                : "text-gray-400"
                            }`
                      }
                    >
                      {getStepIcon(step.key, idx, currentStepIdx, progress)}
                      {step.label}
                    </li>
                  ))}
                </ol>
              </div>
            </CardContent>
          </Card>
        </div>
        {/* Right: Results Card (70%) */}
        <div className="w-[70%] h-full overflow-y-auto">
          <Card className="min-h-[400px] flex flex-col">
            <CardHeader>
              <CardTitle className="text-xl font-semibold text-gray-800">Results</CardTitle>
            </CardHeader>
            <CardContent className="flex-1">
              <div
                ref={outputRef}
                className="flex-1 overflow-y-auto text-base text-gray-800"
              >
                {messages.length === 0 && (
                  <span className="text-gray-400">
                    {streaming
                      ? "Streaming analysis..."
                      : "Submit your curriculum and click 'View Results'."}
                  </span>
                )}
                {messages.map((msg, idx) => {
                  if (msg.type === "markdown") {
                    return (
                      <div key={idx} className="mb-4 prose prose-blue max-w-none">
                        <ReactMarkdown>{msg.content}</ReactMarkdown>
                      </div>
                    );
                  }
                  if (msg.type === "list") {
                    return (
                      <div key={idx} className="mb-4">
                        <ul className="list-disc ml-6">
                          {msg.content.map((item, i) => (
                            <li key={i}>{item}</li>
                          ))}
                        </ul>
                      </div>
                    );
                  }
                  if (
                    msg.step === "jobs_fetched" &&
                    Array.isArray(msg.content) &&
                    msg.content.length > 0 &&
                    typeof msg.content[0] === "object"
                  ) {
                    return (
                      <div key={idx} className="overflow-x-auto mb-4">
                        <table className="min-w-full text-xs text-left text-gray-700 border">
                          <thead>
                            <tr>
                              <th className="px-2 py-1 border">Title</th>
                              <th className="px-2 py-1 border">Company</th>
                              <th className="px-2 py-1 border">Location</th>
                              <th className="px-2 py-1 border">Source</th>
                              <th className="px-2 py-1 border">Posted</th>
                              <th className="px-2 py-1 border">Salary</th>
                              <th className="px-2 py-1 border">Description</th>
                              <th className="px-2 py-1 border">Link</th>
                            </tr>
                          </thead>
                          <tbody>
                            {msg.content.map((job, i) => (
                              <tr key={i} className="border-t border-gray-300">
                                <td className="px-2 py-1 border">{job.title}</td>
                                <td className="px-2 py-1 border">{job.company}</td>
                                <td className="px-2 py-1 border">{job.location}</td>
                                <td className="px-2 py-1 border">{job.source_platform}</td>
                                <td className="px-2 py-1 border">{job.posted_date}</td>
                                <td className="px-2 py-1 border">{job.salary}</td>
                                <td className="px-2 py-1 border max-w-xs">
                                  <div className="prose prose-blue max-w-xs">
                                    <ReactMarkdown>{job.description}</ReactMarkdown>
                                  </div>
                                </td>
                                <td className="px-2 py-1 border">
                                  {job.job_url && (
                                    <a
                                      href={job.job_url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="text-blue-600 underline"
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
                  if (msg.type === "error") {
                    return (
                      <div key={idx} className="text-red-500 mb-2">
                        {msg.content}
                      </div>
                    );
                  }
                  return (
                    <div key={idx} className="mb-2">
                      {msg.content}
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}

export default App;
