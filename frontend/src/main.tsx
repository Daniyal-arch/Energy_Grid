import "maplibre-gl/dist/maplibre-gl.css";
import React, { Suspense, lazy } from "react";
import ReactDOM from "react-dom/client";
import App from "./ui/App";
import "./index.css";

// ?capture=16x9: the earlier single view, kept for the video recorder (docs/VIDEO.md);
// with &app the recorder records this app instead
const EuropeView = lazy(() => import("./components/EuropeView"));
const params = new URLSearchParams(window.location.search);
const capture = params.has("capture") && !params.has("app");

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {capture ? (
      <Suspense fallback={null}>
        <EuropeView />
      </Suspense>
    ) : (
      <App />
    )}
  </React.StrictMode>,
);
