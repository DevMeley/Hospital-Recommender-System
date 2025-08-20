// src/components/MapComponent.jsx
import React, { useEffect } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

const MapComponent = ({ origin, destination }) => {
  useEffect(() => {
    const map = L.map("map").setView(origin, 13);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);

    L.marker(origin).addTo(map).bindPopup("Your Location");
    L.marker(destination).addTo(map).bindPopup("Hospital");

    const getRoute = async () => {
      try {
        const res = await fetch(
          "https://api.openrouteservice.org/v2/directions/driving-car/geojson",
          {
            coordinates: [
              [origin[1], origin[0]],
              [destination[1], destination[0]],
            ],
          },
          {
            method: "POST",
            headers: {
              Authorization: "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjU4ZTMyNzhmOGFiZjQ3YTE5MWRjM2ZhNTAyNjBlMjRlIiwiaCI6Im11cm11cjY0In0=",
              "Content-Type": "application/json",
            },
          }
        );

        L.geoJSON(res.data, {
          style: { color: "blue", weight: 4 },
        }).addTo(map);
      } catch (err) {
        console.error("Route error:", err);
      }
    };

    getRoute();

    return () => map.remove();
  }, [origin, destination]);

  return <div id="map" style={{ height: "400px", width: "100%", marginTop: "1rem" }} />;
};

export default MapComponent;
