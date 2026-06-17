"use client";

import { useEffect, useRef, useState } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";
import { tokenManager } from "@/lib/api-client";
import { Terminal as TerminalIcon, AlertTriangle } from "lucide-react";

interface WebTerminalProps {
  vmId: number;
}

export default function WebTerminal({ vmId }: WebTerminalProps) {
  const terminalRef = useRef<HTMLDivElement>(null);
  const terminalInstance = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const [status, setStatus] = useState<"connecting" | "connected" | "disconnected" | "error">("connecting");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!terminalRef.current) return;

    // Initialize Terminal
    const term = new Terminal({
      cursorBlink: true,
      fontFamily: '"Fira Code", "Courier New", monospace',
      fontSize: 14,
      theme: {
        background: "#0d1117",
        foreground: "#c9d1d9",
        cursor: "#58a6ff",
        cursorAccent: "#0d1117",
        selectionBackground: "rgba(88, 166, 255, 0.3)",
        black: "#484f58",
        red: "#ff7b72",
        green: "#3fb950",
        yellow: "#d29922",
        blue: "#58a6ff",
        magenta: "#bc8cff",
        cyan: "#39c5cf",
        white: "#b1bac4",
        brightBlack: "#6e7681",
        brightRed: "#ffa198",
        brightGreen: "#56d364",
        brightYellow: "#e3b341",
        brightBlue: "#79c0ff",
        brightMagenta: "#d2a8ff",
        brightCyan: "#56d4dd",
        brightWhite: "#ffffff",
      },
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(terminalRef.current);
    fitAddon.fit();

    terminalInstance.current = term;
    fitAddonRef.current = fitAddon;

    term.writeln("\x1b[1;34m[VMLedger Terminal]\x1b[0m Initializing secure connection...");

    // Initialize WebSocket
    const token = tokenManager.getToken();
    if (!token) {
      term.writeln("\x1b[1;31m[Error]\x1b[0m Authentication required. Please log in.");
      setStatus("error");
      setErrorMessage("Authentication required");
      return;
    }

    const wsUrl = process.env.NEXT_PUBLIC_API_BASE_URL
      ? process.env.NEXT_PUBLIC_API_BASE_URL.replace(/^http/, "ws")
      : "ws://localhost:8000";
      
    const ws = new WebSocket(`${wsUrl}/ws/vms/${vmId}/ssh?token=${token}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus("connected");
      // Send initial resize event based on current terminal dimensions
      const cols = term.cols;
      const rows = term.rows;
      ws.send(JSON.stringify({ type: "resize", cols, rows }));
    };

    ws.onmessage = (event) => {
      term.write(event.data);
    };

    ws.onclose = (event) => {
      if (status !== "error") {
        setStatus("disconnected");
        term.writeln(`\r\n\x1b[1;33m[Connection closed]\x1b[0m (Code: ${event.code})`);
      }
    };

    ws.onerror = (error) => {
      setStatus("error");
      setErrorMessage("WebSocket connection failed");
      term.writeln("\r\n\x1b[1;31m[Connection error]\x1b[0m WebSocket error occurred.");
      console.error("WebSocket Error:", error);
    };

    // Handle terminal input -> send to WebSocket
    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(data);
      }
    });

    // Handle window resize -> fit terminal and send new dimensions to server
    const handleResize = () => {
      if (fitAddon && term) {
        fitAddon.fit();
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(
            JSON.stringify({
              type: "resize",
              cols: term.cols,
              rows: term.rows,
            })
          );
        }
      }
    };

    window.addEventListener("resize", handleResize);

    // Cleanup on unmount
    return () => {
      window.removeEventListener("resize", handleResize);
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
      term.dispose();
    };
  }, [vmId]);

  return (
    <div className="flex flex-col h-full w-full bg-[#0d1117] rounded-lg overflow-hidden border border-gray-800 shadow-2xl">
      {/* Terminal Header */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-900 border-b border-gray-800">
        <div className="flex items-center space-x-2">
          <TerminalIcon className="w-4 h-4 text-gray-400" />
          <span className="text-sm font-medium text-gray-300">Terminal</span>
        </div>
        <div className="flex items-center space-x-3">
          {status === "connecting" && (
            <div className="flex items-center space-x-2 text-yellow-500">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-yellow-500"></span>
              </span>
              <span className="text-xs">Connecting...</span>
            </div>
          )}
          {status === "connected" && (
            <div className="flex items-center space-x-2 text-green-500">
              <span className="relative flex h-2 w-2">
                <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
              </span>
              <span className="text-xs">Connected</span>
            </div>
          )}
          {status === "disconnected" && (
            <div className="flex items-center space-x-2 text-gray-500">
              <span className="relative flex h-2 w-2">
                <span className="relative inline-flex rounded-full h-2 w-2 bg-gray-500"></span>
              </span>
              <span className="text-xs">Disconnected</span>
            </div>
          )}
          {status === "error" && (
            <div className="flex items-center space-x-1 text-red-500">
              <AlertTriangle className="w-3 h-3" />
              <span className="text-xs">Error</span>
            </div>
          )}
        </div>
      </div>

      {/* Terminal Container */}
      <div className="flex-1 p-2 overflow-hidden relative">
        <div ref={terminalRef} className="h-full w-full" />
      </div>
    </div>
  );
}
