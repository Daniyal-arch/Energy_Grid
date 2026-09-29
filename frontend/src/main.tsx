import "maplibre-gl/dist/maplibre-gl.css";
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import EuropeView from "./components/EuropeView";
import RailDayView from "./components/RailDayView";
import "./index.css";

// standalone views instead of the atlas: ?railday=YYYYMMDD|latest, ?europe
const params = new URLSearchParams(window.location.search);
const railDay = params.get("railday");
const europe = params.has("europe");

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>{railDay ? <RailDayView date={railDay} /> : europe ? <EuropeView /> : <App />}</React.StrictMode>,
);
