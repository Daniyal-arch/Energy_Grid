import "maplibre-gl/dist/maplibre-gl.css";
import React, { Suspense, lazy } from "react";
import ReactDOM from "react-dom/client";
import App from "./ui/App";
import "./index.css";

// ?capture=16x9: the earlier single view, kept for the video recorder (docs/VIDEO.md);
// with &app the recorder records this app instead
const EuropeView = lazy(() => import("./components/EuropeView"));
// ?coverage: the coverage registry as a matrix with each cell's evidence (brief 30)
const CoverageExplorer = lazy(() => import("./ui/CoverageExplorer"));
// ?compare=France;Germany: two to six places side by side (?compare=1 stays the Maps view)
const ComparePage = lazy(() => import("./ui/ComparePage"));
// ?downloads: per dataset its files, licence, attribution and as-of date (brief 30)
const Downloads = lazy(() => import("./ui/Downloads"));
const cmp = new URLSearchParams(window.location.search).get("compare");
const params = new URLSearchParams(window.location.search);
const capture = params.has("capture") && !params.has("app");

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {capture ? (
      <Suspense fallback={null}>
        <EuropeView />
      </Suspense>
    ) : cmp && cmp !== "1" ? (
      <Suspense fallback={null}>
        <ComparePage />
      </Suspense>
    ) : params.has("downloads") ? (
      <Suspense fallback={null}>
        <Downloads />
      </Suspense>
    ) : params.has("coverage") ? (
      <Suspense fallback={null}>
        <CoverageExplorer />
      </Suspense>
    ) : (
      <App />
    )}
  </React.StrictMode>,
);
