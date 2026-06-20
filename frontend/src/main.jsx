// Frontend entry point: mount the React app into #root (see index.html).
// StrictMode is intentional — it surfaces unsafe lifecycles and accidental side
// effects during development (it double-invokes renders in dev only).
import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
