import React from "react";
import { Link } from "react-router";
import "../App.css";

function Home() {
  return (
    <div className="Home">
      <div className="home-contents">
        <div className="welcome-txt">
          <h1>Welcome to Hospital Recommender</h1>
        </div>
        <Link to={"/recommendation"}>
          {" "}
          <button className="explore">Explore</button>{" "}
        </Link>
      </div>
    </div>
  );
}

export default Home;
