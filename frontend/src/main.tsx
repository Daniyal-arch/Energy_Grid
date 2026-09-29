import "maplibre-gl/dist/maplibre-gl.css";
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import RailDayView from "./components/RailDayView";
import "./index.css";

// ?railday=YYYYMMDD opens the standalone rail-day time-lapse instead of the atlas
const railDay = new URLSearchParams(window.location.search).get("railday");

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>{railDay ? <RailDayView date={railDay} /> : <App />}</React.StrictMode>,
);
