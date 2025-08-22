import React, { useState } from "react";
import "../Styles/MainPage.css";
import Nav from "./Nav";
import Recommendations from "./Recommendations";
import { Link } from "react-router";

function MainPage({ formData, handleGetRecommendation, setFormData, error }) {
  return (
    <div className="main-page">
      <div className="inputs">
        <div className="left">
          <label>
            <p>Location(e.g Ikeja) </p>
            <input
              type="text"
              value={formData.location}
              onChange={(e) =>
                setFormData({ ...formData, location: e.target.value })
              }
            />
          </label>
          <label>
            <p>Service Type(e.g General Medicine) </p>
            <input
              type="text"
              value={formData.service_needed}
              onChange={(e) =>
                setFormData({ ...formData, service_needed: e.target.value })
              }
            />
          </label>
        </div>
        <div className="right">
          <h2>Preferences</h2>
          <div className="right-input">
            <label>
              <p>Treatment Cost</p>
              <select
                name="Cost"
                value={formData.cost_preference}
                onChange={(e) =>
                  setFormData({ ...formData, cost_preference: e.target.value })
                }
              >
                <option value="" className="option">
                  value
                </option>
                <option value="High">Expensive</option>
                <option value="Medium">Moderate</option>
                <option value="Low">Affordable</option>
              </select>
            </label>
            <label>
              <p>Service Quality</p>
              <select
                name="Quality"
                value={formData.quality_preference}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    quality_preference: e.target.value,
                  })
                }
              >
                <option value="" className="option">
                  value
                </option>
                <option value="High">High-Quality</option>
                <option value="Medium">Standard</option>
                <option value="Low">Low-Quality</option>
              </select>
            </label>
          </div>
        </div>
        {/* <Link to={'/recommend'}> */}
          <button className="get" onClick={handleGetRecommendation}>
            Get Recommendation
          </button>
        {/* </Link> */}
      </div>
        {error && <div className="error-message">{error}</div>}
    </div>
  );
}

export default MainPage;
