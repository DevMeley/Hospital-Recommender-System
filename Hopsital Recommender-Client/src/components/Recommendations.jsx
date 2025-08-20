
import React, { useEffect, useState } from "react";
import "../App.css";
import { geocodeWithNominatim } from "../../utils/geocode"; // You'll create this
import MapComponent from "./Map"; // You'll also create this

// function Recommendations({ recommendation, isLoading, error }) {
//   const [geoCoded, setGeoCoded] = useState([]);
//   const [selectedHospital, setSelectedHospital] = useState(null);
//   const [userCoords, setUserCoords] = useState(null);

//   // Get user's current location
//   useEffect(() => {
//     navigator.geolocation.getCurrentPosition(
//       (pos) => setUserCoords([pos.coords.latitude, pos.coords.longitude]),
//       () => setUserCoords([6.5244, 3.3792]) // fallback: Lagos
//     );
//   }, []);

//   // Geocode hospital addresses when recommendations arrive
//   useEffect(() => {
//     const fetchCoords = async () => {
//       const result = [];

//       for (let hospital of recommendation) {
//         const coords = await geocodeWithNominatim(hospital.full_address);
//         result.push({
//           ...hospital,
//           coords: coords || null, // store even if geocoding fails
//         });
//       }

//       setGeoCoded(result);
//     };

//     if (recommendation.length) {
//       fetchCoords();
//     }
//   }, [recommendation]);

//   return (
//     <div>
//       <div className="Recommendation">
//         <h3>Recommendations</h3>
//         {isLoading ? (
//           <img src="assets/spinner.gif" alt="Loading..." />
//         ) : (
//           <div className="Table">
//             <table>
//               <thead>
//                 <tr>
//                   <th>S/N</th>
//                   <th>Name</th>
//                   <th>Services</th>
//                   <th>Address</th>
//                   <th>Recommendation</th>
//                   <th>Map</th>
//                 </tr>
//               </thead>
//               <tbody>
//                 {geoCoded.map((recommend, idx) => (
//                   <tr key={recommend.name}>
//                     <td>{idx + 1}</td>
//                     <td>{recommend.name}</td>
//                     <td>{recommend.services}</td>
//                     <td>{recommend.full_address}</td>
//                     <td>
//                       {recommend.recommendation_score > 0.5
//                         ? "Highly Recommended"
//                         : "Not Recommended"}
//                     </td>
//                     <td>
//                       {recommend.coords ? (
//                         <button className="rec-btn" onClick={() => setSelectedHospital(recommend)}>
//                           View on Map
//                         </button>
//                       ) : (
//                         <span style={{ color: "gray" }}>
//                           Location unavailable
//                         </span>
//                       )}
//                     </td>
//                   </tr>
//                 ))}
//               </tbody>
//             </table>

//             {selectedHospital && userCoords && selectedHospital.coords && (
//               <div style={{ marginTop: "20px", marginBottom:"20px" }}>
//                 <h4>Route to: {selectedHospital.name}</h4>
//                 <MapComponent
//                   origin={userCoords}
//                   destination={selectedHospital.coords}
//                 />
//               </div>
//             )}
//           </div>
//         )}
//       </div>
//     </div>
//   );
// }

// export default Recommendations;

const API_BASE_URL = "https://hospital-recommender-system.onrender.com/recommend"

function Recommendations({ recommendation, isLoading, error, mapUrl }) {

  const getMapUrl = (mapUrl) => {
  if (!mapUrl) return null;
  return mapUrl.startsWith("http") ? mapUrl : `${API_BASE_URL}${mapUrl}`;
};
  return (
    <div>
      <div className="Recommendation">
        <h3>Recommendations</h3>

        {isLoading ? (
          <img src="assets/spinner.gif" alt="Loading..." />
        ) : (
          <>
            <div className="Table">
              <table>
                <thead>
                  <tr>
                    <th>S/N</th>
                    <th>Name</th>
                    <th>Services</th>
                    <th>Address</th>
                    <th>Recommendation level</th>
                  </tr>
                </thead>
                <tbody>
                  {recommendation.map((recommend, idx) => (
                    <tr key={recommend.name}>
                      <td>{idx + 1}</td>
                      <td>{recommend.name}</td>
                      <td>{recommend.services}</td>
                      <td>{recommend.full_address}</td>
                      <td>
                        {recommend.recommendation_score > 0.5
                          ? "Highly Recommended"
                          : "Not recommended"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Embed map here */}
            {mapUrl && (
  <div className="mt-4">
    <h2 className="route_time">Route Map</h2>
    <img 
      src={getMapUrl(mapUrl)}
      alt="Route Map" 
      className="map_img"
    />
  </div>
)}
          </>
        )}
      </div>
    </div>
  );
}

export default Recommendations