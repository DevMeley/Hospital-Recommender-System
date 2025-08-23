// // src/components/MapComponent.jsx
// import React, { useEffect, useRef, useState } from "react";
// import L from "leaflet";
// import "leaflet/dist/leaflet.css";

// // Props:
// //   destination: [lat, lon]  (from backend hospital coords)
// //   originHint: string       (optional: user's typed location like "Ikorodu")
// //   originFallback: [lat, lon] (optional: last resort fallback; default Lagos)
// const MapComponent = ({ destination, originHint = "", originFallback = [6.5244, 3.3792] }) => {
//   const [origin, setOrigin] = useState(null);
//   const mapRef = useRef(null);
//   const containerRef = useRef(null);

//   // --- helper: geocode a place name as a fallback (only if needed) ---
//   const geocodePlace = async (place) => {
//     if (!place) return null;
//     try {
//       const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(place)}`;
//       const res = await fetch(url, { headers: { "Accept": "application/json" } });
//       const data = await res.json();
//       if (!data?.[0]) return null;
//       return [parseFloat(data[0].lat), parseFloat(data[0].lon)];
//     } catch {
//       return null;
//     }
//   };

//   // --- get user's current location with high accuracy & quality checks ---
//   useEffect(() => {
//     let cancelled = false;
//     if (!destination) return;

//     const opts = { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 };

//     navigator.geolocation.getCurrentPosition(
//       async (pos) => {
//         if (cancelled) return;
//         const cand = [pos.coords.latitude, pos.coords.longitude];
//         const accuracy = pos.coords.accuracy ?? 99999; // meters

//         // If accuracy is poor (>5km), try the user's typed location as a better hint
//         if (accuracy > 5000 && originHint) {
//           const hinted = await geocodePlace(originHint);
//           setOrigin(hinted || cand);
//         } else {
//           setOrigin(cand);
//         }
//       },
//       async () => {
//         if (cancelled) return;
//         // Permission denied or timeout -> try originHint, then final fallback
//         const hinted = await geocodePlace(originHint);
//         setOrigin(hinted || originFallback);
//       },
//       opts
//     );

//     return () => {
//       cancelled = true;
//     };
//   }, [destination, originHint, originFallback]);

//   // --- build the map once we have both origin & destination ---
//   useEffect(() => {
//     if (!origin || !destination) return;

//     // clean up any prior map instance
//     if (mapRef.current) {
//       mapRef.current.remove();
//       mapRef.current = null;
//     }

//     const map = L.map(containerRef.current).setView(origin, 13);
//     mapRef.current = map;

//     L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
//       attribution: "&copy; OpenStreetMap contributors",
//     }).addTo(map);

//     L.marker(origin).addTo(map).bindPopup("Your Location");
//     L.marker(destination).addTo(map).bindPopup("Hospital");

//     // fetch route from OpenRouteService (requires a valid key)
//     const getRoute = async () => {
//       try {
//         const res = await fetch(
//           "https://api.openrouteservice.org/v2/directions/driving-car/geojson",
//           {
//             method: "POST",
//             headers: {
//               Authorization: "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjY2YTFiZDY4OThjOTRiY2RiOGNmZDkyYmZmYmIyOTlkIiwiaCI6Im11cm11cjY0In0=", // move to backend or .env in production
//               "Content-Type": "application/json",
//             },
//             body: JSON.stringify({
//               coordinates: [
//                 [origin[1], origin[0]],       
//                 [destination[1], destination[0]],
//               ],
//             }),
//           }
//         );

//         const data = await res.json();

//         if (data?.features?.length) {
//           L.geoJSON(data, { style: { weight: 4 } }).addTo(map);

//           // Fit to the route
//           const latLngs = data.features[0].geometry.coordinates.map(([lng, lat]) => [lat, lng]);
//           map.fitBounds(latLngs);
//         } else {
//           console.warn("No route found", data);
//           // fall back to fitting both points
//           map.fitBounds([origin, destination]);
//         }
//       } catch (err) {
//         console.error("Route error:", err);
//         map.fitBounds([origin, destination]);
//       }
//     };

//     getRoute();

//     return () => {
//       map.remove();
//       mapRef.current = null;
//     };
//   }, [origin, destination]);

//   return <div ref={containerRef} style={{ height: 400, width: "100%", marginTop: "1rem" }} />;
// };

// export default MapComponent;


// src/components/MapComponent.jsx
import React, { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

const MapComponent = ({ origin, destination }) => {
  const mapRef = useRef(null); // store map instance
  const routeLayerRef = useRef(null); // store route layer

  useEffect(() => {
    if (!mapRef.current) {
      // Initialize map ONCE
      mapRef.current = L.map("map").setView(origin || [9.082, 8.6753], 6); // Nigeria center fallback

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap contributors",
      }).addTo(mapRef.current);
    }

    if (origin) {
      L.marker(origin).addTo(mapRef.current).bindPopup("Your Location").openPopup();
      mapRef.current.setView(origin, 13);
    }

    if (destination) {
      L.marker(destination).addTo(mapRef.current).bindPopup("Hospital");
    }

    // Fetch route if both exist
    if (origin && destination) {
      const getRoute = async () => {
        try {
          const res = await fetch(
            "https://api.openrouteservice.org/v2/directions/driving-car/geojson",
            {
              method: "POST",
              headers: {
                Authorization: "YOUR_API_KEY_HERE",
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                coordinates: [
                  [origin[1], origin[0]],
                  [destination[1], destination[0]],
                ],
              }),
            }
          );

          const data = await res.json();

          // Remove old route if exists
          if (routeLayerRef.current) {
            mapRef.current.removeLayer(routeLayerRef.current);
          }

          // Add new route
          routeLayerRef.current = L.geoJSON(data, {
            style: { color: "blue", weight: 4 },
          }).addTo(mapRef.current);
        } catch (err) {
          console.error("Route error:", err);
        }
      };

      getRoute();
    }
  }, [origin, destination]); // only rerun when these change

  return (
    <div
      id="map"
      style={{ height: "400px", width: "100%", marginTop: "1rem" }}
    />
  );
};

export default MapComponent;

