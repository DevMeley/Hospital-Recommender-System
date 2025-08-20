import React from 'react'
import "../Styles/SideBar.css"

function SideBar() {
  return (
    <div className='side-bar'>
        <h2>Dashboard</h2>
        <div className="links">
          <p>Recommend</p>
          <p>Map</p>
        </div>
    </div>
  )
}

export default SideBar