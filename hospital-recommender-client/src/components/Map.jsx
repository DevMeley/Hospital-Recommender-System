// src/components/MapComponent.jsx
import React, { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

const MapComponent = ({ destination }) => {
  const mapRef = useRef(null);
  const routeLayerRef = useRef(null);
  const [origin, setOrigin] = useState(null);

  useEffect(() => {
    // Ask for user location
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setOrigin([pos.coords.latitude, pos.coords.longitude]); // [lat, lng]
      },
      (err) => {
        console.error("Geolocation error:", err);
        // fallback (Akure as default)
        setOrigin([7.2526, 5.1931]);
      }
    );
  }, []);

  useEffect(() => {
    if (!origin || !destination) return;

    // Initialize map only once
    if (!mapRef.current) {
      mapRef.current = L.map("map").setView(origin, 13);

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap contributors",
      }).addTo(mapRef.current);
    }

    // Add markers
    L.marker(origin).addTo(mapRef.current).bindPopup("You are here").openPopup();
    L.marker(destination).addTo(mapRef.current).bindPopup("Hospital");

    // Fetch route
    const getRoute = async () => {
      try {
        const res = await fetch(
          "https://api.openrouteservice.org/v2/directions/driving-car/geojson",
          {
            method: "POST",
            headers: {
              Authorization: "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjY2YTFiZDY4OThjOTRiY2RiOGNmZDkyYmZmYmIyOTlkIiwiaCI6Im11cm11cjY0In0=", // replace with your ORS key
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              coordinates: [
                [origin[1], origin[0]], // [lng, lat]
                [destination[1], destination[0]],
              ],
            }),
          }
        );

        const data = await res.json();

        if (!res.ok) {
          console.error("ORS Error:", data);
          return;
        }

        // Remove old route if exists
        if (routeLayerRef.current) {
          mapRef.current.removeLayer(routeLayerRef.current);
        }

        // Draw new route
        routeLayerRef.current = L.geoJSON(data, {
          style: { color: "blue", weight: 4 },
        }).addTo(mapRef.current);

        // Fit map to route
        mapRef.current.fitBounds(routeLayerRef.current.getBounds());
      } catch (err) {
        console.error("Route error:", err);
      }
    };

    getRoute();
  }, [origin, destination]);

  return (
    <div
      id="map"
      style={{ height: "400px", width: "100%", marginTop: "1rem" }}
    />
  );
};

export default MapComponent;
